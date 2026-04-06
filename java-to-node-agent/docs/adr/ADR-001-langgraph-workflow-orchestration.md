# ADR-001: LangGraph for Workflow Orchestration

## Status
Accepted

## Context

The Java-to-Node.js conversion process is inherently multi-step:
1. Scan and parse Java source files
2. Categorize classes by role (Controller, Service, Entity, etc.)
3. Map inter-class dependencies
4. Design target architecture
5. Generate domain, application, infrastructure, and presentation layers
6. Write output files to disk

These steps have strict ordering requirements, shared data that flows between them, and different failure modes at each stage. We needed an orchestration mechanism to manage this pipeline reliably.

**Alternatives considered:**

| Option | Reason Rejected |
|---|---|
| Plain sequential Python functions | No state isolation, error tracking, or resumability |
| Celery / task queues | Designed for distributed async jobs; overkill for a local sequential pipeline |
| Apache Airflow | Heavy infrastructure dependency; not suitable for a CLI tool |
| Custom hand-rolled pipeline | Would re-implement what LangGraph already provides |
| LangChain LCEL chains | Good for simple prompt chains, not for multi-step stateful workflows with branching |

## Decision

Use **LangGraph** (`langgraph>=0.2.0`) as the workflow orchestration framework.

The workflow is modelled as a `StateGraph` — a directed acyclic graph (DAG) where:
- Each **node** is a pure Python function `(ConversionState) -> ConversionState`
- Each **edge** defines the execution order between nodes
- The **shared state** (`ConversionState`) is a `TypedDict` that carries all data across nodes

```
scan_codebase
    → categorize_classes
    → analyze_dependencies
    → design_architecture
    → generate_domain_layer
    → generate_application_layer
    → generate_infrastructure_layer
    → generate_presentation_layer
    → generate_config_files
    → write_outputs
    → END
```

> **Note:** An earlier version of the pipeline included an `extract_domain_knowledge` step between `analyze_dependencies` and `design_architecture`. This step was removed because LLM-based domain extraction was slow and the same information can be derived deterministically from Java annotations and method names. See ADR-002 for context.

Reference files:
- [`src/graph/workflow.py`](../../src/graph/workflow.py) — graph definition
- [`src/graph/nodes.py`](../../src/graph/nodes.py) — node implementations
- [`src/graph/state.py`](../../src/graph/state.py) — shared state definition

## Consequences

**Positive:**
- Each node is independently testable as a pure function.
- Adding or reordering pipeline steps requires only editing `workflow.py` — no code changes to node logic.
- LangGraph provides built-in checkpointing via `SqliteSaver`, enabling resumable workflows after failures.
- The DAG structure makes the execution order explicit and auditable.
- LangGraph integrates natively with the LangChain ecosystem already used for LLM calls.

**Negative:**
- Introduces a dependency on LangGraph, which is still a relatively young library with evolving APIs.
- Parallel node execution (e.g., generating multiple layers concurrently) is not used, leaving potential performance gains on the table.
- Debugging requires understanding LangGraph's state propagation model, which adds onboarding complexity.
