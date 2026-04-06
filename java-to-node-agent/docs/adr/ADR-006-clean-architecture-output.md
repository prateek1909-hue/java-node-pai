# ADR-006: Clean Architecture as the Target Output Architecture

## Status
Accepted

## Context

When generating the Node.js/TypeScript output, we needed to decide on the target architectural pattern. The source Java applications are typically layered (Controller → Service → Repository) but this does not directly translate well to modern Node.js idioms or best practices.

The generated codebase should be:
- Maintainable and extensible by the teams who receive it
- Framework-agnostic at the business logic level (so they can swap Express for NestJS or TypeORM for Prisma)
- Following recognised patterns that developers can understand without reading documentation
- Testable in isolation at each layer

**Alternatives considered:**

| Option | Reason Rejected |
|---|---|
| 1:1 Layer mapping (Controller/Service/Repository) | Tightly couples business logic to frameworks; doesn't separate domain from infrastructure |
| Microservices split | Too opinionated a refactor; the agent doesn't have enough context to decide service boundaries |
| MVC | Business logic bleeds into controllers and models; no separation of domain from infra |
| Hexagonal / Ports & Adapters | Very similar to Clean Architecture; Clean Architecture has clearer naming conventions for generated code |

## Decision

Use **Clean Architecture** (as defined by Robert C. Martin) as the target structure for all generated Node.js/TypeScript code.

The generated output is organised into four layers with strict dependency direction (inner layers never depend on outer):

```
src/
├── domain/                    # Layer 1: Enterprise business rules
│   ├── entities/              # Domain entities with business rules
│   └── repositories/          # Repository interfaces (ports)
├── application/               # Layer 2: Application business rules
│   ├── use-cases/             # One class per business use case
│   └── dtos/                  # Data Transfer Objects
├── infrastructure/            # Layer 3: Frameworks & adapters
│   └── repositories/          # Repository implementations (adapters)
├── presentation/              # Layer 4: Interface adapters
│   └── controllers/           # HTTP controllers / route handlers
└── index.js / index.ts        # Application entry point (Express server)
```

**Scope:** The agent selects exactly **3 source classes** from the Java codebase:
- 1 Controller → generates `presentation/controllers/`
- 1 Service → generates `application/use-cases/`
- 1 DAO/Repository → generates `infrastructure/repositories/` and `domain/repositories/`

The matching entity class generates `domain/entities/` and `application/dtos/`.

Each generation node in the workflow maps to one layer:
- `generate_domain_layer` → `domain/`
- `generate_application_layer` → `application/`
- `generate_infrastructure_layer` → `infrastructure/`
- `generate_presentation_layer` → `presentation/`
- `generate_config_files` → `package.json`, `tsconfig.json`, `src/index.js`

Reference files:
- [`src/graph/workflow.py`](../../src/graph/workflow.py) — layer generation sequence
- [`src/generators/base_code_creator.py`](../../src/generators/base_code_creator.py) — file path helpers per layer
- [`src/config/settings.py`](../../src/config/settings.py) — `architecture_pattern` setting

## Consequences

**Positive:**
- Domain logic (entities, use cases, business rules) is completely isolated from Express/NestJS/TypeORM — swapping the framework only requires changing the infrastructure and presentation layers.
- Use-case classes map 1:1 to public service methods, making the generated code's structure directly traceable to business requirements.
- Repository interfaces in the domain layer make the generated code trivially testable with mocks.
- Clean Architecture is well-documented and widely understood — developers receiving the generated code can navigate it without custom documentation.
- The generated `src/index.js` wires all layers together and produces a runnable Express server.

**Negative:**
- Clean Architecture introduces more files and indirection than a simple layered MVC — small projects may feel over-engineered.
- Developers unfamiliar with Clean Architecture may find the strict dependency rules confusing initially.
- The domain layer's repository *interfaces* require corresponding infrastructure *implementations* — generating both adds complexity to the prompt engineering.
