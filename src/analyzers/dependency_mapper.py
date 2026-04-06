"""
Dependency mapping for analyzing relationships between Java classes.
"""

from typing import List, Dict, Set, Optional
from dataclasses import dataclass
from src.models.java_models import JavaClass, JavaField


@dataclass
class ClassDependency:
    """Represents a dependency between two classes."""

    from_class: str  # Source class name
    to_class: str  # Target class name
    dependency_type: str  # Type of dependency (field, parameter, return_type, extends, implements)
    field_name: Optional[str] = None  # Field name if dependency is via field
    method_name: Optional[str] = None  # Method name if dependency is via method


@dataclass
class DependencyGraph:
    """Represents the complete dependency graph of a project."""

    dependencies: List[ClassDependency]
    class_map: Dict[str, JavaClass]  # Map of class name to JavaClass object

    def get_dependencies_for_class(self, class_name: str) -> List[ClassDependency]:
        """Get all dependencies for a specific class."""
        return [dep for dep in self.dependencies if dep.from_class == class_name]

    def get_dependents_of_class(self, class_name: str) -> List[ClassDependency]:
        """Get all classes that depend on a specific class."""
        return [dep for dep in self.dependencies if dep.to_class == class_name]

    def get_dependency_count(self, class_name: str) -> int:
        """Get the number of dependencies for a class."""
        return len(self.get_dependencies_for_class(class_name))

    def get_dependent_count(self, class_name: str) -> int:
        """Get the number of classes that depend on this class."""
        return len(self.get_dependents_of_class(class_name))


