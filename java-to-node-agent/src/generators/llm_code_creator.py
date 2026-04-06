"""
LLM-based code generator for Java-to-Node.js conversion.

Uses LLM to generate high-quality TypeScript/JavaScript code from domain models.
"""

from typing import Dict, List, Optional
import json
import logging

from src.models.domain_models import DomainEntity, UseCase, APIEndpoint
from src.generators.base_code_creator import BaseGenerator
from src.generators.token_budget import (
    budget_methods,
    budget_source_context,
    METHODS_TOKEN_BUDGET,
    SOURCE_CTX_METHODS_BUDGET,
)
from src.llm.llm_client_provider import LLMClient
from src.config.settings import Settings
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

logger = logging.getLogger(__name__)


class LLMCodeGenerator(BaseGenerator):
    """
    LLM-based code generator for Java-to-Node.js conversion.

    Extends BaseGenerator (Template Method pattern — ADR-008) and implements
    generate() by orchestrating LLM calls for each Clean Architecture layer artifact.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        super().__init__(language=self.settings.language)
        self.llm_client = LLMClient(self.settings)
        self.console = Console()
        self.language = self.settings.language
        self.language_label = "JavaScript" if self.language == "javascript" else "TypeScript"
        self.file_ext = ".js" if self.language == "javascript" else ".ts"

    def generate(self) -> Dict[str, str]:
        """
        Required by BaseGenerator (ADR-008).
        In practice, callers use the specific generate_* methods directly.
        Returns an empty dict — individual generation is driven by workflow nodes.
        """
        return {}

    def _get_code_instruction(self) -> str:
        """
        Return the closing instruction line appended to LLM prompts.

        Tells the LLM to output bare code without prose or markdown fences,
        which simplifies post-processing in _extract_code_from_response.

        Returns:
            Language-specific instruction string
        """
        if self.language == "javascript":
            return "Generate ONLY the JavaScript code, no explanations."
        return "Generate ONLY the TypeScript code, no explanations."

    # ============================================================
    # Entity Generation
    # ============================================================

    def generate_entity(self, entity: DomainEntity) -> str:
        """
        Generate a TypeORM entity class from a domain entity model.

        Produces a complete entity file with @Entity decorator, typed @Column fields,
        relationship decorators, class-validator decorators derived from business rules,
        and JSDoc comments.  Generates JavaScript or TypeScript depending on
        self.language.

        Args:
            entity: DomainEntity describing the entity's properties, rules, and relationships

        Returns:
            Source code string for the generated entity file (code only, no markdown)
        """
        related_entities = [rel.get("target", "") for rel in entity.relationships]

        if self.language == "javascript":
            system_prompt = """You are an expert JavaScript and TypeORM developer.
Generate clean, production-ready TypeORM entity classes following best practices:
- Use proper TypeORM decorators (@Entity, @Column, @ManyToOne, etc.)
- Include all properties with correct types
- Add relationships with proper decorators
- Include validation decorators from class-validator
- Add JSDoc comments explaining business logic
- Use proper naming conventions
- Export classes using module.exports"""

            user_prompt = f"""Generate a TypeORM entity class for: {entity.name}

Entity Type: {entity.type}

Properties:
{json.dumps(entity.properties, indent=2)}

Business Rules:
{json.dumps(entity.business_rules, indent=2)}

Relationships:
{json.dumps(entity.relationships, indent=2)}

Context - Related Entities in Domain:
{', '.join(related_entities) if related_entities else 'None'}

Requirements:
1. Create a complete TypeORM entity with @Entity() decorator
2. Add all properties with @Column() decorators and proper JSDoc types
3. Implement relationships using @ManyToOne, @OneToMany, @ManyToMany as needed
4. Add validation decorators (@IsNotEmpty, @IsString, @Matches, etc.) based on business rules
5. Include @PrimaryGeneratedColumn() for ID
6. Add createdAt and updatedAt timestamp columns
7. Include JSDoc comments explaining the entity's purpose and business rules
8. Export the class using module.exports

Generate ONLY the JavaScript code, no explanations."""
        else:
            system_prompt = """You are an expert TypeScript and TypeORM developer.
