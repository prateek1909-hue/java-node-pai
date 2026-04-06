# ADR-009: Pydantic for Domain and Data Transfer Models

## Status
Accepted

## Context

The agent works with several layers of structured data that cross subsystem boundaries:
- **Java class metadata** parsed from source files (`JavaClass`, `JavaMethod`, `JavaField`, `JavaAnnotation`)
- **Domain models** used for code generation (`DomainEntity`, `UseCase`, `APIEndpoint`)
- **Architecture design** from the LLM (`ModernArchitecture`)
- **Output manifest** of generated files

These models must support:
- Type validation at construction time
- JSON serialisation/deserialisation (for LLM response parsing and state checkpointing)
- Default values for optional fields
- Clear, self-documenting field definitions

**Alternatives considered:**

| Option | Reason Rejected |
|---|---|
| Plain Python dataclasses | No built-in validation, JSON serialisation requires manual `__post_init__` |
| `attrs` | Good but less integrated with the pydantic-settings and LangChain ecosystem |
| Raw dictionaries | No type safety; errors surface late and are hard to diagnose |
| TypedDict | No validation or serialisation; suitable for the state object but not domain models |

## Decision

Use **Pydantic v2** (`pydantic>=2.0.0`) for all domain models, data transfer objects, and structured LLM output schemas.

All domain models inherit from `pydantic.BaseModel` with:
- `Field(...)` for required fields with `description` metadata
- `Field(default_factory=list)` for optional collection fields
- Enum types (`DomainEntityType`) for constrained string values

```python
class DomainEntity(BaseModel):
    name: str = Field(..., description="Entity name")
    type: DomainEntityType = Field(..., description="Entity type classification")
    properties: List[Dict[str, str]] = Field(default_factory=list)
    business_rules: List[str] = Field(default_factory=list)
    relationships: List[Dict[str, str]] = Field(default_factory=list)
    validation_rules: List[str] = Field(default_factory=list)
    lifecycle: Optional[str] = Field(default=None)

class UseCase(BaseModel):
    name: str = Field(..., description="Use case name")
    description: str = Field(default="", description="What the use case does")  # optional
    actors: List[str] = Field(default_factory=list)
    preconditions: List[str] = Field(default_factory=list)
    steps: List[str] = Field(default_factory=list)
    postconditions: List[str] = Field(default_factory=list)
    entities_involved: List[str] = Field(default_factory=list)
    error_scenarios: List[str] = Field(default_factory=list)

class APIEndpoint(BaseModel):
    path: str = Field(..., description="URL path")
    method: str = Field(..., description="HTTP method")
    description: str = Field(default="")
    business_operation: str = Field(default="")
    request_schema: Optional[Dict] = Field(default=None)
    response_schema: Optional[Dict] = Field(default=None)
    path_parameters: List[Dict[str, str]] = Field(default_factory=list)
    query_parameters: List[Dict[str, str]] = Field(default_factory=list)
    validation_rules: List[str] = Field(default_factory=list)
    error_scenarios: List[Dict[str, str]] = Field(default_factory=list)
    business_logic_summary: str = Field(default="")
```

> **Note:** An earlier version included a large `DomainKnowledge` model with nested `BoundedContext`, `ClassSummary`, `MethodSummary`, etc. This was removed when LLM-based domain extraction was dropped (see ADR-002). The current `domain_models.py` contains only the three lightweight models needed by code generators.

Reference files:
- [`src/models/domain_models.py`](../../src/models/domain_models.py)
- [`src/models/java_models.py`](../../src/models/java_models.py)
- [`src/models/architecture_models.py`](../../src/models/architecture_models.py)

## Consequences

**Positive:**
- `model_dump()` and `model_validate()` provide clean, zero-boilerplate JSON round-tripping.
- Type errors in LLM responses are caught at the boundary (parsing) rather than propagating as silent `None` values.
- Pydantic v2 is significantly faster than v1 and aligns with LangChain and FastAPI ecosystem conventions.
- Simpler `domain_models.py` (3 models instead of 10+) reduces cognitive overhead.

**Negative:**
- Pydantic v2 has breaking changes from v1 (e.g., `model_dump()` vs `.dict()`) — library dependencies using Pydantic v1 internally may cause conflicts.
- The `Field(description=...)` metadata is not enforced at runtime — it relies on prompt engineering to guide the LLM to produce conformant output.
