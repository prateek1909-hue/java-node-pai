"""
LangGraph workflow nodes for Java-to-Node.js conversion.

Each node is a function that takes the state, performs an operation,
and returns an updated state.
"""

import logging
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from rich.console import Console

from src.graph.state import ConversionState
from src.analyzers.project_analyzer import ProjectAnalyzer
from src.analyzers.class_categorizer import ClassCategorizer
from src.analyzers.dependency_mapper import DependencyMapper
from src.models.domain_models import DomainEntity, DomainEntityType, APIEndpoint, UseCase
from src.config.settings import Settings

# Initialize logger and console
logger = logging.getLogger(__name__)
console = Console()


# ============================================================
# Source-class selection helpers
# ============================================================

def _is_test_class(java_class) -> bool:
    """
    Return True when a class appears to be a test class.

    Checks the file path, class name, and package for common test indicators
    ("test" substring, *Test/*Tests suffix, *.test.* package segment).

    Args:
        java_class: JavaClass object to inspect

    Returns:
        True if the class is likely a test class, False otherwise
    """
    file_path = (java_class.file_path or "").lower()
    class_name = (java_class.name or "").lower()
    package = (java_class.package or "").lower()
    return (
        "test" in file_path
        or class_name.endswith("test")
        or class_name.endswith("tests")
        or ".test" in package
    )


def _role_fit_score(role: str, java_class) -> int:
    """
    Compute a numeric fit score indicating how well a class matches a given role.

    Higher scores indicate a better match. Used to deterministically rank candidates
    when multiple classes share the same category, avoiding random or alphabetical ties.

    Scoring contributions:
    - +3 for concrete classes (vs. interfaces)
    - +20 for a role-specific Spring annotation (e.g., @RestController for "controller")
    - +10/+8/+12 for role keywords in the class name, package, or file path

    Args:
        role: Target role — "controller", "service", or "dao"
        java_class: JavaClass object to score

    Returns:
        Integer fit score; higher is a better match for the role
    """
    name = (java_class.name or "").lower()
    path = (java_class.file_path or "").lower()
    package = (java_class.package or "").lower()

    score = 0

    if java_class.type == "class":
        score += 3

    if role == "controller":
        if java_class.has_annotation("RestController") or java_class.has_annotation("Controller"):
            score += 20
        if "controller" in name or "controller" in package or "controller" in path:
            score += 10

    if role == "service":
        if java_class.has_annotation("Service"):
            score += 20
        if "service" in name or "service" in package or "service" in path:
            score += 10
        if "dto" in name or "dto" in package or "assembler" in name:
            score -= 10

    if role == "dao":
        if java_class.has_annotation("Repository"):
            score += 20
        if "repository" in name or "dao" in name:
            score += 12
        if "repository" in package or "repository" in path or "dao" in package:
            score += 8

    return score


def _pick_preferred_class(candidates: List, role: str) -> Optional[Any]:
    """
    Pick the best-matching candidate class for a given role from a list of options.

    Ranking criteria (lexicographic, lower is better):
    1. Test classes are ranked last (is_test_class=True → deprioritised)
    2. Higher role fit score is preferred
    3. More methods is preferred (richer implementation beats stubs)
    4. More fields is preferred
    5. Alphabetical class name as a final tiebreaker for reproducibility

    Args:
        candidates: List of JavaClass objects to evaluate
        role: Target role — "controller", "service", or "dao"

    Returns:
        The best-matching JavaClass, or None if candidates is empty
    """
    if not candidates:
        return None

    ranked = sorted(
        candidates,
        key=lambda cls: (
            _is_test_class(cls),
            -_role_fit_score(role, cls),
            -len(cls.methods),
            -len(cls.fields),
            cls.name,
        ),
    )
    return ranked[0]


def _select_source_classes_from_paths(
    all_java_classes: List, selected_file_paths: List[str]
) -> Dict[str, Any]:
    """
    Build the selected-source-classes dict by matching user-chosen file paths
    against scanned JavaClass objects.

    Roles are assigned by category: Controller → 'controller', Service → 'service',
    DAO/Repository → 'dao'.  When the user picks multiple files of the same role,
    the first one wins.
    """
    # Normalise paths so Windows back-slashes don't break comparison
    norm_selected = {Path(p).resolve().as_posix() for p in selected_file_paths}

    role_map: Dict[str, Any] = {}
    for cls in all_java_classes:
        norm_cls_path = Path(cls.file_path).resolve().as_posix()
        if norm_cls_path not in norm_selected:
            continue
        category = (cls.category or "").lower()
        if "controller" in category and "controller" not in role_map:
            role_map["controller"] = cls
        elif "service" in category and "service" not in role_map:
            role_map["service"] = cls
        elif category in ("dao", "repository") and "dao" not in role_map:
            role_map["dao"] = cls
        elif "repository" in category and "dao" not in role_map:
            role_map["dao"] = cls

    names = {role: cls.name for role, cls in role_map.items()}
    files = {role: cls.file_path for role, cls in role_map.items()}
    details = {
        role: {
            "name": cls.name,
            "package": cls.package,
            "category": cls.category,
            "file_path": cls.file_path,
            "method_count": len(cls.methods),
            "field_count": len(cls.fields),
            "methods": [
                {
                    "name": method.name,
                    "signature": method.signature,
                    "description": method.description or "",
                    "complexity": method.complexity or "",
                }
                for method in cls.methods[:20]
            ],
        }
        for role, cls in role_map.items()
    }
    return {"names": names, "files": files, "details": details}


