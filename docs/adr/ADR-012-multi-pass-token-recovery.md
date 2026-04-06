# ADR-012: Multi-Pass LLM Generation with Merge for Token Recovery

## Status
Accepted

## Context

The token budget strategy introduced in ADR-002 and implemented across `token_budget.py` and `llm_client_provider.py` has two failure modes that silently discard business logic:

**Layer 2 (semantic method budgeting):** When a Java service class has more methods than fit within the 2 000-token `methods_info` budget, the lowest-priority methods are dropped before the prompt is assembled. The LLM never sees them. Previously, `budget_methods()` returned only a `bool` indicating trimming occurred — the dropped methods themselves were discarded and unrecoverable.

**Layer 3 (last-resort string truncation):** When the assembled prompt still exceeds the model's context window after Layer 2, `LLMClient._truncate_prompt()` cuts the prompt string at the last newline within the trailing 30% of the token budget. Any content after the cut is lost permanently. The LLM receives a `[... input truncated ...]` marker and generates the best code it can from the partial input.

In both cases the prior system made a single LLM call and returned whatever was generated. Dropped or truncated methods were **silently absent** from the output — callers received no indication that the generated file was incomplete, and users had no way to detect the loss short of manually diffing the Java source against the TypeScript output.

This is acceptable for simple accessors (`getFirstName()`) which the LLM regenerates by convention. It is unacceptable for high-complexity business methods (`processPayment()`, `validateOrder()`) which encode intent that cannot be reconstructed without the original source.

**Alternatives considered:**

| Option | Reason Rejected |
|---|---|
| Increase `METHODS_TOKEN_BUDGET` | Raises risk of hitting context window for 8K models; does not eliminate the problem, only defers it |
| Require user to split large classes before running | Shifts burden to the user; impractical for automated pipelines |
| Log a WARNING and accept the loss | Already done — insufficient; business logic is permanently missing from the output |
| Use a single very large prompt with all methods | Context windows vary per model; not portable across GPT-4 (8K), GPT-4 Turbo (128K), and Claude (200K) |
| Store dropped methods and ask user to re-run | Requires manual intervention per class; breaks the one-command pipeline promise |

## Decision

Implement a **multi-pass LLM generation loop** with a **structural merge** strategy in a new module `src/generators/multi_pass_merger.py`, wired into `generate_service_layer` in `src/generators/llm_code_creator.py`.

### Mechanism

**Signal changes:**

- `budget_methods()` in `token_budget.py` now returns `(selected: List[Dict], dropped: List[Dict])` instead of `(selected, was_trimmed: bool)`. The dropped list is the exact set of methods that did not fit — it feeds the recovery loop directly.
- `LLMClient` gains a `_last_call_was_truncated: bool` instance flag. It is reset to `False` at the start of every `generate()` call and set to `True` inside `_truncate_prompt()` when truncation actually fires. Callers read this flag immediately after `generate()` returns.

**Recovery loop (up to `MAX_PASSES`, default 10):**

```
passes_done = 1   ← first pass already completed by generate_service_layer

while dropped_methods remain AND passes_done < MAX_PASSES:

    batch = budget_methods(dropped_methods, EXTRA_PASS_BUDGET)[0]
    # EXTRA_PASS_BUDGET = METHODS_TOKEN_BUDGET // 2 = 1 000 tokens
    # Half budget so (first-pass-context + batch) still fits

    extra_pass_prompt:
      "DO NOT redeclare the class or existing methods.
       Output ONLY these missing methods as bare class methods:
       {json(batch)}"

    extra_code = llm_client.generate(extra_pass_prompt)
    accumulated_code = merge(accumulated_code, extra_code)
    passes_done += 1
```

**Two truncation sub-cases handled differently:**

| Sub-case | Condition | Strategy |
|---|---|---|
| A | Layer 2 dropped methods (with or without Layer 3 also firing) | Use `dropped_methods` — a clean, structured list |
| B | Layer 3 truncated but `dropped_methods` is empty | Recovery pass: LLM compares partial output against all original methods and generates what is missing |

**Merge strategy (in preference order):**

1. **Structural merge** — strip the closing `}` from the accumulated class, append the extra-pass bare methods, re-close. No additional LLM call.
2. **LLM-assisted merge** — if `_looks_like_bare_methods()` returns False (the LLM included a class wrapper despite the instruction), a fallback LLM call merges both fragments.

**Deduplication guards applied after every merge:**
- Import deduplication: extra-pass imports already present in the accumulated class are stripped before merge; a global pass re-emits unique import lines at the top.
- Method name deduplication: methods with the same name in both fragments trigger a WARNING and the first-pass version is kept.

**Configuration:**

Two new `Settings` fields control the feature:
- `enable_multi_pass: bool = True` — set `ENABLE_MULTI_PASS=false` to restore single-pass behaviour.
- `max_passes: int = 10` — cap on total LLM calls per generated file (including the first pass).

Reference files:
- [`src/generators/multi_pass_merger.py`](../../src/generators/multi_pass_merger.py) — `MultiPassMerger` class
- [`src/generators/token_budget.py`](../../src/generators/token_budget.py) — updated `budget_methods` return type
- [`src/llm/llm_client_provider.py`](../../src/llm/llm_client_provider.py) — `_last_call_was_truncated` flag
- [`src/generators/llm_code_creator.py`](../../src/generators/llm_code_creator.py) — wiring in `generate_service_layer`
- [`src/config/settings.py`](../../src/config/settings.py) — `enable_multi_pass`, `max_passes`

## Consequences

**Positive:**
- Business logic methods that previously vanished silently are now recovered in subsequent passes. A service class with 40 methods and a 2 000-token budget that previously generated only the top 25 will now generate all 40 across multiple passes.
- The merge is transparent to callers — `generate_service_layer` still returns a single string containing the complete merged class.
- `MAX_PASSES=10` means the most extreme case (a class where every pass can only fit 1 method) would still recover 9 dropped methods on top of the first pass. In practice batches are much larger.
- Multi-pass is off by default in terms of cost only when not needed: the `needs_extra_pass()` gate ensures no extra LLM calls fire for classes that fit within budget in a single pass.
- Setting `ENABLE_MULTI_PASS=false` restores prior behaviour exactly, making the feature opt-out for cost-sensitive deployments.

**Negative:**
- Extra LLM calls increase API cost and latency proportionally to the number of passes. A class requiring 3 passes costs ~3× the tokens of a single-pass class.
- The `_last_call_was_truncated` flag on `LLMClient` is not thread-safe. This is acceptable because each `LLMCodeGenerator` owns its own `LLMClient` instance (one per workflow node execution). Concurrent use of a shared `LLMClient` would require a lock or per-call return value instead of instance state.
- The structural merge relies on the LLM obeying the "bare methods only" instruction. When it does not (class wrapper included), the LLM-assisted merge fallback adds a third LLM call, further increasing cost. The `_looks_like_bare_methods()` heuristic catches most violations.
- `budget_methods` changing its return type from `(List, bool)` to `(List, List)` is a breaking change for any external callers. All internal callers have been updated; downstream code extending this module must be updated as well.
- Sub-case B recovery (truncation without a clean dropped list) relies on the LLM self-identifying missing methods from a partial class — this is less reliable than the structured sub-case A loop and may miss methods in very large classes.
