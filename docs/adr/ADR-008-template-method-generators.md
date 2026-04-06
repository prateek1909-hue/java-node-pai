# ADR-008: Template Method Pattern for Code Generators

## Status
Accepted

## Context

The agent generates TypeScript/JavaScript code for multiple distinct artifact types: domain entities, repository interfaces, use cases, DTOs, infrastructure adapters, controllers, and configuration files. All generators share significant common behaviour:

- TypeScript/JavaScript code formatting
- Java-to-TypeScript type mapping
- File path computation per layer
- Import statement rendering
- Class header generation
- Try-catch block wrapping

Without a shared base, each generator would duplicate these utilities, leading to inconsistency and maintenance burden.

## Decision

Apply the **Template Method Pattern** using an abstract base class `BaseGenerator`.

`BaseGenerator` provides all shared utility methods as concrete implementations and declares one abstract method:

```python
class BaseGenerator(ABC):
    def __init__(self, output_dir: str = "./output", language: str = "typescript"):
        self.output_dir = Path(output_dir)
        self.language = language
        self.file_extension = ".js" if language == "javascript" else ".ts"

    @abstractmethod
    def generate(self) -> Dict[str, str]:
        """Subclasses implement this to produce file_path -> content maps."""
        pass

    # --- Shared utilities (concrete) ---
    def format_typescript(self, code: str) -> str: ...
    def indent(self, text: str, spaces: int = 2) -> str: ...
    def to_camel_case(self, snake_str: str) -> str: ...
    def to_pascal_case(self, snake_str: str) -> str: ...
    def to_kebab_case(self, text: str) -> str: ...
    def map_java_type_to_typescript(self, java_type: str) -> str: ...
    def get_entity_path(self, entity_name: str) -> str: ...
    def get_repository_interface_path(self, entity_name: str) -> str: ...
    def get_repository_impl_path(self, entity_name: str) -> str: ...
    def get_use_case_path(self, use_case_name: str) -> str: ...
    def get_dto_path(self, dto_name: str) -> str: ...
    def get_controller_path(self, controller_name: str) -> str: ...
    def render_imports(self, imports: List[Dict[str, str]]) -> str: ...
    def render_class_header(self, ...) -> str: ...
    def wrap_in_try_catch(self, code: str, ...) -> str: ...
```

The concrete `LLMCodeGenerator` extends `BaseGenerator` and implements `generate()`, which orchestrates LLM calls for each artifact type, using the base class utilities to format and path the results.

Reference files:
- [`src/generators/base_code_creator.py`](../../src/generators/base_code_creator.py) — abstract base
- [`src/generators/llm_code_creator.py`](../../src/generators/llm_code_creator.py) — concrete implementation

## Consequences

**Positive:**
- All TypeScript formatting, naming conventions, and file paths are defined in one place — a change (e.g., switching to a different file naming convention) is made once in `BaseGenerator` and propagates everywhere.
- Adding a new generator type (e.g., a GraphQL schema generator) requires only subclassing `BaseGenerator` and implementing `generate()`.
- The `ABC` enforcement ensures that any subclass missing `generate()` raises `TypeError` at instantiation, catching contract violations early.
- Java-to-TypeScript type mapping is centralised — the same mapping applies consistently across entities, DTOs, use cases, and controllers.

**Negative:**
- `BaseGenerator` accumulates utility methods over time and may become a large utility class. Methods should be extracted to separate helpers if the class grows beyond a single cohesive responsibility.
- Subclasses cannot easily override individual utility methods without risking inconsistency — any utility that needs variant behaviour across generators should be parameterised rather than overridden.
