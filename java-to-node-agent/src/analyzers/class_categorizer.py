"""
Enhanced class categorization using patterns and heuristics.
"""

from typing import List, Set, Dict
from src.models.java_models import JavaClass, JavaAnnotation


class ClassCategorizer:
    """
    Enhanced categorization of Java classes beyond simple annotation-based detection.
    Analyzes patterns, naming conventions, and relationships to determine class roles.
    """

    # Annotation patterns for different categories
    CONTROLLER_ANNOTATIONS = {
        "RestController",
        "Controller",
        "Resource",
        "Path",
        "WebServlet",
    }

    SERVICE_ANNOTATIONS = {
        "Service",
        "ApplicationScoped",
        "Singleton",
        "Stateless",
        "Stateful",
    }

    REPOSITORY_ANNOTATIONS = {
        "Repository",
        "Dao",
        "Mapper",
    }

    ENTITY_ANNOTATIONS = {
        "Entity",
        "Table",
        "Document",
        "Embeddable",
    }

    CONFIG_ANNOTATIONS = {
        "Configuration",
        "ConfigurationProperties",
        "Component",
        "Bean",
    }

    # Naming patterns
    CONTROLLER_SUFFIXES = {"Controller", "Resource", "Endpoint", "Api"}
    SERVICE_SUFFIXES = {"Service", "Manager", "Handler", "Processor", "Facade"}
    REPOSITORY_SUFFIXES = {"Repository", "Dao", "Mapper", "Store"}
    ENTITY_SUFFIXES = {"Entity", "Model", "Document", "DTO", "VO"}
    CONFIG_SUFFIXES = {"Config", "Configuration", "Properties", "Settings"}
    UTIL_SUFFIXES = {"Util", "Utils", "Helper", "Helpers", "Tool", "Tools"}

    # Interface patterns
    REPOSITORY_INTERFACES = {
        "JpaRepository",
        "CrudRepository",
        "PagingAndSortingRepository",
        "MongoRepository",
        "Repository",
    }

    def __init__(self) -> None:
        """Initialize the class categorizer."""
        pass

    def categorize(self, java_class: JavaClass) -> str:
        """
        Perform enhanced categorization of a Java class.

        Args:
            java_class: The JavaClass to categorize

        Returns:
            Category string (Controller, Service, DAO, Entity, Config, Util, etc.)
        """
        # Use existing category as a starting point if it's not "Other"
        if java_class.category != "Other":
            current_category = java_class.category
        else:
            current_category = None

        # Check annotations first (highest priority)
        annotation_category = self._categorize_by_annotations(java_class)
        if annotation_category:
            return annotation_category

        # Check inheritance/implementation
        inheritance_category = self._categorize_by_inheritance(java_class)
        if inheritance_category:
            return inheritance_category

        # Check naming patterns
        naming_category = self._categorize_by_naming(java_class)
        if naming_category:
            return naming_category

        # Check class structure and methods
        structure_category = self._categorize_by_structure(java_class)
        if structure_category:
            return structure_category

        # Fall back to current category or "Other"
        return current_category or "Other"

    def _categorize_by_annotations(self, java_class: JavaClass) -> str | None:
        """Categorize based on class annotations."""
        annotation_names = {ann.name for ann in java_class.annotations}

        if annotation_names & self.CONTROLLER_ANNOTATIONS:
            return "Controller"
        if annotation_names & self.SERVICE_ANNOTATIONS:
            return "Service"
        if annotation_names & self.REPOSITORY_ANNOTATIONS:
            return "DAO"
        if annotation_names & self.ENTITY_ANNOTATIONS:
            return "Entity"
        if annotation_names & self.CONFIG_ANNOTATIONS:
            return "Config"

        return None

    def _categorize_by_inheritance(self, java_class: JavaClass) -> str | None:
        """Categorize based on inheritance and interface implementation."""
        # Check if it implements a repository interface
        for interface in java_class.implements:
            if any(repo_interface in interface for repo_interface in self.REPOSITORY_INTERFACES):
                return "DAO"

        # Check if it extends a known base class
        if java_class.extends:
            extends_lower = java_class.extends.lower()
            if "controller" in extends_lower or "resource" in extends_lower:
                return "Controller"
            if "service" in extends_lower:
                return "Service"
            if "repository" in extends_lower or "dao" in extends_lower:
                return "DAO"

        return None

    def _categorize_by_naming(self, java_class: JavaClass) -> str | None:
        """Categorize based on naming conventions."""
        class_name = java_class.name

        # Check controller patterns
        if any(class_name.endswith(suffix) for suffix in self.CONTROLLER_SUFFIXES):
            return "Controller"

        # Check service patterns
        if any(class_name.endswith(suffix) for suffix in self.SERVICE_SUFFIXES):
            return "Service"

        # Check repository patterns
        if any(class_name.endswith(suffix) for suffix in self.REPOSITORY_SUFFIXES):
            return "DAO"

        # Check entity patterns
        if any(class_name.endswith(suffix) for suffix in self.ENTITY_SUFFIXES):
            # Double-check if it's actually an entity (has entity-like fields)
            if self._has_entity_characteristics(java_class):
                return "Entity"

        # Check config patterns
        if any(class_name.endswith(suffix) for suffix in self.CONFIG_SUFFIXES):
            return "Config"

        # Check util patterns
        if any(class_name.endswith(suffix) for suffix in self.UTIL_SUFFIXES):
            return "Util"

        return None

    def _categorize_by_structure(self, java_class: JavaClass) -> str | None:
        """Categorize based on class structure and method patterns."""
        # Check if it looks like a controller (has request mapping methods)
        if self._has_rest_endpoints(java_class):
            return "Controller"

        # Check if it looks like a service (has business logic methods)
        if self._has_service_characteristics(java_class):
            return "Service"

        # Check if it looks like an entity (mostly fields with getters/setters)
        if self._has_entity_characteristics(java_class):
            return "Entity"

        # Check if it's a utility class (all static methods)
        if self._is_utility_class(java_class):
            return "Util"

        return None

    def _has_rest_endpoints(self, java_class: JavaClass) -> bool:
        """Check if class has REST endpoint methods."""
        rest_annotations = {
            "GetMapping",
            "PostMapping",
            "PutMapping",
            "DeleteMapping",
            "PatchMapping",
            "RequestMapping",
            "GET",
            "POST",
            "PUT",
            "DELETE",
            "PATCH",
            "Path",
        }

        for method in java_class.methods:
            method_annotations = {ann.name for ann in method.annotations}
            if method_annotations & rest_annotations:
                return True

        return False

    def _has_service_characteristics(self, java_class: JavaClass) -> bool:
        """Check if class has service-like characteristics."""
        if not java_class.methods:
            return False

        # Services typically have multiple public methods
        public_methods = [m for m in java_class.methods if "public" in m.modifiers]

        # Services often have transactional methods
        transactional_methods = 0
        for method in java_class.methods:
            method_annotations = {ann.name for ann in method.annotations}
            if "Transactional" in method_annotations or "Async" in method_annotations:
                transactional_methods += 1

        return len(public_methods) >= 3 or transactional_methods > 0

    def _has_entity_characteristics(self, java_class: JavaClass) -> bool:
        """Check if class has entity-like characteristics."""
        if not java_class.fields:
            return False

        # Entities typically have:
        # 1. Multiple private fields
        # 2. Getters and setters
        # 3. Persistence annotations on fields

        private_fields = [f for f in java_class.fields if "private" in f.modifiers]

        # Check for persistence annotations on fields
        persistence_field_annotations = {
            "Id",
            "Column",
            "ManyToOne",
            "OneToMany",
            "OneToOne",
            "ManyToMany",
            "JoinColumn",
            "Field",
        }

        fields_with_persistence = 0
        for field in java_class.fields:
            field_annotations = {ann.name for ann in field.annotations}
            if field_annotations & persistence_field_annotations:
                fields_with_persistence += 1

        # Count getter/setter methods
        getter_setter_count = 0
        for method in java_class.methods:
            if (method.name.startswith("get") or method.name.startswith("set") or
                method.name.startswith("is")):
                getter_setter_count += 1

        # Entity if:
        # - Has multiple private fields
        # - Has persistence annotations OR has many getters/setters
        has_many_fields = len(private_fields) >= 3
        has_persistence = fields_with_persistence > 0
        has_accessors = getter_setter_count >= len(private_fields)

        return has_many_fields and (has_persistence or has_accessors)

    def _is_utility_class(self, java_class: JavaClass) -> bool:
        """Check if class is a utility class (all static methods)."""
        if not java_class.methods or java_class.type != "class":
            return False

        # Check if all methods are static
        static_methods = [m for m in java_class.methods if "static" in m.modifiers]

        # Utility class if most methods are static (at least 70%)
        return len(static_methods) / len(java_class.methods) >= 0.7

    def get_category_confidence(self, java_class: JavaClass) -> Dict[str, float]:
        """
        Get confidence scores for different categories.

        Args:
            java_class: The JavaClass to analyze

        Returns:
            Dictionary mapping category names to confidence scores (0.0-1.0)
        """
        scores: Dict[str, float] = {
            "Controller": 0.0,
            "Service": 0.0,
            "DAO": 0.0,
            "Entity": 0.0,
            "Config": 0.0,
            "Util": 0.0,
            "Other": 0.0,
        }

        annotation_names = {ann.name for ann in java_class.annotations}

        # Annotation-based scoring (high weight)
        if annotation_names & self.CONTROLLER_ANNOTATIONS:
            scores["Controller"] += 0.8
        if annotation_names & self.SERVICE_ANNOTATIONS:
            scores["Service"] += 0.8
        if annotation_names & self.REPOSITORY_ANNOTATIONS:
            scores["DAO"] += 0.8
        if annotation_names & self.ENTITY_ANNOTATIONS:
            scores["Entity"] += 0.8
        if annotation_names & self.CONFIG_ANNOTATIONS:
            scores["Config"] += 0.8

        # Naming-based scoring (medium weight)
        class_name = java_class.name
        if any(class_name.endswith(suffix) for suffix in self.CONTROLLER_SUFFIXES):
            scores["Controller"] += 0.5
        if any(class_name.endswith(suffix) for suffix in self.SERVICE_SUFFIXES):
            scores["Service"] += 0.5
        if any(class_name.endswith(suffix) for suffix in self.REPOSITORY_SUFFIXES):
            scores["DAO"] += 0.5
        if any(class_name.endswith(suffix) for suffix in self.ENTITY_SUFFIXES):
            scores["Entity"] += 0.3

        # Structure-based scoring (lower weight)
        if self._has_rest_endpoints(java_class):
            scores["Controller"] += 0.6
        if self._has_service_characteristics(java_class):
            scores["Service"] += 0.4
        if self._has_entity_characteristics(java_class):
            scores["Entity"] += 0.5
        if self._is_utility_class(java_class):
            scores["Util"] += 0.7

        # Normalize scores to 0-1 range
        max_score = max(scores.values())
        if max_score > 0:
            scores = {k: v / max_score for k, v in scores.items()}
        else:
            scores["Other"] = 1.0

        return scores
