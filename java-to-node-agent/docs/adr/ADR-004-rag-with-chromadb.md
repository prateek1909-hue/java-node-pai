# ADR-004: RAG with ChromaDB for Domain Knowledge Augmentation

## Status
Superseded by ADR-002

## Context

When generating TypeScript code for a specific entity or use case, the LLM benefits from knowing about *related* entities, business rules, and API contracts — not just the one it is currently generating. However:

- Sending the entire domain knowledge object in every prompt quickly exhausts token budgets, especially for large Java codebases.
- Naively truncating context loses important relational information.
- Rule-based filtering is brittle and misses semantic relationships.

A RAG (Retrieval-Augmented Generation) approach using ChromaDB was originally implemented to selectively retrieve relevant context for each LLM call.

## Why This Decision Was Superseded

The RAG implementation depended on a prior `extract_domain_knowledge` LLM step that:
- Was too slow for large codebases (dozens of API calls per run)
- Produced JSON truncation errors when LLM output exceeded `max_tokens` limits
- Was not needed — Java annotations and method signatures provide sufficient structural metadata deterministically

When `extract_domain_knowledge` was removed (see ADR-002), the ChromaDB RAG store had no data to index. The `rag_store.py` module was deleted as part of this simplification.

The `src/rag/` package is retained as a placeholder for future use but currently contains no active implementation.

## Original Decision (for reference)

ChromaDB was used as a local vector store with five collections (`entities`, `business_rules`, `use_cases`, `api_endpoints`, `bounded_contexts`). Before each code generation call, a semantic similarity query retrieved the top-K relevant documents, which were injected into the LLM prompt as a `RAG Context` block.

## Consequences of Removal

**Positive:**
- No ChromaDB dependency (avoids native C++ HNSWLIB installation issues on some platforms).
- No stale `.chroma_db/` index to manage.
- Faster pipeline — no embedding generation step.

**Negative:**
- Generated code for one entity no longer has context about related entities unless they are included explicitly in the prompt.
- For large, highly interconnected domain models, the generated code may miss some cross-entity relationships.