def _select_source_classes(classes_by_category: Dict[str, List]) -> Dict[str, Any]:
    """
    Automatically select one representative class for each of the three workflow roles.

    Used when the user has not specified files via the UI.  Combines DAO and Repository
    categories as candidates for the "dao" role.  Returns dicts keyed by role name so
    that downstream nodes can access names, file paths, and enriched method details.

    Args:
        classes_by_category: Dict mapping category name → list of JavaClass objects,
            as produced by the categorize_classes workflow node

    Returns:
        Dict with keys "names" (role → class name), "files" (role → file path), and
        "details" (role → metadata dict with method list)
    """
    controller = _pick_preferred_class(classes_by_category.get("Controller", []), "controller")
    service = _pick_preferred_class(classes_by_category.get("Service", []), "service")

    dao_candidates = list(classes_by_category.get("DAO", []))
    repository_candidates = classes_by_category.get("Repository", [])
    if repository_candidates:
        dao_candidates.extend(repository_candidates)
    dao = _pick_preferred_class(dao_candidates, "dao")

    selected = {
        "controller": controller,
        "service": service,
        "dao": dao,
    }

    names = {
        role: cls.name
        for role, cls in selected.items()
        if cls is not None
    }
    files = {
        role: cls.file_path
        for role, cls in selected.items()
        if cls is not None
    }
    details = {
        role: {
            "name": cls.name,
            "package": cls.package,
            "category": cls.category,
            "file_path": cls.file_path,
            "method_count": len(cls.methods),
            "field_count": len(cls.fields),
            "methods": [
                {
                    "name": method.name,
                    "signature": method.signature,
                    "description": method.description or "",
                    "complexity": method.complexity or "",
                }
                for method in cls.methods[:20]
            ],
        }
        for role, cls in selected.items()
        if cls is not None
    }

    return {
        "names": names,
        "files": files,
        "details": details,
    }


