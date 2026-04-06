# ADR-002: LLM-Based Code Generation over Rule-Based Transformation

## Status
Accepted (Updated — domain extraction step removed; code generation retained)

## Context

Translating a Java/Spring Boot application to Node.js requires understanding:
- Java-specific idioms (annotations, generics, Spring DI)
- Domain semantics buried in business logic
- Mapping of Spring patterns to equivalent Node.js patterns (e.g., `@Service` → injectable class, `JpaRepository` → TypeORM repository)
- Nuanced naming conventions, validation logic, and error handling strategies

**Alternatives considered:**

| Option | Reason Rejected |
|---|---|
| Rule-based AST-to-AST transformation (e.g., custom transpiler) | Cannot capture business semantics or infer intent from method names and logic |
| Template-based code scaffolding | Can generate structure but cannot fill in business logic, entity relationships, or use-case descriptions |
| Compiler-style intermediate representation | Enormous engineering effort; would replicate a partial Java compiler |

## Decision

Use **Large Language Models (LLMs)** exclusively for **code generation**, not for domain knowledge extraction.

Domain knowledge (entities, use cases, API endpoints) is now derived **deterministically** from Java source metadata:
- **Entities** — parsed from JPA field annotations (`@Id`, `@Column`, `@NotNull`, `@Transient`)
- **API endpoints** — parsed from Spring MVC method annotations (`@GetMapping`, `@PostMapping`, etc.) with name-based HTTP method inference as fallback
- **Use cases** — derived from public service method names using camelCase-to-title-case conversion

LLMs are used only for the final code generation step, producing TypeScript/JavaScript for:
1. Domain entities (TypeORM/Sequelize models)
2. Repository interfaces and implementations
3. DTOs (create, update, response)
4. Use case classes
5. Express/NestJS controllers

LLM calls are made via the `LLMClient` abstraction in `src/llm/llm_client_provider.py`, keeping generation logic decoupled from any specific provider.

**Why the domain extraction LLM step was removed:**
- Extracting structured domain knowledge from all classes was too slow for large codebases (dozens of API calls per run)
- JSON truncation errors occurred when LLM output exceeded `max_tokens` limits
- The same structural information (field names, method names, HTTP verbs) is reliably available from Java annotations without LLM involvement
- Only 3 classes are converted (1 Controller, 1 Service, 1 DAO/Repository) — selected deterministically by role-fit scoring

Reference files:
- [`src/generators/llm_code_creator.py`](../../src/generators/llm_code_creator.py) — code generation
- [`src/graph/nodes.py`](../../src/graph/nodes.py) — deterministic domain model builders (`_java_class_to_domain_entity`, `_java_class_to_api_endpoints`, `_java_class_to_use_cases`)

## Consequences

**Positive:**
- Pipeline is significantly faster: LLM calls only happen during code generation for 3 selected classes, not for all classes.
- No more JSON truncation errors from oversized domain extraction responses.
- Deterministic domain model building is predictable and testable without LLM.
- The system still captures intent via LLM code generation — business logic, validation rules, and naming semantics are preserved in the generated code.

**Negative:**
- Annotation-based extraction is only as good as what is present in the Java source; unannotated methods or non-standard patterns may produce incomplete domain models.
- The fallback (HTTP method inference from method names) is heuristic and may occasionally be wrong.
- Complex business rules that live in method bodies rather than annotations are not captured in the domain model.
