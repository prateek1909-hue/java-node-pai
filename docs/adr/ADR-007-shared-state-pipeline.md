# ADR-007: Shared State Pipeline Pattern for Workflow Nodes

## Status
Accepted (Updated — `domain_knowledge` field removed from state)

## Context

The 10-step conversion workflow requires passing increasingly rich data between steps. Early steps (scanning, categorising) produce data consumed by later steps (architecture design, code generation). We needed to decide how to structure this inter-node data flow.

**Alternatives considered:**

| Option | Reason Rejected |
|---|---|
| Return values chained directly (functional pipeline) | Makes it hard to inspect intermediate state; each node must know the exact output shape of its predecessor |
| Global mutable object / singleton | Makes testing and parallelism difficult; hidden dependencies between steps |
| Database (SQLite, Redis) | Unnecessary infrastructure for a single-process CLI tool |
| Message queue / event bus | Overkill for a linear sequential pipeline |

## Decision

Use a **single shared `ConversionState` TypedDict** that is passed into and returned from every node.

```python
class ConversionState(TypedDict, total=False):
    # Repository inputs
    repo_path: str
    repo_url: Optional[str]
    branch: Optional[str]

    # Phase 1: Scanned data
    java_files: List[str]
    java_classes: List[JavaClass]
    total_files: int
    parsed_files: int
    parse_errors: List[Dict[str, str]]

    # Phase 2: Categorised & selected data
    classes_by_category: Dict[str, List[JavaClass]]
    selected_source_classes: Dict[str, str]          # role → class name
    selected_source_class_files: Dict[str, str]       # role → file path
    selected_source_class_details: Dict[str, Dict]    # role → metadata
    dependency_graph: Dict[str, List[str]]
    circular_dependencies: List[List[str]]

    # Phase 3: Architecture design
    architecture: Optional[ModernArchitecture]
    target_framework: str
    target_orm: str

    # Phase 4: Generated code
    generated_files: Dict[str, str]
    output_directory: str

    # Metadata
    current_step: str
    errors: List[Dict[str, Any]]
    warnings: List[str]
    start_time: Optional[float]
    end_time: Optional[float]

    # Configuration (runtime overrides passed through state)
    llm_provider: str           # openai, azure_openai, anthropic
    verbose: bool               # Enable detailed logging
    skip_tests: bool            # Whether to skip test files during scanning
```

> **Note:** An earlier version included `domain_knowledge: Optional[DomainKnowledge]` populated by an LLM extraction step. This was removed when the `extract_domain_knowledge` node was eliminated (see ADR-002). Domain models are now built deterministically inside each generation node using helpers in `src/graph/nodes.py`.

Each node receives the full state, reads what it needs, updates its own fields, and returns the modified state. This integrates natively with LangGraph's `StateGraph`, which manages state propagation.

Reference files:
- [`src/graph/state.py`](../../src/graph/state.py)
- [`src/graph/nodes.py`](../../src/graph/nodes.py)

## Consequences

**Positive:**
- Any node can read any previously written field — no rigid producer/consumer contracts between adjacent nodes.
- The entire intermediate state is inspectable at any point during execution (useful for debugging).
- LangGraph's checkpointing saves the full state to SQLite, enabling exact-point resumability after failures.
- `total=False` allows nodes to only write the fields they produce, keeping each node's contract minimal.
- `current_step`, `errors`, and `warnings` fields provide a built-in audit trail without external logging infrastructure.
- Removing `domain_knowledge` from state makes each generation node self-contained — domain models are derived on demand.

**Negative:**
- The state object is a large, flat structure — it does not enforce that a node only accesses fields relevant to its phase, risking accidental coupling.
- `TypedDict` provides type hints but no runtime validation — a node writing a wrong type into the state will not fail immediately.
- As the pipeline grows, `ConversionState` may become a "god object" containing too many fields; it should be reviewed and potentially split if the workflow branches significantly.