Generate clean, production-ready TypeORM entity classes following best practices:
- Use proper TypeORM decorators (@Entity, @Column, @ManyToOne, etc.)
- Include all properties with correct types
- Add relationships with proper decorators
- Include validation decorators from class-validator
- Add JSDoc comments explaining business logic
- Follow TypeScript strict mode conventions
- Use proper naming conventions"""

            user_prompt = f"""Generate a TypeORM entity class for: {entity.name}

Entity Type: {entity.type}

Properties:
{json.dumps(entity.properties, indent=2)}

Business Rules:
{json.dumps(entity.business_rules, indent=2)}

Relationships:
{json.dumps(entity.relationships, indent=2)}

Context - Related Entities in Domain:
{', '.join(related_entities) if related_entities else 'None'}

Requirements:
1. Create a complete TypeORM entity with @Entity() decorator
2. Add all properties with @Column() decorators and correct TypeScript types
3. Implement relationships using @ManyToOne, @OneToMany, @ManyToMany as needed
4. Add validation decorators (@IsNotEmpty, @IsString, @Matches, etc.) based on business rules
5. Include @PrimaryGeneratedColumn() for ID
6. Add createdAt and updatedAt timestamp columns
7. Include JSDoc comments explaining the entity's purpose and business rules
8. Export the class

Generate ONLY the TypeScript code, no explanations."""

        response = self.llm_client.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.2,
        )
        return self._extract_code_from_response(response)

    # ============================================================
    # Repository Generation
    # ============================================================

    def generate_repository_interface(self, entity: DomainEntity) -> str:
        """
        Generate a repository interface for a domain entity following DDD conventions.

        The interface includes standard CRUD methods (findById, findAll, save, update,
        delete) and custom query methods inferred from the entity's properties.  In
        TypeScript mode the interface uses typed Promise<T> return types; in JavaScript
        mode JSDoc type annotations are used instead.

        Args:
            entity: DomainEntity whose properties drive the custom query method signatures

        Returns:
            Source code string for the repository interface file
        """
        if self.language == "javascript":
            system_prompt = """You are an expert JavaScript developer.
Generate clean repository interfaces following Domain-Driven Design principles."""

            user_prompt = f"""Generate a repository interface for: {entity.name}

The interface should include:
1. Standard CRUD methods (findById, findAll, save, update, delete)
2. Custom query methods based on the entity's properties
3. Proper JSDoc type documentation
4. JSDoc comments
5. Return types using Promise<T>

Entity properties for reference:
{json.dumps(entity.properties, indent=2)}

Generate ONLY the JavaScript code with JSDoc type annotations, no explanations."""
        else:
            system_prompt = """You are an expert TypeScript developer.
Generate clean repository interfaces following Domain-Driven Design principles."""

            user_prompt = f"""Generate a repository interface for: {entity.name}

The interface should include:
1. Standard CRUD methods (findById, findAll, save, update, delete)
2. Custom query methods based on the entity's properties
3. Proper TypeScript types and generics
4. JSDoc comments
5. Return types using Promise<T>

Entity properties for reference:
{json.dumps(entity.properties, indent=2)}

Generate ONLY the TypeScript code, no explanations."""

        response = self.llm_client.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.2,
        )
        return self._extract_code_from_response(response)

    def generate_repository_implementation(
        self,
        entity: DomainEntity,
        interface_code: str,
        orm: str = "typeorm",
    ) -> str:
        """
        Generate an ORM-specific repository implementation that satisfies the given interface.

        Supports TypeORM (default) and Sequelize.  The generated class uses async/await,
        includes error handling with try-catch, and injects the ORM model or repository
        via constructor.

        Args:
            entity: DomainEntity the repository manages
            interface_code: Source code of the repository interface to implement
            orm: ORM to target — "typeorm" (default) or "sequelize"

        Returns:
            Source code string for the repository implementation file
        """
        if orm == "sequelize":
            if self.language == "javascript":
                system_prompt = """You are an expert Sequelize developer in JavaScript.
Generate production-ready Sequelize repository implementations."""

                user_prompt = f"""Generate a Sequelize repository implementation for: {entity.name}

Repository Interface:
```javascript
{interface_code}
```

