# Architecture Decision Records (ADRs)

This directory contains the Architecture Decision Records for the **Java-to-Node Agent** — an AI-powered tool that converts Java/Spring Boot applications into modern Node.js/TypeScript applications following Clean Architecture principles.

For full project documentation see the [project README](../../README.md).

ADRs are written in the [Nygard format](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions): each record captures the **Context**, **Decision**, and **Consequences** for one significant architectural choice.

---

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-001](ADR-001-langgraph-workflow-orchestration.md) | LangGraph for Workflow Orchestration | Accepted |
| [ADR-002](ADR-002-llm-based-code-generation.md) | LLM-Based Code Generation over Rule-Based Transformation | Accepted (Updated) |
| [ADR-003](ADR-003-multi-provider-llm-support.md) | Multi-Provider LLM Support (OpenAI, Azure, Anthropic) | Accepted |
| [ADR-004](ADR-004-rag-with-chromadb.md) | RAG with ChromaDB for Domain Knowledge Augmentation | Superseded by ADR-002 |
| [ADR-005](ADR-005-tree-sitter-java-parsing.md) | tree-sitter for Java Source Code Parsing | Accepted |
| [ADR-006](ADR-006-clean-architecture-output.md) | Clean Architecture as the Target Output Architecture | Accepted |
| [ADR-007](ADR-007-shared-state-pipeline.md) | Shared State Pipeline Pattern for Workflow Nodes | Accepted (Updated) |
| [ADR-008](ADR-008-template-method-generators.md) | Template Method Pattern for Code Generators | Accepted |
| [ADR-009](ADR-009-pydantic-domain-models.md) | Pydantic for Domain and Data Transfer Models | Accepted |
| [ADR-010](ADR-010-environment-based-configuration.md) | Environment-Based Configuration with pydantic-settings | Accepted |
| [ADR-011](ADR-011-flask-web-ui.md) | Flask Web UI with Server-Sent Events | Accepted |
| [ADR-012](ADR-012-multi-pass-token-recovery.md) | Multi-Pass LLM Generation with Merge for Token Recovery | Accepted |

---

## ADR Format

Each ADR follows this structure:

```
# ADR-NNN: Title

## Status
Proposed | Accepted | Deprecated | Superseded by ADR-NNN

## Context
The forces and situation that led to this decision.

## Decision
The decision that was made.

## Consequences
What becomes easier, harder, or different as a result.
```

---

## How to Add a New ADR

1. Copy the template above.
2. Number it sequentially (ADR-012, ADR-013, ...).
3. Add it to the index table in this README.
4. Link it from any relevant source files or other ADRs.
