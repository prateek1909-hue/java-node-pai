"""
Token budget utilities for LLM prompt construction.

Provides helpers to trim method lists to fit within token budgets,
prioritising high-complexity business logic over simple accessors.
"""

import json
import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Conservative per-section budgets (tokens).  These work for all supported
# models, including GPT-4 (8 K context).  Larger-context models (GPT-4 Turbo,
# Claude) benefit automatically — these are safe *lower* bounds, not maximums.
METHODS_TOKEN_BUDGET: int = 2000
SOURCE_CTX_METHODS_BUDGET: int = 1000


def budget_methods(
    methods: List[Dict],
    max_tokens: int,
) -> Tuple[List[Dict], bool]:
    """
    Return the largest semantically-prioritised subset of *methods* that fits
    within *max_tokens* (measured with tiktoken cl100k_base).

    Priority order — highest first:
      3  High-complexity, non-accessor methods
      2  Medium-complexity, non-accessor methods
      1  Low-complexity / unknown, non-accessor
      0  Simple accessors  (get*/set*/is* with an uppercase next char)

    Accessors are dropped first because losing a ``getFirstName()`` signature
    is far less harmful than losing a ``processPayment()`` or ``validateOrder()``.

    Original list order is preserved in the returned subset so the LLM sees
    methods in their natural class order.

    Returns ``(selected, was_trimmed)``.
    """
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
    except Exception:
        return methods, False

    def _priority(m: Dict) -> int:
        name = m.get("name", "")
        complexity = (m.get("complexity") or "").strip().lower()
        if re.match(r"^(?:get|set|is)[A-Z_]", name):
            return 0
        if complexity == "high":
            return 3
        if complexity == "medium":
            return 2
        return 1

    # Sort by priority (best first) to fill the budget greedily
    sorted_methods = sorted(methods, key=_priority, reverse=True)

    selected_names: set = set()
    used = 0
    for m in sorted_methods:
        cost = len(enc.encode(json.dumps(m)))
        if used + cost > max_tokens:
            continue  # skip this one but keep trying smaller ones
        selected_names.add(m.get("name"))
        used += cost

    if len(selected_names) == len(methods):
        return methods, False

    # Restore original declaration order
    selected = [m for m in methods if m.get("name") in selected_names]
    return selected, True


def budget_source_context(
    ctx: Optional[Dict],
    max_tokens: int,
) -> Optional[Dict]:
    """
    Return a copy of *ctx* with its ``methods`` list trimmed to *max_tokens*.
    If no trimming is needed, the original dict is returned unchanged.
    """
    if not ctx or "methods" not in ctx:
        return ctx

    trimmed_methods, was_trimmed = budget_methods(ctx["methods"], max_tokens)
    if not was_trimmed:
        return ctx

    result = dict(ctx)
    result["methods"] = trimmed_methods
    logger.warning(
        "source_context for '%s': methods trimmed from %d → %d "
        "(accessors and low-complexity methods dropped first).",
        ctx.get("name", "unknown"),
        len(ctx["methods"]),
        len(trimmed_methods),
    )
    return result