Requirements:
1. Implement the repository interface
2. Use Sequelize model methods (findByPk, findAll, create, update, destroy)
3. Inject/receive the Sequelize model via constructor
4. Implement all interface methods using async/await
5. Add proper error handling with try-catch
6. Include logging for important operations
7. Export the class using module.exports
8. Add JSDoc comments

Generate ONLY the JavaScript code, no explanations."""
            else:
                system_prompt = """You are an expert Sequelize developer in TypeScript.
Generate production-ready Sequelize repository implementations."""

                user_prompt = f"""Generate a Sequelize repository implementation for: {entity.name}

Repository Interface:
```typescript
{interface_code}
```

Requirements:
1. Implement the repository interface
2. Use Sequelize model methods (findByPk, findAll, create, update, destroy)
3. Inject/receive the Sequelize model via constructor
4. Implement all interface methods using async/await with proper types
5. Add proper error handling with try-catch
6. Include logging for important operations
7. Add JSDoc comments

Generate ONLY the TypeScript code, no explanations."""
        elif self.language == "javascript":
            system_prompt = """You are an expert TypeORM developer in JavaScript.
Generate production-ready TypeORM repository implementations."""

            user_prompt = f"""Generate a TypeORM repository implementation for: {entity.name}

Repository Interface:
```javascript
{interface_code}
```

Requirements:
1. Implement the repository interface
2. Use TypeORM Repository from 'typeorm'
3. Export the class using module.exports
4. Implement all interface methods using TypeORM query methods
5. Add proper error handling with try-catch
6. Include logging for important operations
7. Use async/await for all database operations
8. Add JSDoc comments

Generate ONLY the JavaScript code, no explanations."""
        else:
            system_prompt = """You are an expert TypeORM developer.
Generate production-ready TypeORM repository implementations."""

            user_prompt = f"""Generate a TypeORM repository implementation for: {entity.name}

Repository Interface:
```typescript
{interface_code}
```

Requirements:
1. Implement the repository interface
2. Use TypeORM Repository<T> from 'typeorm'
3. Inject the repository using @InjectRepository decorator
4. Implement all interface methods using TypeORM query methods
5. Add proper error handling with try-catch
6. Include logging for important operations
7. Use async/await for all database operations
8. Add JSDoc comments

Generate ONLY the TypeScript code, no explanations."""

        response = self.llm_client.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.2,
        )
        return self._extract_code_from_response(response)

    # ============================================================
    # Use Case Generation
    # ============================================================

    def generate_use_case(
        self,
        use_case: UseCase,
        framework: str = "express",
        source_context: Optional[Dict] = None,
    ) -> str:
        """
        Generate a use case class containing the business logic for a single operation.

        In NestJS mode produces an @Injectable() application service; in express/default
        mode produces a plain Clean Architecture use case class with an execute() method.
        In both modes the class validates preconditions before executing business logic
        and returns a typed DTO or Result object.

        A token budget is applied to source_context (see budget_source_context) to
        prevent context-window overflow when the source class has many methods.

        Args:
            use_case: UseCase model with name, description, actors, steps, and conditions
            framework: Target framework — "nestjs" or "express" (default)
            source_context: Optional enriched metadata of the originating Java service class,
                used to include a migration note in the generated class

        Returns:
            Source code string for the generated use case / application service file
        """
        # Trim supplemental source_context methods list.
        source_context = budget_source_context(
            source_context, SOURCE_CTX_METHODS_BUDGET
        )

        source_context_block = ""
        if source_context:
            source_context_block = (
                "\nSource Java Context:\n"
                f"{json.dumps(source_context, indent=2)}\n"
            )

        if framework == "nestjs":
            system_prompt = """You are an expert NestJS and TypeScript developer.
Generate production-ready application services for a Clean Architecture codebase.
Follow these principles:
- Single Responsibility Principle
- Dependency Inversion (depend on interfaces)
- Proper NestJS DI with @Injectable()
- Validation and error handling before business logic
- Clear DTO input/output contracts"""

            user_prompt = f"""Generate a NestJS application service for: {use_case.name}

Description: {use_case.description}

Actors: {', '.join(use_case.actors)}

Steps:
{chr(10).join(f"{i+1}. {step}" for i, step in enumerate(use_case.steps))}