def _get_role_source_context(state: ConversionState, role: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve the enriched source-class metadata dict for a given workflow role.

    The metadata dict was populated during the categorize_classes step and contains
    the class name, package, method list (with LLM-enriched descriptions), and
    other details used as context when prompting the LLM for code generation.

    Args:
        state: Current workflow state
        role: One of "controller", "service", or "dao"

    Returns:
        The metadata dict for the selected class, or None if no class was selected for
        the given role
    """
    details = state.get("selected_source_class_details", {}) or {}
    return details.get(role)


def _build_conversion_traceability(
    state: ConversionState,
    generated_files: Dict[str, str],
    endpoints_by_resource: Optional[Dict[str, List]] = None,
) -> Dict[str, Any]:
    """
    Build a traceability manifest that links each selected Java source class to its
    generated Node.js artifacts.

    The manifest is written to analysis/conversion_traceability.json and is useful
    for auditing which Java classes were the basis for each generated controller,
    use case, and repository file.

    Args:
        state: Current workflow state containing selected_source_class_details
        generated_files: Map of generated file paths to their contents
        endpoints_by_resource: Optional map of resource name → APIEndpoint list
            used to record which endpoints were generated for each controller

    Returns:
        Dict with keys: "selected_source_classes", "generated_artifacts",
        "controller_endpoint_groups"
    """
    selected = state.get("selected_source_class_details", {}) or {}

    controller_files = sorted(
        path for path in generated_files.keys() if "/presentation/controllers/" in path
    )
    use_case_files = sorted(
        path for path in generated_files.keys() if "/application/use-cases/" in path
    )
    repository_files = sorted(
        path for path in generated_files.keys() if "/infrastructure/repositories/" in path
    )

    return {
        "selected_source_classes": selected,
        "generated_artifacts": {
            "controllers": controller_files,
            "use_cases": use_case_files,
            "repositories": repository_files,
        },
        "controller_endpoint_groups": {
            resource: [
                {"method": ep.method, "path": ep.path}
                for ep in endpoints
            ]
            for resource, endpoints in (endpoints_by_resource or {}).items()
        },
    }


# ============================================================
# Domain model builders (deterministic, no LLM)
# ============================================================

def _java_class_to_domain_entity(java_class) -> DomainEntity:
    """
    Convert a Java entity class to a DomainEntity model suitable for LLM code generation.

    Iterates over the class's fields (skipping @Transient ones) and maps each to a
    property dict that includes name, Java type, and any derived constraints
    (@NotNull/@NotEmpty → "required"; @Id → "primary_key").

    Args:
        java_class: JavaClass object categorised as "Entity"

    Returns:
        DomainEntity with properties populated from fields; business_rules and
        relationships are left empty and can be enriched downstream
    """
    properties = []
    for field in java_class.fields:
        if field.has_annotation("Transient"):
            continue
        constraints_parts = []
        if field.has_annotation("NotNull") or field.has_annotation("NotEmpty"):
            constraints_parts.append("required")
        if field.has_annotation("Id"):
            constraints_parts.append("primary_key")
        properties.append({
            "name": field.name,
            "type": field.type,
            "constraints": ", ".join(constraints_parts),
        })

    return DomainEntity(
        name=java_class.name,
        type=DomainEntityType.ENTITY,
        properties=properties,
        business_rules=[],
        relationships=[],
    )


_ANNOTATION_TO_HTTP = {
    "GetMapping": "GET",
    "PostMapping": "POST",
    "PutMapping": "PUT",
    "DeleteMapping": "DELETE",
    "PatchMapping": "PATCH",
}


def _extract_mapping_path(annotation_args: str, class_base_path: str = "") -> str:
    """
    Extract the URL path from a Spring mapping annotation's argument string.

    Handles both positional ('"/owners"') and named ('value="/owners/{id}"') forms.
    Prepends the class-level base path when provided.

    Args:
        annotation_args: Raw annotation argument string (e.g., '"/owners/{id}"')
        class_base_path: Optional base path from a class-level @RequestMapping

    Returns:
        Fully-qualified path string (e.g., "/owners/{id}"), or just the base path
        if no path literal is found, or "/" if both are empty
    """
    match = re.search(r'"(/[^"]*)"', annotation_args)
    if match:
        path = match.group(1)
    else:
        path = ""
    base = class_base_path.rstrip("/")
    return base + path if path else base or "/"


def _get_class_base_path(java_class) -> str:
    """
    Extract the base URL path from a controller's class-level @RequestMapping annotation.

    Args:
        java_class: JavaClass object (typically a Controller)

    Returns:
        Base path string (e.g., "/api/owners"), or empty string if no @RequestMapping
        annotation is present at the class level
    """
    for ann in java_class.annotations:
        if ann.name == "RequestMapping":
            return _extract_mapping_path(ann.arguments)
    return ""


_METHOD_NAME_TO_HTTP = {
    "get": "GET", "find": "GET", "fetch": "GET", "list": "GET", "search": "GET", "read": "GET",
    "add": "POST", "create": "POST", "save": "POST", "register": "POST",
    "update": "PUT", "edit": "PUT", "modify": "PUT",
    "patch": "PATCH",
    "delete": "DELETE", "remove": "DELETE",
}


def _infer_http_method(method_name: str) -> str:
    """
    Infer the HTTP method for a Java method based on its name prefix.

    Used as a fallback when Spring mapping annotations are not present or not
    parseable.  Checks known verb prefixes (get/find/fetch → GET,
    add/create/save → POST, update/edit → PUT, patch → PATCH, delete/remove → DELETE).

    Args:
        method_name: The Java method name (e.g., "findCustomerById")

    Returns:
        HTTP method string (e.g., "GET"); defaults to "GET" when no prefix matches
    """
    lower = method_name.lower()
    for prefix, http in _METHOD_NAME_TO_HTTP.items():
        if lower.startswith(prefix):
            return http
    return "GET"


def _java_class_to_api_endpoints(java_class) -> List[APIEndpoint]:
    """
    Build a list of APIEndpoint objects from a Java controller class.

    Primary path: iterates over methods that have Spring HTTP-mapping annotations
    (@GetMapping, @PostMapping, etc.) and extracts path, HTTP method, and parameter
    metadata (@PathVariable and @RequestParam parameters).

    Fallback: if no annotated endpoints are found, derives endpoints from the first
    15 public methods using name-based HTTP method inference and a /{id} suffix
    heuristic for methods with ID-like parameters.

    Args:
        java_class: JavaClass object categorised as "Controller"

    Returns:
        List of APIEndpoint objects; at most one endpoint is emitted per Java method
        (the first matching HTTP-mapping annotation wins)
    """
    base_path = _get_class_base_path(java_class)
    endpoints = []

    for method in java_class.get_rest_endpoints():
        for ann in method.annotations:
            http_method = _ANNOTATION_TO_HTTP.get(ann.name)
            if not http_method:
                if ann.name == "RequestMapping":
                    m = re.search(r'method\s*=\s*RequestMethod\.(\w+)', ann.arguments)
                    http_method = m.group(1) if m else "GET"
                else:
                    continue

            path = _extract_mapping_path(ann.arguments, base_path)

            path_params = [
                {"name": p.name, "type": p.type, "description": ""}
                for p in method.parameters
                if p.has_annotation("PathVariable")
            ]
            query_params = [
                {"name": p.name, "type": p.type, "description": ""}
                for p in method.parameters
                if p.has_annotation("RequestParam")
            ]

            endpoints.append(APIEndpoint(
                path=path,
                method=http_method,
                description=f"{method.name} in {java_class.name}",
                business_operation=method.name,
                path_parameters=path_params,
                query_parameters=query_params,
            ))
            break  # one HTTP method per Java method

    # Fallback: if no endpoints from annotations, derive from public method names
    if not endpoints:
        resource = re.sub(r'Controller$', '', java_class.name, flags=re.IGNORECASE).lower()
        base = base_path or f"/{resource}"
        for method in java_class.get_public_methods()[:15]:
            http_method = _infer_http_method(method.name)
            has_id_param = any(
                "id" in p.name.lower() or "Id" in p.name
                for p in method.parameters
            )
            path = base + ("/{id}" if has_id_param else "")
            path_params = [
                {"name": p.name, "type": p.type, "description": ""}
                for p in method.parameters
                if "id" in p.name.lower()
            ]
            endpoints.append(APIEndpoint(
                path=path,
                method=http_method,
                description=f"{method.name} in {java_class.name}",
                business_operation=method.name,
                path_parameters=path_params,
                query_parameters=[],
            ))

    return endpoints


def _java_class_to_use_cases(java_class) -> List[UseCase]:
    """
    Derive a list of UseCase objects from a Java service class's public methods.

    Each public method (up to 15) becomes its own use case.  The use-case name is a
    human-readable title derived by splitting the camelCase method name, and the
    description is the full method signature.

    Args:
        java_class: JavaClass object categorised as "Service"

    Returns:
        List of UseCase objects — one per public method
    """
    use_cases = []
    for method in java_class.get_public_methods()[:15]:
        # Convert camelCase → human-readable title
        human_name = re.sub(r'([A-Z])', r' \1', method.name).strip().title()
        params = [f"{p.type} {p.name}" for p in method.parameters]
        use_cases.append(UseCase(
            name=human_name,
            description=f"{method.return_type} {method.name}({', '.join(params)})",
            actors=["User"],
            steps=[f"Call {method.name} on {java_class.name}"],
            entities_involved=[],
        ))
    return use_cases


def _find_matching_entity(entity_classes, selected_names):
    """
    Find the entity class that best matches the selected DAO, service, or controller name.

    Strips common Java role suffixes (Repository, Service, Controller, Impl, etc.) from
    each selected class name to obtain a "core domain name", then looks for an entity
    whose name (after stripping an "Entity" suffix) matches that core name.

    Matching priority:
    1. Exact case-insensitive match on core name
    2. Substring containment (either direction)
    3. Falls back to the first entity class if no match is found

    Args:
        entity_classes: List of JavaClass objects categorised as "Entity"
        selected_names: Dict of role → class name (e.g., {"dao": "CustomerRepository"})

    Returns:
        The best-matching JavaClass, or None if entity_classes is empty
    """
    for role in ["dao", "service", "controller"]:
        base_name = selected_names.get(role, "")
        if not base_name:
            continue
        # Strip common Java suffixes to get the core domain name
        clean = re.sub(
            r'(Repository|RepositoryImpl|JpaRepository|Service|ServiceImpl|DAO|DaoImpl|Controller|Impl)$',
            '',
            base_name,
            flags=re.IGNORECASE,
        ).strip()
        if not clean:
            continue
        for entity in entity_classes:
            entity_base = re.sub(r'Entity$', '', entity.name, flags=re.IGNORECASE)
            if entity_base.lower() == clean.lower() or entity.name.lower() == clean.lower():
                return entity
        # Looser: contains match
        for entity in entity_classes:
            entity_base = re.sub(r'Entity$', '', entity.name, flags=re.IGNORECASE).lower()
            if clean.lower() in entity_base or entity_base in clean.lower():
                return entity
    return entity_classes[0] if entity_classes else None


# ============================================================
# PHASE 1: Repository & Scanning Nodes
# ============================================================


def scan_codebase(state: ConversionState) -> ConversionState:
    """
    Scan the Java codebase and parse all Java files.

    Updates state with:
    - java_files: List of found Java file paths
    - java_classes: Parsed JavaClass objects
    - total_files, parsed_files, parse_errors
    """
    state["current_step"] = "scan_codebase"

    try:
        repo_path = state["repo_path"]
        verbose = state.get("verbose", False)

        if verbose:
            console.print(f"\n[bold cyan]Scanning codebase:[/bold cyan] {repo_path}\n")

        analyzer = ProjectAnalyzer(repo_path)
        analysis = analyzer.analyze(verbose=verbose)

        state["java_classes"] = analysis.java_classes
        state["total_files"] = len(analysis.java_classes)
        state["parsed_files"] = len(analysis.java_classes)

        if verbose:
            console.print(f"[green]✓ Successfully parsed {len(analysis.java_classes)} Java classes[/green]\n")

        return state

    except Exception as e:
        error_msg = f"Failed to scan codebase: {str(e)}"
        logger.error(error_msg, exc_info=True)
        state["errors"].append({
            "step": "scan_codebase",
            "error": error_msg,
            "exception": str(e)
        })
        return state


def categorize_classes(state: ConversionState) -> ConversionState:
    """
    Categorize Java classes by type (Controller, Service, Entity, etc.).

    Updates state with:
    - classes_by_category: Dict mapping category -> list of classes
    """
    state["current_step"] = "categorize_classes"

    try:
        java_classes = state.get("java_classes", [])
        verbose = state.get("verbose", False)

        if verbose:
            console.print(f"\n[bold cyan]Categorizing classes...[/bold cyan]\n")

        categorizer = ClassCategorizer()
        categories = {}

        for java_class in java_classes:
            category = categorizer.categorize(java_class)
            if category not in categories:
                categories[category] = []
            categories[category].append(java_class)

        state["classes_by_category"] = categories

        # Use the UI-selected file paths when provided; otherwise fall back to auto-selection.
        user_paths = state.get("selected_file_paths") or []
        if user_paths:
            selected = _select_source_classes_from_paths(java_classes, user_paths)
        else:
            selected = _select_source_classes(categories)

        # Enrich method descriptions and complexity via LLM for each selected class
        from src.generators.llm_code_creator import LLMCodeGenerator
        from src.config.settings import Settings as _Settings
        _generator = LLMCodeGenerator(_Settings())
        enriched_details = {}
        for role, info in selected["details"].items():
            if verbose:
                console.print(f"  [cyan]→ Enriching methods for {info['name']}...[/cyan]")
            enriched_methods = _generator.enrich_class_methods(info["name"], info["methods"])
            enriched_details[role] = {**info, "methods": enriched_methods}

        state["selected_source_classes"] = selected["names"]
        state["selected_source_class_files"] = selected["files"]
        state["selected_source_class_details"] = enriched_details

        state["generated_files"] = state.get("generated_files", {})
        state["generated_files"]["analysis/selected_source_classes.json"] = json.dumps(
            enriched_details,
            indent=2,
        )

        if len(selected["names"]) < 3:
            missing = [
                role
                for role in ["controller", "service", "dao"]
                if role not in selected["names"]
            ]
            state["warnings"].append(
                "Missing source-class selections for roles: " + ", ".join(missing)
            )

        if verbose:
            console.print("[green]✓ Classes categorized:[/green]")
            for category, classes in categories.items():
                console.print(f"  • {category}: {len(classes)} classes")

            if selected["details"]:
                console.print("\n[green]✓ Selected source classes:[/green]")
                for role in ["controller", "service", "dao"]:
                    info = selected["details"].get(role)
                    if info:
                        console.print(
                            f"  • {role}: {info['name']} ({info['category']}) [{info['method_count']} methods]"
                        )
            console.print()

        return state

    except Exception as e:
        error_msg = f"Failed to categorize classes: {str(e)}"
        logger.error(error_msg, exc_info=True)
        state["errors"].append({
            "step": "categorize_classes",
            "error": error_msg,
            "exception": str(e)
        })
        return state


def analyze_dependencies(state: ConversionState) -> ConversionState:
    """
    Analyze dependencies between Java classes.

    Updates state with:
    - dependency_graph: Dict mapping class -> list of dependencies
    - circular_dependencies: List of circular dependency chains
    """
    state["current_step"] = "analyze_dependencies"

    try:
        java_classes = state.get("java_classes", [])
        verbose = state.get("verbose", False)

        if verbose:
            console.print(f"\n[bold cyan]Analyzing dependencies...[/bold cyan]\n")

        mapper = DependencyMapper(java_classes)
        dependency_graph_obj = mapper.map_dependencies()

        dependency_graph = {}
        for dep in dependency_graph_obj.dependencies:
            if dep.from_class not in dependency_graph:
                dependency_graph[dep.from_class] = []
            dependency_graph[dep.from_class].append(dep.to_class)

        state["dependency_graph"] = dependency_graph
        state["circular_dependencies"] = []

        if verbose:
            total_deps = sum(len(deps) for deps in dependency_graph.values())
            console.print(f"[green]✓ Found {total_deps} dependencies[/green]")
            console.print()

        return state

    except Exception as e:
        error_msg = f"Failed to analyze dependencies: {str(e)}"
        logger.error(error_msg, exc_info=True)
        state["errors"].append({
            "step": "analyze_dependencies",
            "error": error_msg,
            "exception": str(e)
        })
        return state


# ============================================================
# PHASE 2: Architecture Design
# ============================================================


def design_architecture(state: ConversionState) -> ConversionState:
    """
    Design the target Node.js architecture.

    Updates state with:
    - architecture: ModernArchitecture object
    """
    state["current_step"] = "design_architecture"

    try:
        target_framework = state.get("target_framework", "express")
        target_orm = state.get("target_orm", "typeorm")
        settings = Settings()
        target_language = "JavaScript" if settings.language == "javascript" else "TypeScript"
        verbose = state.get("verbose", False)

        if verbose:
            console.print(f"\n[bold cyan]Designing architecture...[/bold cyan]\n")

        from src.models.architecture_models import (
            ModernArchitecture,
            ArchitecturePattern,
            TechStack,
            LayerDefinition,
        )

        architecture = ModernArchitecture(
            pattern=ArchitecturePattern.CLEAN_ARCHITECTURE,
            rationale="Clean Architecture with clear separation of concerns",
            tech_stack=TechStack(
                runtime="Node.js",
                language=target_language,
                framework=target_framework,
                orm=target_orm,
                testing_framework="jest",
                validation_library="class-validator",
                di_container="tsyringe" if target_framework == "express" else "built-in",
            ),
            layers=[
                LayerDefinition(name="domain", purpose="Core business logic and entities", dependencies=[]),
                LayerDefinition(name="application", purpose="Use cases and application services", dependencies=["domain"]),
                LayerDefinition(name="infrastructure", purpose="External services, database, etc.", dependencies=["domain"]),
                LayerDefinition(name="presentation", purpose="API controllers and routes", dependencies=["application", "domain"]),
            ],
            modules=[],
            folder_structure={},
        )

        state["architecture"] = architecture

        if verbose:
            console.print(f"[green]✓ Architecture designed:[/green]")
            console.print(f"  • Pattern: {architecture.pattern.value}")
            console.print(f"  • Framework: {architecture.tech_stack.framework}")
            console.print(f"  • ORM: {architecture.tech_stack.orm}")
            console.print()

        return state

    except Exception as e:
        error_msg = f"Failed to design architecture: {str(e)}"
        logger.error(error_msg, exc_info=True)
        state["errors"].append({
            "step": "design_architecture",
            "error": error_msg,
            "exception": str(e)
        })
        return state


# ============================================================
# PHASE 3: Code Generation Nodes
# ============================================================


def generate_domain_layer(state: ConversionState) -> ConversionState:
    """
    Generate domain layer code using LLM (entities, repositories, DTOs).

    Updates state with:
    - generated_files: Adds domain layer files
    """
    state["current_step"] = "generate_domain_layer"

    try:
        architecture = state.get("architecture")
        target_orm = state.get("target_orm", "typeorm")
        verbose = state.get("verbose", False)
        java_classes = state.get("java_classes", [])

        if verbose:
            console.print(f"\n[bold cyan]Generating domain layer with LLM...[/bold cyan]\n")

        if not architecture:
            raise ValueError("Architecture not found in state")

        entity_classes = [c for c in java_classes if c.category == "Entity"]
        if not entity_classes:
            if verbose:
                console.print("[yellow]⚠ No entity classes found, skipping domain layer[/yellow]\n")
            return state

        # Only generate for the ONE entity that matches the selected DAO/service
        selected_names = state.get("selected_source_classes", {})
        java_class = _find_matching_entity(entity_classes, selected_names)
        if java_class is None:
            if verbose:
                console.print("[yellow]⚠ Could not match entity, skipping domain layer[/yellow]\n")
            return state

        from src.generators.llm_code_creator import LLMCodeGenerator
        settings = Settings()
        generator = LLMCodeGenerator(settings)
        generated_files = state.get("generated_files", {})

        entity = _java_class_to_domain_entity(java_class)

        if verbose:
            console.print(f"  [cyan]→ Generating entity model: {entity.name}...[/cyan]")

        entity_code = generator.generate_entity(entity)
        generated_files[f"src/domain/entities/{entity.name.lower()}.entity{generator.file_ext}"] = entity_code

        repo_code = generator.generate_repository_layer(entity=entity, orm=target_orm)
        generated_files[f"src/infrastructure/repositories/{entity.name.lower()}.repository{generator.file_ext}"] = repo_code

        if verbose:
            console.print(f"  [green]✓ Generated entity model and repository for {entity.name}[/green]")

        state["generated_files"] = generated_files

        if verbose:
            console.print(f"\n[green]✓ Generated domain layer: {len(generated_files)} files total[/green]\n")

        return state

    except Exception as e:
        error_msg = f"Failed to generate domain layer: {str(e)}"
        logger.error(error_msg, exc_info=True)
        state["errors"].append({
            "step": "generate_domain_layer",
            "error": error_msg,
            "exception": str(e)
        })
        return state


def generate_application_layer(state: ConversionState) -> ConversionState:
    """
    Generate application layer code using LLM (use cases).

    Updates state with:
    - generated_files: Adds application layer files
    """
    state["current_step"] = "generate_application_layer"

    try:
        target_framework = state.get("target_framework", "express")
        verbose = state.get("verbose", False)
        classes_by_category = state.get("classes_by_category", {})

        if verbose:
            console.print(f"\n[bold cyan]Generating application layer with LLM...[/bold cyan]\n")

        all_service_classes = classes_by_category.get("Service", [])
        if not all_service_classes:
            if verbose:
                console.print("[yellow]⚠ No service classes found, skipping application layer[/yellow]\n")
            return state

        # Only use the selected service class, not all services
        selected_service_name = state.get("selected_source_classes", {}).get("service")
        service_classes = [c for c in all_service_classes if c.name == selected_service_name]
        if not service_classes:
            service_classes = all_service_classes[:1]  # Fallback to first service

        from src.generators.llm_code_creator import LLMCodeGenerator
        settings = Settings()
        generator = LLMCodeGenerator(settings)
        file_ext = ".js" if settings.language == "javascript" else ".ts"

        generated_files = state.get("generated_files", {})

        raw_service_name = service_classes[0].name if service_classes else "Service"
        service_name = re.sub(r'(ServiceImpl|Impl)$', '', raw_service_name, flags=re.IGNORECASE) + "Service"

        # Build methods info directly from Java methods preserving original names/signatures
        methods_info = []
        for svc in service_classes:
            for method in svc.get_public_methods()[:15]:
                params = [f"{p.type} {p.name}" for p in method.parameters]
                signature = method.signature or (
                    f"{' '.join(method.modifiers)} {method.return_type} {method.name}({', '.join(params)})"
                )
                methods_info.append({
                    "name": method.name,
                    "signature": signature,
                    "description": method.description or f"Executes {method.name}",
                    "complexity": method.complexity or "Medium",
                })

        if verbose:
            console.print(f"  [cyan]→ Generating service: {service_name} ({len(methods_info)} methods)...[/cyan]")

        try:
            source_context = _get_role_source_context(state, "service")
            service_code = generator.generate_service_layer(
                service_name=service_name,
                methods_info=methods_info,
                framework=target_framework,
                source_context=source_context,
            )
            resource = re.sub(r'Service$', '', service_name, flags=re.IGNORECASE).lower()
            file_path = f"src/application/services/{resource}.service{file_ext}"
            generated_files[file_path] = service_code

            if verbose:
                console.print(f"  [green]✓ Generated {service_name}[/green]")

        except Exception as e:
            if verbose:
                console.print(f"  [yellow]⚠ Failed to generate service: {str(e)}[/yellow]")
            logger.warning(f"Failed to generate service {service_name}: {e}")

        state["generated_files"] = generated_files

        if verbose:
            console.print(f"\n[green]✓ Generated application layer: 1 service file[/green]\n")

        return state

    except Exception as e:
        error_msg = f"Failed to generate application layer: {str(e)}"
        logger.error(error_msg, exc_info=True)
        state["errors"].append({
            "step": "generate_application_layer",
            "error": error_msg,
            "exception": str(e)
        })
        return state


def generate_infrastructure_layer(state: ConversionState) -> ConversionState:
    """
    Generate infrastructure layer code (repository implementations, database config).

    Updates state with:
    - generated_files: Adds infrastructure layer files
    """
    state["current_step"] = "generate_infrastructure_layer"

    try:
        target_orm = state.get("target_orm", "typeorm")
        settings = Settings()
        file_ext = ".js" if settings.language == "javascript" else ".ts"
        verbose = state.get("verbose", False)

        if verbose:
            console.print(f"\n[bold cyan]Generating infrastructure layer...[/bold cyan]\n")

        generated_files = state.get("generated_files", {})

        if target_orm == "sequelize":
            if settings.language == "javascript":
                generated_files[f"src/infrastructure/database/sequelize{file_ext}"] = """const { Sequelize } = require('sequelize');

const sequelize = new Sequelize(process.env.DATABASE_URL, {
    dialect: process.env.DB_DIALECT || 'mysql',
    logging: process.env.DB_LOGGING === 'true',
});

async function connectDatabase() {
    await sequelize.authenticate();
    return sequelize;
}

module.exports = { sequelize, connectDatabase };
"""
                generated_files[f"src/infrastructure/database/model-registry{file_ext}"] = """const { sequelize } = require('./sequelize');

async function syncModels() {
    await sequelize.sync();
}

module.exports = { syncModels };
"""
            else:
                generated_files[f"src/infrastructure/database/sequelize{file_ext}"] = """import { Sequelize } from 'sequelize';

export const sequelize = new Sequelize(process.env.DATABASE_URL ?? '', {
    dialect: (process.env.DB_DIALECT as any) ?? 'mysql',
    logging: process.env.DB_LOGGING === 'true',
});

export async function connectDatabase(): Promise<Sequelize> {
    await sequelize.authenticate();
    return sequelize;
}
"""
                generated_files[f"src/infrastructure/database/model-registry{file_ext}"] = """import { sequelize } from './sequelize';

export async function syncModels(): Promise<void> {
    await sequelize.sync();
}
"""

        state["generated_files"] = generated_files

        if verbose:
            console.print(f"[green]✓ Generated infrastructure layer ({target_orm})[/green]\n")

        return state

    except Exception as e:
        error_msg = f"Failed to generate infrastructure layer: {str(e)}"
        logger.error(error_msg, exc_info=True)
        state["errors"].append({
            "step": "generate_infrastructure_layer",
            "error": error_msg,
            "exception": str(e)
        })
        return state


def generate_presentation_layer(state: ConversionState) -> ConversionState:
    """
    Generate presentation layer code using LLM (controllers with Express routing).

    Updates state with:
    - generated_files: Adds presentation layer files
    """
    state["current_step"] = "generate_presentation_layer"

    try:
        target_framework = state.get("target_framework", "express")
        verbose = state.get("verbose", False)
        classes_by_category = state.get("classes_by_category", {})

        if verbose:
            console.print(f"\n[bold cyan]Generating presentation layer with LLM...[/bold cyan]\n")

        all_controller_classes = classes_by_category.get("Controller", [])
        if not all_controller_classes:
            if verbose:
                console.print("[yellow]⚠ No controller classes found, skipping presentation layer[/yellow]\n")
            return state

        # Only use the selected controller class, not all controllers
        selected_controller_name = state.get("selected_source_classes", {}).get("controller")
        controller_classes = [c for c in all_controller_classes if c.name == selected_controller_name]
        if not controller_classes:
            controller_classes = all_controller_classes[:1]  # Fallback to first controller

        from src.generators.llm_code_creator import LLMCodeGenerator
        settings = Settings()
        generator = LLMCodeGenerator(settings)
        file_ext = ".js" if settings.language == "javascript" else ".ts"

        generated_files = state.get("generated_files", {})

        # Build all endpoints and group by resource
        endpoints_by_resource: Dict[str, List[APIEndpoint]] = {}
        for ctrl in controller_classes:
            for endpoint in _java_class_to_api_endpoints(ctrl):
                path_parts = endpoint.path.strip('/').split('/')
                resource = path_parts[0] if path_parts else 'root'
                if not resource:
                    resource = 'welcome'
                elif '.' in resource:
                    resource = resource.split('.')[0]
                endpoints_by_resource.setdefault(resource, []).append(endpoint)

        for resource, endpoints in endpoints_by_resource.items():
            controller_name = f"{resource.capitalize()}Controller"

            if verbose:
                console.print(f"  [cyan]→ Generating {controller_name} ({len(endpoints)} endpoints)...[/cyan]")

            try:
                source_context = _get_role_source_context(state, "controller")
                controller_code = generator.generate_controller(
                    endpoints=endpoints,
                    controller_name=controller_name,
                    framework=target_framework,
                    source_context=source_context,
                )

                file_path = f"src/presentation/controllers/{resource}.controller{file_ext}"
                generated_files[file_path] = controller_code

                if verbose:
                    console.print(f"  [green]✓ Generated {controller_name}[/green]")

            except Exception as e:
                if verbose:
                    console.print(f"  [yellow]⚠ Skipped {controller_name}: {str(e)}[/yellow]")
                logger.warning(f"Failed to generate controller {controller_name}: {e}")

        generated_files["analysis/conversion_traceability.json"] = json.dumps(
            _build_conversion_traceability(
                state=state,
                generated_files=generated_files,
                endpoints_by_resource=endpoints_by_resource,
            ),
            indent=2,
        )

        state["generated_files"] = generated_files

        if verbose:
            console.print(f"\n[green]✓ Generated presentation layer: {len(endpoints_by_resource)} controllers[/green]\n")

        return state

    except Exception as e:
        error_msg = f"Failed to generate presentation layer: {str(e)}"
        logger.error(error_msg, exc_info=True)
        state["errors"].append({
            "step": "generate_presentation_layer",
            "error": error_msg,
            "exception": str(e)
        })
        return state


def generate_config_files(state: ConversionState) -> ConversionState:
    """
    Generate configuration files (package.json, tsconfig.json, etc.).

    Updates state with:
    - generated_files: Adds config files
    """
    state["current_step"] = "generate_config_files"

    try:
        architecture = state.get("architecture")
        target_framework = state.get("target_framework", "express")
        target_orm = state.get("target_orm", "typeorm")
        verbose = state.get("verbose", False)

        if verbose:
            console.print(f"\n[bold cyan]Generating configuration files...[/bold cyan]\n")

        if not architecture:
            raise ValueError("Architecture not found in state")

        generated_files = state.get("generated_files", {})
        settings = Settings()
        selected_details = state.get("selected_source_class_details", {})

        if settings.language == "javascript":
            if target_framework == "nestjs":
                package_json = f"""{{
    "name": "converted-nodejs-app",
    "version": "1.0.0",
    "description": "Auto-generated from Java codebase",
    "main": "src/main.js",
    "scripts": {{
        "start": "node src/main.js",
        "dev": "node --watch src/main.js",
        "test": "jest"
    }},
    "dependencies": {{
        "@nestjs/common": "^10.0.0",
        "@nestjs/core": "^10.0.0",
        "@nestjs/platform-express": "^10.0.0",
        "reflect-metadata": "^0.2.0",
        "rxjs": "^7.8.0",
        "{target_orm}": "^0.0.0"
    }},
    "devDependencies": {{
        "jest": "^29.0.0"
    }}
}}
"""
            else:
                package_json = f"""{{
    "name": "converted-nodejs-app",
    "version": "1.0.0",
    "description": "Auto-generated from Java codebase",
    "main": "src/index.js",
    "scripts": {{
        "start": "node src/index.js",
        "dev": "node --watch src/index.js",
        "test": "jest"
    }},
    "dependencies": {{
        "express": "^4.18.0",
        "{target_orm}": "^0.0.0"
    }},
    "devDependencies": {{
        "jest": "^29.0.0"
    }}
}}
"""

            generated_files["package.json"] = package_json
            generated_files.pop("tsconfig.json", None)
        else:
            if target_framework == "nestjs":
                package_json = f"""{{
  "name": "converted-nodejs-app",
  "version": "1.0.0",
  "description": "Auto-generated from Java codebase",
  "main": "dist/main.js",
  "scripts": {{
    "build": "tsc",
    "start": "node dist/main.js",
    "dev": "ts-node-dev src/main.ts",
    "test": "jest"
  }},
  "dependencies": {{
    "@nestjs/common": "^10.0.0",
    "@nestjs/core": "^10.0.0",
    "@nestjs/platform-express": "^10.0.0",
    "class-transformer": "^0.5.1",
    "class-validator": "^0.14.1",
    "reflect-metadata": "^0.2.0",
    "rxjs": "^7.8.0",
    "{target_orm}": "^0.0.0"
  }},
  "devDependencies": {{
    "@types/node": "^20.0.0",
    "typescript": "^5.0.0",
    "ts-node-dev": "^2.0.0",
    "jest": "^29.0.0"
  }}
}}
"""
            else:
                package_json = f"""{{
  "name": "converted-nodejs-app",
  "version": "1.0.0",
  "description": "Auto-generated from Java codebase",
  "main": "dist/index.js",
  "scripts": {{
    "build": "tsc",
    "start": "node dist/index.js",
    "dev": "ts-node-dev src/index.ts",
    "test": "jest"
  }},
  "dependencies": {{
    "express": "^4.18.0",
    "{target_orm}": "^0.0.0"
  }},
  "devDependencies": {{
    "@types/express": "^4.17.0",
    "@types/node": "^20.0.0",
    "typescript": "^5.0.0",
    "ts-node-dev": "^2.0.0",
    "jest": "^29.0.0"
  }}
}}
"""

            generated_files["package.json"] = package_json

            tsconfig_json = """{
  "compilerOptions": {
    "target": "ES2020",
    "module": "commonjs",
    "lib": ["ES2020"],
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true,
    "experimentalDecorators": true,
    "emitDecoratorMetadata": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"]
}
"""
            generated_files["tsconfig.json"] = tsconfig_json

        if selected_details:
            generated_files["analysis/selected_source_classes.json"] = json.dumps(
                selected_details,
                indent=2,
            )

        # Generate app entry point
        ctrl_files = [p for p in generated_files if "/presentation/controllers/" in p]
        if settings.language == "javascript":
            controller_requires = ""
            router_uses = ""
            for cf in ctrl_files:
                resource = Path(cf).stem.replace(".controller", "")
                var_name = resource + "Router"
                rel = cf.replace("src/", "")
                controller_requires += f"const {var_name} = require('./{rel}');\n"
                router_uses += f"app.use('/api/{resource}', {var_name});\n"

            index_content = "'use strict';\n\nconst express = require('express');\n"
            index_content += controller_requires
            index_content += "\nconst app = express();\nconst PORT = process.env.PORT || 3000;\n\n"
            index_content += "app.use(express.json());\napp.use(express.urlencoded({ extended: true }));\n\n"
            index_content += "// Routes\n" + (router_uses if router_uses else "// No routes generated\n")
            index_content += "\napp.get('/health', (req, res) => res.json({ status: 'ok' }));\n\n"
            index_content += "app.listen(PORT, () => {\n    console.log(`Server running on port ${PORT}`);\n});\n\n"
            index_content += "module.exports = app;\n"
            generated_files["src/index.js"] = index_content
        else:
            controller_imports = ""
            router_uses = ""
            for cf in ctrl_files:
                resource = Path(cf).stem.replace(".controller", "")
                var_name = resource + "Router"
                rel = "./" + cf.replace("src/", "").replace(".ts", "")
                controller_imports += f"import {var_name} from '{rel}';\n"
                router_uses += f"app.use('/api/{resource}', {var_name});\n"

            index_content = "import express from 'express';\n"
            index_content += controller_imports
            index_content += "\nconst app = express();\nconst PORT = process.env.PORT ?? 3000;\n\n"
            index_content += "app.use(express.json());\napp.use(express.urlencoded({ extended: true }));\n\n"
            index_content += "// Routes\n" + (router_uses if router_uses else "// No routes generated\n")
            index_content += "\napp.get('/health', (_req, res) => res.json({ status: 'ok' }));\n\n"
            index_content += "app.listen(PORT, () => {\n    console.log(`Server running on port ${PORT}`);\n});\n\n"
            index_content += "export default app;\n"
            generated_files["src/index.ts"] = index_content

        state["generated_files"] = generated_files

        if verbose:
            console.print(f"[green]✓ Generated configuration files[/green]\n")

        return state

    except Exception as e:
        error_msg = f"Failed to generate config files: {str(e)}"
        logger.error(error_msg, exc_info=True)
        state["errors"].append({
            "step": "generate_config_files",
            "error": error_msg,
            "exception": str(e)
        })
        return state


# ============================================================
# PHASE 4: Output & Finalization Nodes
# ============================================================


def write_outputs(state: ConversionState) -> ConversionState:
    """
    Write all generated files to disk.

    Creates the output directory structure and writes all files.
    """
    state["current_step"] = "write_outputs"

    try:
        output_dir = state.get("output_directory", "./output")
        generated_files = state.get("generated_files", {})
        verbose = state.get("verbose", False)

        if verbose:
            console.print(f"\n[bold cyan]Writing generated files to {output_dir}...[/bold cyan]\n")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        for file_path, content in generated_files.items():
            full_path = output_path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)

            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

            if verbose:
                console.print(f"  ✓ {file_path}")

        if verbose:
            console.print(f"\n[green]✓ Wrote {len(generated_files)} files to {output_dir}[/green]\n")

        import time
        state["end_time"] = time.time()

        return state

    except Exception as e:
        error_msg = f"Failed to write outputs: {str(e)}"
        logger.error(error_msg, exc_info=True)
        state["errors"].append({
            "step": "write_outputs",
            "error": error_msg,
            "exception": str(e)
        })
        return state
