"""
Multi-pass LLM generation and merge strategy.

When the token budget drops methods (Layer 2) or the prompt is truncated (Layer 3),
this module runs additional LLM passes for the remainder and merges all passes into
a single coherent source file.

Pass loop (up to settings.max_passes, default 10):
  Pass 1  — normal generate_service_layer call (called by the generator, not here)
  Pass 2+ — SecondPassMerger.run_extra_pass() with the next batch of dropped methods

Merge strategy (in preference order):
  1. Structural merge  — strip last `}`, append bare methods, re-close.
  2. LLM-assisted merge — fallback when the extra-pass code still contains a class wrapper.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from src.llm.llm_client_provider import LLMClient

from src.generators.token_budget import budget_methods, METHODS_TOKEN_BUDGET

logger = logging.getLogger(__name__)

# Budget used for each extra pass's method batch.
# Half of the normal budget so the prompt + first-pass-context still fits.
_EXTRA_PASS_METHOD_BUDGET = METHODS_TOKEN_BUDGET // 2


class MultiPassMerger:
    """
    Orchestrates up to *max_passes* LLM calls and merges their outputs.

    Usage (inside generate_service_layer):

        merger = MultiPassMerger(llm_client, language, framework, max_passes)
        if merger.needs_extra_pass(dropped_methods, prompt_was_truncated):
            final_code = merger.run(
                service_name, first_pass_code,
                dropped_methods, all_original_methods,
                prompt_was_truncated, source_context_block,
                system_prompt, temperature,
            )
        else:
            final_code = first_pass_code
    """

    def __init__(
        self,
        llm_client: "LLMClient",
        language: str = "typescript",
        framework: str = "express",
        max_passes: int = 10,
    ) -> None:
        self.llm_client = llm_client
        self.language = language
        self.framework = framework
        self.max_passes = max_passes
        self._lang_label = "JavaScript" if language == "javascript" else "TypeScript"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def needs_extra_pass(
        self,
        dropped_methods: List[Dict],
        prompt_was_truncated: bool,
    ) -> bool:
        return bool(dropped_methods) or prompt_was_truncated

    def run(
        self,
        service_name: str,
        first_pass_code: str,
        dropped_methods: List[Dict],
        all_original_methods: List[Dict],
        prompt_was_truncated: bool,
        source_context_block: str,
        system_prompt: str,
        temperature: float = 0.2,
    ) -> str:
        """
        Run up to (max_passes - 1) extra passes and return the fully merged code.

        When prompt_was_truncated is True but dropped_methods is empty (sub-case B),
        a recovery pass is run that asks the LLM to identify what is missing from the
        partial first-pass output compared to all_original_methods.
        """
        accumulated_code = first_pass_code
        remaining = list(dropped_methods)

        # Sub-case B: truncation with no cleanly dropped list — ask LLM to recover
        if prompt_was_truncated and not remaining:
            logger.info(
                "MultiPassMerger(%s): prompt was truncated with no dropped-method list "
                "— running recovery pass against all %d original methods.",
                service_name,
                len(all_original_methods),
            )
            recovery_code = self._recovery_pass(
                service_name,
                accumulated_code,
                all_original_methods,
                source_context_block,
                system_prompt,
                temperature,
            )
            accumulated_code = self._merge(service_name, accumulated_code, recovery_code)
            # After recovery there is nothing more to do
            return accumulated_code

        # Sub-case A (and normal budget-drop case): iterate over remaining batches
        passes_done = 1  # first pass already done by caller
        while remaining and passes_done < self.max_passes:
            batch, remaining = self._next_batch(remaining)
            passes_done += 1
            logger.info(
                "MultiPassMerger(%s): pass %d/%d — %d methods in batch, %d still queued.",
                service_name,
                passes_done,
                self.max_passes,
                len(batch),
                len(remaining),
            )
            extra_code = self._extra_pass(
                service_name,
                accumulated_code,
                batch,
                source_context_block,
                system_prompt,
                temperature,
            )
            accumulated_code = self._merge(service_name, accumulated_code, extra_code)

        if remaining:
            logger.warning(
                "MultiPassMerger(%s): reached max_passes=%d with %d methods still unprocessed. "
                "Increase MAX_PASSES or reduce method count.",
                service_name,
                self.max_passes,
                len(remaining),
            )

        return accumulated_code

    # ------------------------------------------------------------------
    # Pass builders
    # ------------------------------------------------------------------

    def _next_batch(self, remaining: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        Pull the next budget-sized batch from *remaining*.
        Returns (batch, still_remaining).
        """
        batch, leftover = budget_methods(remaining, _EXTRA_PASS_METHOD_BUDGET)
        # budget_methods may return all methods if tiktoken is unavailable —
        # in that case consume everything to avoid an infinite loop.
        if not leftover and len(batch) == len(remaining):
            return batch, []
        return batch, leftover

    def _extra_pass(
        self,
        service_name: str,
        accumulated_code: str,
        batch: List[Dict],
        source_context_block: str,
        system_prompt: str,
        temperature: float,
    ) -> str:
        """Ask the LLM for the missing methods only (no class wrapper)."""
        lang = self._lang_label
        user_prompt = (
            f"The following {lang} service class has already been generated. "
            f"DO NOT redeclare the class, its constructor, or any existing methods.\n\n"
            f"Existing class (do NOT repeat these methods):\n"
            f"```{self.language}\n{accumulated_code}\n```\n\n"
            f"These methods were NOT included due to token limits and must be added:\n"
            f"{json.dumps(batch, indent=2)}\n"
            f"{source_context_block}\n"
            f"Output ONLY the missing method bodies as bare {lang} class methods "
            f"(no class declaration, no imports, no constructor). "
            f"Generate ONLY the {lang} code, no explanations."
        )
        response = self.llm_client.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
        )
        return self._extract_code(response)

    def _recovery_pass(
        self,
        service_name: str,
        partial_code: str,
        all_original_methods: List[Dict],
        source_context_block: str,
        system_prompt: str,
        temperature: float,
    ) -> str:
        """
        Sub-case B recovery: the first-pass prompt was truncated mid-string.
        Ask the LLM to identify which methods from the original list are missing
        from the partial output and generate them.
        """
        lang = self._lang_label
        user_prompt = (
            f"The following {lang} service class was only partially generated because "
            f"the prompt was truncated before the LLM could complete it.\n\n"
            f"Partial class (may be incomplete):\n"
            f"```{self.language}\n{partial_code}\n```\n\n"
            f"Full original method list that should have been implemented:\n"
            f"{json.dumps(all_original_methods, indent=2)}\n"
            f"{source_context_block}\n"
            f"Compare the partial class to the method list. "
            f"Generate ONLY the methods that are missing or incomplete as bare {lang} "
            f"class methods (no class declaration, no imports, no constructor). "
            f"Generate ONLY the {lang} code, no explanations."
        )
        response = self.llm_client.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
        )
        return self._extract_code(response)

    # ------------------------------------------------------------------
    # Merge logic
    # ------------------------------------------------------------------

    def _merge(
        self,
        service_name: str,
        accumulated_code: str,
        extra_code: str,
    ) -> str:
        """
        Merge *extra_code* into *accumulated_code*.

        Tries structural merge first (strip last `}`, append methods, re-close).
        Falls back to an LLM-assisted merge if extra_code looks like a full class.
        """
        if not extra_code.strip():
            return accumulated_code

        extra_code = self._dedup_imports_from_extra(accumulated_code, extra_code)
        dedup_warnings = self._check_duplicate_methods(accumulated_code, extra_code, service_name)
        for w in dedup_warnings:
            logger.warning(w)

        if self._looks_like_bare_methods(extra_code):
            return self._structural_merge(accumulated_code, extra_code)

        logger.info(
            "MultiPassMerger(%s): extra pass returned a full class — using LLM merge fallback.",
            service_name,
        )
        return self._llm_merge(service_name, accumulated_code, extra_code)

    def _structural_merge(self, accumulated_code: str, extra_methods: str) -> str:
        """
        Strip the closing `}` of the accumulated class, append extra_methods, re-close.
        """
        last_brace = accumulated_code.rfind("}")
        if last_brace == -1:
            # Accumulated code has no closing brace — just concatenate
            return accumulated_code.rstrip() + "\n\n" + extra_methods.strip() + "\n"
        body = accumulated_code[:last_brace].rstrip()
        merged = body + "\n\n" + extra_methods.strip() + "\n}\n"
        return self._dedup_imports_global(merged)

    def _llm_merge(
        self,
        service_name: str,
        first_code: str,
        second_code: str,
    ) -> str:
        """LLM-assisted merge fallback for when extra_code contains a class wrapper."""
        lang = self._lang_label
        prompt = (
            f"Merge these two {lang} code fragments for the '{service_name}' class "
            f"into a single valid class file.\n\n"
            f"Fragment 1 (complete or partial class):\n"
            f"```{self.language}\n{first_code}\n```\n\n"
            f"Fragment 2 (additional methods):\n"
            f"```{self.language}\n{second_code}\n```\n\n"
            f"Rules:\n"
            f"- Produce a single, valid {lang} class with ALL methods from both fragments\n"
            f"- Deduplicate methods with the same name — keep the more complete version\n"
            f"- Merge imports, keeping all unique import statements at the top\n"
            f"- Output bare code only, no markdown fences\n"
            f"Generate ONLY the {lang} code, no explanations."
        )
        response = self.llm_client.generate(prompt=prompt, temperature=0.1)
        return self._extract_code(response)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _looks_like_bare_methods(code: str) -> bool:
        """
        Return True when *code* appears to be bare methods (no class declaration).
        Heuristic: no top-level `class`, `export class`, `@Injectable`, or `@Controller`.
        """
        return not re.search(
            r"^\s*(export\s+)?(abstract\s+)?class\s|"
            r"^\s*@(?:Injectable|Controller|Module)\s*\(",
            code,
            re.MULTILINE,
        )

    @staticmethod
    def _extract_import_lines(code: str) -> List[str]:
        return re.findall(r"^import\s+.+$", code, re.MULTILINE)

    def _dedup_imports_from_extra(self, accumulated_code: str, extra_code: str) -> str:
        """
        Remove from *extra_code* any import lines that already exist in *accumulated_code*.
        """
        existing = set(self._extract_import_lines(accumulated_code))
        def _keep_line(line: str) -> bool:
            if re.match(r"^\s*import\s+", line):
                return line.strip() not in existing
            return True
        return "\n".join(_keep_line(l) and l or "" for l in extra_code.splitlines()).strip()

    @staticmethod
    def _dedup_imports_global(code: str) -> str:
        """
        After a structural merge the class body may have duplicate import lines.
        Re-emit unique imports at the top.
        """
        lines = code.splitlines()
        seen_imports: set = set()
        result: List[str] = []
        for line in lines:
            if re.match(r"^\s*import\s+", line):
                key = line.strip()
                if key in seen_imports:
                    continue
                seen_imports.add(key)
            result.append(line)
        return "\n".join(result)

    @staticmethod
    def _check_duplicate_methods(
        accumulated_code: str,
        extra_code: str,
        service_name: str,
    ) -> List[str]:
        """
        Return warning strings for any method names that appear in both code blocks.
        The first-pass (accumulated) version takes precedence — callers should log these.
        """
        def _method_names(code: str) -> set:
            return set(re.findall(
                r"(?:async\s+)?(\w+)\s*\([^)]*\)\s*(?::\s*\S+\s*)?\{",
                code,
            ))

        existing = _method_names(accumulated_code)
        incoming = _method_names(extra_code)
        dupes = existing & incoming - {"constructor"}
        return [
            f"MultiPassMerger({service_name}): duplicate method '{n}' — "
            f"keeping first-pass version."
            for n in sorted(dupes)
        ]

    def _extract_code(self, response: str) -> str:
        """Strip markdown fences from an LLM response."""
        for fence in (
            f"```{self.language}",
            "```typescript",
            "```ts",
            "```javascript",
            "```js",
            "```",
        ):
            if fence in response:
                parts = response.split(fence, 1)
                return parts[1].split("```")[0].strip()
        return response.strip()