Preconditions:
{chr(10).join(f"- {cond}" for cond in use_case.preconditions)}

Postconditions:
{chr(10).join(f"- {cond}" for cond in use_case.postconditions)}

Related Entities: {', '.join(use_case.entities_involved)}
{source_context_block}
Requirements:
1. Create an @Injectable() service class (NestJS style)
2. Inject repository interfaces in constructor
3. Implement an execute() method with typed DTO input
4. Validate preconditions before business logic
5. Implement each step from the use case description
6. Enforce business rules and handle domain errors
7. Return typed DTO or Result object
8. Include comprehensive JSDoc comments
9. Include a class-level migration note referencing the source Java class from Source Java Context

Generate ONLY the TypeScript code, no explanations."""
        else:
            system_prompt = """You are an expert in Clean Architecture and TypeScript.
Generate production-ready use case classes following these principles:
- Single Responsibility Principle
- Dependency Inversion (depend on interfaces, not implementations)
- Clear separation of concerns
- Proper error handling
- Validation before business logic
- Return Result<T> or proper response DTOs"""

            user_prompt = f"""Generate a use case class for: {use_case.name}

Description: {use_case.description}

Actors: {', '.join(use_case.actors)}

Steps:
{chr(10).join(f"{i+1}. {step}" for i, step in enumerate(use_case.steps))}

Preconditions:
{chr(10).join(f"- {cond}" for cond in use_case.preconditions)}

Postconditions:
{chr(10).join(f"- {cond}" for cond in use_case.postconditions)}

Related Entities: {', '.join(use_case.entities_involved)}
{source_context_block}
Requirements:
1. Create a use case class following Clean Architecture
2. Inject repository dependencies through constructor
3. Implement an execute() method with proper input DTO
4. Validate preconditions before executing business logic
5. Implement each step from the use case description
6. Return a proper response DTO or Result<T>
7. Add comprehensive error handling
8. Include JSDoc comments
9. Use dependency injection (constructor injection)
10. Add a class-level migration note referencing the source Java class from Source Java Context

Generate ONLY the TypeScript code, no explanations."""

        response = self.llm_client.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
        )
        return self._extract_code_from_response(response)

    # ============================================================
    # Controller Generation
    # ============================================================

    def generate_controller(
        self,
        endpoints: List[APIEndpoint],
        controller_name: str,
        framework: str = "express",
        source_context: Optional[Dict] = None,
    ) -> str:
        """
        Generate a controller class that exposes a set of API endpoints.

        NestJS mode: produces an @Controller() class using NestJS decorators (@Get,
        @Post, etc.) with constructor DI and typed DTOs.

        Express/TSOA mode (default): produces a TSOA controller extending Controller
        with @Route, @Tags, @SuccessResponse, and Swagger decorators for automatic
        OpenAPI spec generation.

        Endpoint path and HTTP method semantics are preserved exactly as provided.
        A token budget is applied to source_context to avoid context-window overflow.

        Args:
            endpoints: List of APIEndpoint objects defining the routes to implement
            controller_name: Class name for the generated controller
            framework: Target framework — "nestjs" or "express" (default, uses TSOA)
            source_context: Optional enriched metadata of the originating Java controller,
                used to add a migration note to the class

        Returns:
            Source code string for the generated controller file
        """
        endpoints_info = [
            {
                "method": ep.method,
                "path": ep.path,
                "description": ep.description,
                "business_operation": ep.business_operation,
                "path_parameters": ep.path_parameters,
                "query_parameters": ep.query_parameters,
            }
            for ep in endpoints
        ]

        # Trim supplemental source_context methods; keep all endpoints (every route matters).
        source_context = budget_source_context(
            source_context, SOURCE_CTX_METHODS_BUDGET
        )

        source_context_block = ""
        if source_context:
            source_context_block = (
                "\nSource Java Context:\n"
                f"{json.dumps(source_context, indent=2)}\n"
            )

        if framework == "nestjs":
            system_prompt = """You are an expert NestJS and TypeScript developer.