class DependencyMapper:
    """
    Maps and analyzes dependencies between Java classes.
    Identifies field injections, method dependencies, inheritance, and interfaces.
    """

    def __init__(self, java_classes: List[JavaClass]) -> None:
        """
        Initialize the dependency mapper.

        Args:
            java_classes: List of JavaClass objects to analyze
        """
        self.java_classes = java_classes
        self.class_map = {cls.name: cls for cls in java_classes}
        self.dependencies: List[ClassDependency] = []

    def map_dependencies(self) -> DependencyGraph:
        """
        Analyze all classes and build the dependency graph.

        Returns:
            DependencyGraph object containing all dependencies
        """
        self.dependencies = []

        for java_class in self.java_classes:
            self._analyze_class_dependencies(java_class)

        return DependencyGraph(
            dependencies=self.dependencies,
            class_map=self.class_map,
        )

    def _analyze_class_dependencies(self, java_class: JavaClass) -> None:
        """Analyze all dependencies for a single class."""
        # Analyze field dependencies
        for field in java_class.fields:
            self._analyze_field_dependency(java_class, field)

        # Analyze method dependencies
        for method in java_class.methods:
            # Check return type
            if method.return_type != "void":
                self._add_dependency_if_exists(
                    java_class.name,
                    method.return_type,
                    "return_type",
                    method_name=method.name,
                )

            # Check parameters
            for param in method.parameters:
                self._add_dependency_if_exists(
                    java_class.name,
                    param.type,
                    "parameter",
                    method_name=method.name,
                )

        # Analyze inheritance
        if java_class.extends:
            self._add_dependency_if_exists(
                java_class.name,
                java_class.extends,
                "extends",
            )

        # Analyze interface implementations
        for interface in java_class.implements:
            self._add_dependency_if_exists(
                java_class.name,
                interface,
                "implements",
            )

    def _analyze_field_dependency(self, java_class: JavaClass, field: JavaField) -> None:
        """Analyze dependencies from a field."""
        field_type = field.type

        # Check if it's an injection (has @Autowired, @Inject, etc.)
        injection_annotations = {"Autowired", "Inject", "Resource", "Value"}
        is_injection = any(
            ann.name in injection_annotations for ann in field.annotations
        )

        dependency_type = "field_injection" if is_injection else "field"

        self._add_dependency_if_exists(
            java_class.name,
            field_type,
            dependency_type,
            field_name=field.name,
        )

    def _add_dependency_if_exists(
        self,
        from_class: str,
        to_class: str,
        dependency_type: str,
        field_name: Optional[str] = None,
        method_name: Optional[str] = None,
    ) -> None:
        """
        Add a dependency if the target class exists in our class map.

        Args:
            from_class: Source class name
            to_class: Target class name
            dependency_type: Type of dependency
            field_name: Optional field name
            method_name: Optional method name
        """
        # Extract base type name (handle generics like List<Customer>)
        base_type = self._extract_base_type(to_class)

        # Check if this class exists in our codebase
        if base_type in self.class_map and base_type != from_class:
            self.dependencies.append(
                ClassDependency(
                    from_class=from_class,
                    to_class=base_type,
                    dependency_type=dependency_type,
                    field_name=field_name,
                    method_name=method_name,
                )
            )

    def _extract_base_type(self, type_string: str) -> str:
        """
        Extract the base type from a type string.

        Examples:
            List<Customer> -> List (or Customer if List is not in our codebase)
            Map<String, Customer> -> Map (or Customer)
            Customer[] -> Customer

        Args:
            type_string: The type string to parse

        Returns:
            Base type name
        """
        # Handle arrays
        if type_string.endswith("[]"):
            return type_string[:-2]

        # Handle generics
        if "<" in type_string:
            # Extract all type arguments
            base = type_string.split("<")[0].strip()
            type_args_str = type_string[type_string.index("<") + 1:type_string.rindex(">")]

            # Split by comma to get individual type arguments
            type_args = [arg.strip() for arg in type_args_str.split(",")]

            # If the base type is in our codebase, return it
            if base in self.class_map:
                return base

            # Otherwise, check type arguments
            for type_arg in type_args:
                # Recursively extract base type from type arguments
                extracted = self._extract_base_type(type_arg)
                if extracted in self.class_map:
                    return extracted

            return base

        return type_string

    def get_injection_dependencies(self) -> List[ClassDependency]:
        """Get all field injection dependencies."""
        return [dep for dep in self.dependencies if dep.dependency_type == "field_injection"]

    def get_class_hierarchy(self) -> Dict[str, List[str]]:
        """
        Get the class hierarchy (extends relationships).

        Returns:
            Dictionary mapping parent class names to lists of child class names
        """
        hierarchy: Dict[str, List[str]] = {}

        for dep in self.dependencies:
            if dep.dependency_type == "extends":
                if dep.to_class not in hierarchy:
                    hierarchy[dep.to_class] = []
                hierarchy[dep.to_class].append(dep.from_class)

        return hierarchy

    def get_interface_implementations(self) -> Dict[str, List[str]]:
        """
        Get interface implementations.

        Returns:
            Dictionary mapping interface names to lists of implementing class names
        """
        implementations: Dict[str, List[str]] = {}

        for dep in self.dependencies:
            if dep.dependency_type == "implements":
                if dep.to_class not in implementations:
                    implementations[dep.to_class] = []
                implementations[dep.to_class].append(dep.from_class)

        return implementations

    def find_circular_dependencies(self) -> List[List[str]]:
        """
        Find circular dependencies in the codebase.

        Returns:
            List of dependency cycles (each cycle is a list of class names)
        """
        cycles = []
        visited = set()

        def dfs(node: str, path: List[str], rec_stack: Set[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            # Get all dependencies for this node
            deps = self.get_dependencies_for_class(node)

            for dep in deps:
                target = dep.to_class

                if target not in visited:
                    dfs(target, path.copy(), rec_stack.copy())
                elif target in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(target)
                    cycle = path[cycle_start:] + [target]
                    if cycle not in cycles:
                        cycles.append(cycle)

            rec_stack.discard(node)

        for java_class in self.java_classes:
            if java_class.name not in visited:
                dfs(java_class.name, [], set())

        return cycles

    def get_dependencies_for_class(self, class_name: str) -> List[ClassDependency]:
        """Get all dependencies for a specific class."""
        return [dep for dep in self.dependencies if dep.from_class == class_name]

    def get_dependency_statistics(self) -> Dict:
        """
        Get statistics about dependencies in the codebase.

        Returns:
            Dictionary containing dependency statistics
        """
        total_deps = len(self.dependencies)
        injection_deps = len(self.get_injection_dependencies())

        # Count dependencies by type
        dep_types: Dict[str, int] = {}
        for dep in self.dependencies:
            dep_types[dep.dependency_type] = dep_types.get(dep.dependency_type, 0) + 1

        # Find most dependent classes (classes with most dependencies)
        class_dep_counts: Dict[str, int] = {}
        for dep in self.dependencies:
            class_dep_counts[dep.from_class] = class_dep_counts.get(dep.from_class, 0) + 1

        most_dependent = sorted(
            class_dep_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:5]

        # Find most depended-upon classes
        class_dependent_counts: Dict[str, int] = {}
        for dep in self.dependencies:
            class_dependent_counts[dep.to_class] = class_dependent_counts.get(dep.to_class, 0) + 1

        most_depended_upon = sorted(
            class_dependent_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:5]

        return {
            "total_dependencies": total_deps,
            "injection_dependencies": injection_deps,
            "dependencies_by_type": dep_types,
            "most_dependent_classes": most_dependent,
            "most_depended_upon_classes": most_depended_upon,
            "circular_dependencies": len(self.find_circular_dependencies()),
        }