Generate production-ready NestJS controllers following strict best practices:
- Use @Controller, @Get, @Post, @Put, @Delete from '@nestjs/common'
- Use DTO classes with class-validator decorators
- Use constructor dependency injection
- Keep controller thin and delegate logic to application services
- Include robust error handling and meaningful HTTP exceptions
- Include concise JSDoc comments"""

            user_prompt = f"""Generate a NestJS controller class: {controller_name}

Endpoints to implement:
{json.dumps(endpoints_info, indent=2)}
{source_context_block}
Requirements:
1. Import from '@nestjs/common': Controller, Get, Post, Put, Delete, Param, Body, Query, HttpCode, HttpStatus
2. Create @Controller() class with a clear route prefix
3. Implement one method per endpoint using NestJS decorators
4. Delegate business logic to injected application services/use-cases
5. Use typed DTOs and parameter decorators (@Param, @Body, @Query)
6. Map endpoint intent to appropriate HTTP codes with @HttpCode when needed
7. Keep methods concise and include try/catch only when needed
8. Include JSDoc comments for methods
9. Preserve endpoint path and HTTP method semantics exactly as listed in Endpoints to implement
10. Add a class-level migration note referencing the source Java controller from Source Java Context

Generate ONLY the TypeScript code, no explanations."""
        else:
            system_prompt = """You are an expert TypeScript developer specializing in TSOA (TypeScript OpenAPI) framework.
Generate production-ready TSOA controllers following these strict requirements:
- MUST use TSOA framework (@Route, @Get, @Post, @Put, @Delete decorators from 'tsoa')
- MUST extend Controller class from 'tsoa'
- MUST use @Tags decorator for grouping
- MUST use @Path, @Body, @Query decorators for parameters
- MUST use @SuccessResponse and @Response decorators for documentation
- Use class-validator for DTO validation
- Handle errors gracefully with try-catch
- Use dependency injection via constructor
- Return proper HTTP status codes
- Include comprehensive JSDoc comments"""

            user_prompt = f"""Generate a TSOA controller class: {controller_name}

Endpoints to implement:
{json.dumps(endpoints_info, indent=2)}
{source_context_block}
STRICT Requirements:
1. Import from 'tsoa': Controller, Get, Post, Put, Delete, Route, Tags, Path, Body, Query, SuccessResponse, Response as SwaggerResponse
2. Import from 'express': Request, Response, NextFunction
3. Import class-validator: validateOrReject
4. Create controller class extending Controller
5. Use @Route decorator with base path
6. Use @Tags decorator for API grouping
7. For each endpoint, create a method with:
   - Appropriate HTTP method decorator (@Get, @Post, etc.)
   - @SuccessResponse for success cases
   - @SwaggerResponse for error cases
   - Parameters decorated with @Path, @Body, @Query
   - Express req, res, next parameters
   - Validate DTOs using validateOrReject
   - Try-catch error handling
   - Proper HTTP status codes via res.status()
8. Define inline DTOs/interfaces if needed for request/response types
9. Inject use case interfaces via constructor
10. Include JSDoc comments for all methods
11. Preserve endpoint path and HTTP method semantics exactly as listed in Endpoints to implement
12. Add a class-level migration note referencing the source Java controller from Source Java Context

IMPORTANT: Use ONLY TSOA decorators, do NOT use routing-controllers or any other framework.

Generate ONLY the TypeScript code, no explanations."""

        response = self.llm_client.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.2,
        )
        return self._extract_code_from_response(response)

    # ============================================================
    # DTO Generation
    # ============================================================

    def generate_dto(
        self,
        dto_name: str,
        entity: DomainEntity,
        dto_type: str = "create",
    ) -> str:
        """
        Generate a DTO class with validation decorators for a domain entity.

        Fields and validation decorators are derived from the entity's properties and
        business rules.  CREATE DTOs include all required fields; UPDATE DTOs mark most
        fields as optional; RESPONSE DTOs expose all fields.

        Args:
            dto_name: Class name for the generated DTO
            entity: DomainEntity whose properties and business_rules drive the DTO shape
            dto_type: One of "create", "update", or "response" (default: "create")

        Returns:
            Source code string for the generated DTO file (TypeScript only)
        """
        system_prompt = """You are an expert TypeScript developer.
Generate clean DTO classes with proper validation decorators."""

        user_prompt = f"""Generate a {dto_type.upper()} DTO for: {dto_name}

Based on entity: {entity.name}

Entity properties:
{json.dumps(entity.properties, indent=2)}

Business rules to validate:
{json.dumps(entity.business_rules, indent=2)}

Requirements:
1. Create a DTO class with all necessary properties
2. Add class-validator decorators (@IsString, @IsNotEmpty, @IsOptional, etc.)
3. Add class-transformer decorators if needed (@Type, @Expose, @Exclude)
4. Include JSDoc comments
5. Export the class
6. For UPDATE DTOs, make most fields optional
7. For CREATE DTOs, include all required fields
8. For RESPONSE DTOs, include all fields that should be returned

Generate ONLY the TypeScript code, no explanations."""

        response = self.llm_client.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.2,
        )
        return self._extract_code_from_response(response)

    # ============================================================
    # Utility Methods
    # ============================================================

    def enrich_class_methods(self, class_name: str, methods: List[Dict]) -> List[Dict]:
        """
        Call the LLM once per class to fill in description and complexity
        for each method. Returns the same list with those fields populated.
        """
        if not methods:
            return methods

        method_list = [
            {"name": m["name"], "signature": m["signature"]}
            for m in methods
        ]

        user_prompt = f"""You are analyzing Java class: {class_name}

For each method below, provide a short description (one sentence) and a complexity estimate (Low, Medium, or High).

Methods:
{json.dumps(method_list, indent=2)}

Reply ONLY with a JSON array in this exact format, no extra text:
[
  {{
    "name": "methodName",
    "description": "What this method does in one sentence",
    "complexity": "Low"
  }}
]"""

        try:
            response = self.llm_client.generate(
                prompt=user_prompt,
                system_prompt="You are a Java code analyst. Reply only with valid JSON.",
                temperature=0.1,
            )
            # Strip markdown fences if present
            raw = response.strip()
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.split("```")[0].strip()

            enriched = json.loads(raw)
            enriched_by_name = {e["name"]: e for e in enriched}

            return [
                {
                    **m,
                    "description": enriched_by_name.get(m["name"], {}).get("description", ""),
                    "complexity": enriched_by_name.get(m["name"], {}).get("complexity", ""),
                }
                for m in methods
            ]
        except Exception:
            return methods

    def _extract_code_from_response(self, response: str) -> str:
        """
        Strip markdown code fences from an LLM response and return bare source code.

        Tries language-specific fences (```typescript, ```ts, ```javascript, ```js)
        first, then falls back to a generic ``` fence, and finally returns the full
        response unchanged if no fences are found.

        Args:
            response: Raw LLM response string, possibly wrapped in a markdown code block

        Returns:
            Trimmed source code string with no surrounding markdown
        """
        if "```typescript" in response:
            code = response.split("```typescript")[1].split("```")[0]
        elif "```ts" in response:
            code = response.split("```ts")[1].split("```")[0]
        elif "```javascript" in response:
            code = response.split("```javascript")[1].split("```")[0]
        elif "```js" in response:
            code = response.split("```js")[1].split("```")[0]
        elif "```" in response:
            code = response.split("```")[1].split("```")[0]
        else:
            code = response
        return code.strip()

    def generate_service_layer(
        self,
        service_name: str,
        methods_info: List[Dict],
        framework: str = "express",
        source_context: Optional[Dict] = None,
        orm: str = "typeorm",
    ) -> str:
        """
        Generate a single consolidated service file containing all business logic methods.

        A token budget is applied to methods_info before serialisation: high-complexity
        and non-accessor methods are prioritised; simple getters/setters are dropped first
        if the total would exceed METHODS_TOKEN_BUDGET.  A warning is logged if trimming
        occurs.  The same budget logic is applied to source_context.

        NestJS mode: produces an @Injectable() service class.
        Express/default mode: produces a plain service class with constructor DI.

        Args:
            service_name: Class name for the generated service (e.g., "CustomerService")
            methods_info: List of method dicts with keys "name", "signature",
                "description", and "complexity"
            framework: Target framework — "nestjs" or "express" (default)
            source_context: Optional enriched metadata of the originating Java service
                class, used to add a migration note to the generated class
            orm: ORM hint passed through (currently unused but reserved for future use)

        Returns:
            Source code string for the generated service file
        """
        # --- token-budget management ---
        # Trim methods_info before serialisation so that high-complexity / non-trivial
        # methods are always included and simple accessors are dropped first if needed.
        original_count = len(methods_info)
        methods_info, trimmed = budget_methods(
            methods_info, METHODS_TOKEN_BUDGET
        )
        if trimmed:
            logger.warning(
                "generate_service_layer(%s): methods_info reduced from %d → %d methods "
                "(accessors and low-complexity methods dropped first to stay within "
                "token budget).",
                service_name,
                original_count,
                len(methods_info),
            )

        # Also trim the supplemental source_context methods list.
        source_context = budget_source_context(
            source_context, SOURCE_CTX_METHODS_BUDGET
        )

        source_context_block = ""
        if source_context:
            source_context_block = (
                "\nSource Java Context:\n"
                f"{json.dumps(source_context, indent=2)}\n"
            )

        if framework == "nestjs":
            system_prompt = f"""You are an expert NestJS and {self.language_label} developer.
Generate a single production-ready service class containing ALL business logic methods."""

            user_prompt = f"""Generate a NestJS @Injectable() service class: {service_name}

Methods to implement:
{json.dumps(methods_info, indent=2)}
{source_context_block}
Requirements:
1. Single @Injectable() service class with ALL methods listed above
2. Inject repository/dependencies via constructor
3. Each method handles its own validation and error handling
4. Use async/await throughout
5. Include JSDoc for the class only

{self._get_code_instruction()}"""
        else:
            system_prompt = f"""You are an expert {self.language_label} developer.
Generate a single production-ready service class containing ALL business logic methods."""

            user_prompt = f"""Generate a service class: {service_name}

Methods to implement:
{json.dumps(methods_info, indent=2)}
{source_context_block}
Requirements:
1. Single service class with ALL methods listed above
2. Inject repository/dependencies via constructor
3. Each method handles its own validation and error handling
4. Use async/await throughout
5. {"Export using module.exports" if self.language == "javascript" else "Export the class"}
6. Include JSDoc for the class only

{self._get_code_instruction()}"""

        response = self.llm_client.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.2,
        )
        return self._extract_code_from_response(response)

    def generate_repository_layer(
        self,
        entity: DomainEntity,
        orm: str = "typeorm",
    ) -> str:
        """
        Generate a single consolidated repository file with all CRUD and query methods.

        The generated class (or object in JavaScript mode) includes findById, findAll,
        create, update, delete, and any domain-relevant query methods derived from the
        entity's properties.  All methods use async/await with try-catch error handling.

        Args:
            entity: DomainEntity whose properties drive query method generation
            orm: ORM to use — "typeorm" (default) or "sequelize"

        Returns:
            Source code string for the generated repository file
        """
        if orm == "sequelize":
            orm_label = "Sequelize"
            orm_import = "sequelize" if self.language == "javascript" else "sequelize-typescript"
        else:
            orm_label = "TypeORM"
            orm_import = "typeorm"

        if self.language == "javascript":
            system_prompt = f"""You are an expert {orm_label} developer in JavaScript.
Generate a single repository file with all CRUD and query methods for an entity."""

            user_prompt = f"""Generate a {orm_label} repository for: {entity.name}

Properties:
{json.dumps(entity.properties, indent=2)}

Requirements:
1. Single repository class/object with findById, findAll, create, update, delete and any relevant query methods
2. Use {orm_label} APIs ({orm_import})
3. All methods use async/await with try-catch
4. Export using module.exports

{self._get_code_instruction()}"""
        else:
            system_prompt = f"""You are an expert {orm_label} developer in TypeScript.
Generate a single repository file with all CRUD and query methods for an entity."""

            user_prompt = f"""Generate a {orm_label} repository for: {entity.name}

Properties:
{json.dumps(entity.properties, indent=2)}

Requirements:
1. Single repository class with findById, findAll, create, update, delete and any relevant query methods
2. Use {orm_label} ({orm_import})
3. All methods use async/await with proper types
4. Export the class

{self._get_code_instruction()}"""

        response = self.llm_client.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.2,
        )
        return self._extract_code_from_response(response)
