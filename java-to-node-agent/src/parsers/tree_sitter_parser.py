"""
Main tree-sitter based Java parser.
Extracts complete structural information from Java source files.
"""

from typing import Any, Dict, List, Optional, Tuple
from tree_sitter import Language, Parser, Node, Tree, QueryCursor
import tree_sitter_java as tsjava

from ..models.java_models import (
    JavaClass,
    JavaMethod,
    JavaField,
    JavaAnnotation,
    JavaParameter,
)
from .ast_extractor import ASTExtractor
from .queries import JavaQueries


class TreeSitterJavaParser:
    """
    Fast, robust Java parser using tree-sitter.
    Extracts structural information without semantic analysis.
    """

    def __init__(self) -> None:
        """Initialize the parser with Java language and queries."""
        self.language = Language(tsjava.language())
        self.parser = Parser(self.language)
        self.queries = JavaQueries()
        self.extractor = ASTExtractor()

    def parse_file(self, file_path: str, content: str) -> JavaClass:
        """
        Parse a Java file and extract complete structural information.

        Args:
            file_path: Path to the Java file
            content: Java source code content

        Returns:
            JavaClass object with all extracted information

        Raises:
            ValueError: If no class/interface found in file
        """
        tree = self.parser.parse(bytes(content, "utf8"))
        root = tree.root_node

        # Extract basic information
        package = self._extract_package(root, content)
        imports = self._extract_imports(root, content)

        # Find class, interface, or enum declaration
        class_node = self._find_class_node(root)
        if not class_node:
            raise ValueError(f"No class/interface/enum found in {file_path}")

        # Extract class metadata
        class_info = self._extract_class_info(class_node, content)

        # Extract annotations at class level
        class_annotations = self._extract_annotations(class_node, content)

        # Extract methods
        methods = self._extract_methods(class_node, content)

        # Extract fields
        fields = self._extract_fields(class_node, content)

        # Categorize the class
        category = self._categorize_class(
            class_info["name"], class_annotations, class_info.get("extends")
        )

        return JavaClass(
            name=class_info["name"],
            type=class_info["type"],
            package=package,
            imports=imports,
            annotations=class_annotations,
            modifiers=class_info.get("modifiers", []),
            extends=class_info.get("extends"),
            implements=class_info.get("implements", []),
            fields=fields,
            methods=methods,
            file_path=file_path,
            category=category,
            source_code=content,
            start_line=class_node.start_point[0] + 1,
            end_line=class_node.end_point[0] + 1,
        )

    def _extract_package(self, root: Node, source: str) -> str:
        """
        Extract the package declaration from the file root node.

        Args:
            root: The root AST node of the parsed Java file
            source: The Java source code string

        Returns:
            The package name (e.g., "com.example.controller"), or empty string if absent
        """
        query = self.queries.get_package_query()
        cursor = QueryCursor(query)
        matches = cursor.matches(root)

        for match in matches:
            captures_dict = match[1]
            if "package_name" in captures_dict:
                nodes = captures_dict["package_name"]
                node_list = nodes if isinstance(nodes, list) else [nodes]
                for node in node_list:
                    return self.extractor.get_node_text(node, source)
        return ""

    def _extract_imports(self, root: Node, source: str) -> List[str]:
        """
        Extract all import statements from the file.

        Args:
            root: The root AST node of the parsed Java file
            source: The Java source code string

        Returns:
            List of fully-qualified import paths (e.g., ["org.springframework.web.bind.annotation.RestController"])
        """
        imports = []
        query = self.queries.get_import_query()
        cursor = QueryCursor(query)
        matches = cursor.matches(root)

        for match in matches:
            captures_dict = match[1]
            if "import_path" in captures_dict:
                nodes = captures_dict["import_path"]
                node_list = nodes if isinstance(nodes, list) else [nodes]
                for node in node_list:
                    imports.append(self.extractor.get_node_text(node, source))
        return imports

    def _find_class_node(self, root: Node) -> Optional[Node]:
        """
        Find the top-level class, interface, or enum declaration node.

        Tries class first, then interface, then enum. Only returns the first
        top-level declaration (inner classes are ignored at this stage).

        Args:
            root: The root AST node of the parsed Java file

        Returns:
            The declaration node, or None if no class/interface/enum was found
        """
        # Try class first
        query = self.queries.get_class_query()
        cursor = QueryCursor(query)
        matches = cursor.matches(root)
        for match in matches:
            captures_dict = match[1]
            if "class" in captures_dict:
                nodes = captures_dict["class"]
                return nodes[0] if isinstance(nodes, list) else nodes

        # Try interface
        query = self.queries.get_interface_query()
        cursor = QueryCursor(query)
        matches = cursor.matches(root)
        for match in matches:
            captures_dict = match[1]
            if "interface" in captures_dict:
                nodes = captures_dict["interface"]
                return nodes[0] if isinstance(nodes, list) else nodes

        # Try enum
        query = self.queries.get_enum_query()
        cursor = QueryCursor(query)
        matches = cursor.matches(root)
        for match in matches:
            captures_dict = match[1]
            if "enum" in captures_dict:
                nodes = captures_dict["enum"]
                return nodes[0] if isinstance(nodes, list) else nodes

        return None

    def _extract_class_info(self, class_node: Node, source: str) -> Dict[str, Any]:
        """
        Extract basic structural metadata from a class, interface, or enum node.

        Reads name, type, modifiers, superclass, and implemented interfaces.

        Args:
            class_node: The AST node for the class/interface/enum declaration
            source: The Java source code string

        Returns:
            Dict with keys: "type", "name", "modifiers" (list), "extends" (optional),
            "implements" (list)
        """
        info: Dict[str, Any] = {
            "modifiers": [],
            "implements": [],
        }

        # Determine type
        if class_node.type == "class_declaration":
            info["type"] = "class"
            query = self.queries.get_class_query()
            name_capture = "class_name"
        elif class_node.type == "interface_declaration":
            info["type"] = "interface"
            query = self.queries.get_interface_query()
            name_capture = "interface_name"
        elif class_node.type == "enum_declaration":
            info["type"] = "enum"
            query = self.queries.get_enum_query()
            name_capture = "enum_name"
        else:
            info["type"] = "class"
            name_capture = "class_name"
            query = self.queries.get_class_query()

        cursor = QueryCursor(query)
        matches = cursor.matches(class_node)

        for match in matches:
            captures_dict = match[1]

            # Extract class/interface/enum name
            if name_capture in captures_dict:
                nodes = captures_dict[name_capture]
                node_list = nodes if isinstance(nodes, list) else [nodes]
                info["name"] = self.extractor.get_node_text(node_list[0], source)

            # Extract modifiers
            if "modifiers" in captures_dict:
                nodes = captures_dict["modifiers"]
                node_list = nodes if isinstance(nodes, list) else [nodes]
                info["modifiers"] = self._parse_modifiers(node_list[0], source)

            # Extract superclass
            if "superclass" in captures_dict:
                nodes = captures_dict["superclass"]
                node_list = nodes if isinstance(nodes, list) else [nodes]
                for child in node_list[0].children:
                    if child.type == "type_identifier":
                        info["extends"] = self.extractor.get_node_text(child, source)
                        break

            # Extract interfaces
            if "interfaces" in captures_dict or "extends" in captures_dict:
                key = "interfaces" if "interfaces" in captures_dict else "extends"
                nodes = captures_dict[key]
                node_list = nodes if isinstance(nodes, list) else [nodes]
                info["implements"] = self._parse_interfaces(node_list[0], source)

        return info

    def _parse_modifiers(self, modifiers_node: Node, source: str) -> List[str]:
        """
        Parse access and other modifiers from a modifiers AST node.

        Args:
            modifiers_node: The AST node for the modifiers block
            source: The Java source code string (unused but kept for API consistency)

        Returns:
            List of modifier strings (e.g., ["public", "static", "final"])
        """
        modifiers = []
        modifier_types = [
            "public",
            "private",
            "protected",
            "static",
            "final",
            "abstract",
            "synchronized",
            "volatile",
            "transient",
            "native",
        ]

        for child in modifiers_node.children:
            if child.type in modifier_types:
                modifiers.append(child.type)

        return modifiers

    def _parse_interfaces(self, interfaces_node: Node, source: str) -> List[str]:
        """
        Parse the list of implemented interfaces (or extended interfaces for interface declarations).

        Handles both plain type identifiers and generic types (e.g., JpaRepository<User, Long>
        is captured as "JpaRepository").

        Args:
            interfaces_node: The AST node for the super_interfaces/extends_interfaces clause
            source: The Java source code string

        Returns:
            List of interface (or parent interface) names
        """
        interfaces = []

        # Find type_list node
        type_list = self.extractor.find_child_by_type(interfaces_node, "type_list")
        if not type_list:
            return interfaces

        for child in type_list.children:
            if child.type == "type_identifier":
                interfaces.append(self.extractor.get_node_text(child, source))
            elif child.type == "generic_type":
                # Extract base type from generic
                type_id = self.extractor.find_child_by_type(child, "type_identifier")
                if type_id:
                    interfaces.append(self.extractor.get_node_text(type_id, source))

        return interfaces

    def _extract_annotations(
        self, node: Node, source: str
    ) -> List[JavaAnnotation]:
        """
        Extract all annotations attached to a class, method, or field node.

        Looks for a modifiers child node and queries it for annotation declarations,
        capturing both marker annotations (@Override) and value annotations (@GetMapping("/path")).

        Args:
            node: The AST node whose annotations should be extracted
            source: The Java source code string

        Returns:
            List of JavaAnnotation objects with name and arguments
        """
        annotations = []

        # Look for modifiers node which contains annotations
        modifiers_node = self.extractor.find_child_by_type(node, "modifiers")
        if not modifiers_node:
            return annotations

        query = self.queries.get_annotation_query()
        cursor = QueryCursor(query)
        matches = cursor.matches(modifiers_node)

        for match in matches:
            captures_dict = match[1]

            # Get annotation name
            if "annotation_name" in captures_dict:
                name_nodes = captures_dict["annotation_name"]
                name_node_list = name_nodes if isinstance(name_nodes, list) else [name_nodes]

                if name_node_list:
                    ann_name = self.extractor.get_node_text(name_node_list[0], source)
                    # Remove @ prefix if present
                    ann_name = ann_name.lstrip("@")

                    # Get annotation arguments if present
                    args = ""
                    if "args" in captures_dict:
                        args_nodes = captures_dict["args"]
                        args_node_list = args_nodes if isinstance(args_nodes, list) else [args_nodes]
                        if args_node_list:
                            args = self.extractor.get_node_text(args_node_list[0], source)

                    annotations.append(JavaAnnotation(name=ann_name, arguments=args))

        return annotations

    def _extract_fields(self, class_node: Node, source: str) -> List[JavaField]:
        """
        Extract all field declarations from a class or interface body.

        Parses field name, type, access modifiers, and annotations for each
        field_declaration in the class body.

        Args:
            class_node: The AST node for the class or interface declaration
            source: The Java source code string

        Returns:
            List of JavaField objects for every declared field
        """
        fields = []

        # Find class body
        class_body = self.extractor.find_child_by_type(
            class_node, "class_body"
        ) or self.extractor.find_child_by_type(class_node, "interface_body")
        if not class_body:
            return fields

        query = self.queries.get_field_query()
        cursor = QueryCursor(query)
        matches = cursor.matches(class_body)

        for match in matches:
            captures_dict = match[1]

            # Extract field name
            if "field_name" not in captures_dict:
                continue

            field_name_nodes = captures_dict["field_name"]
            field_name_list = field_name_nodes if isinstance(field_name_nodes, list) else [field_name_nodes]
            field_name = self.extractor.get_node_text(field_name_list[0], source)

            # Extract field type
            field_type = "unknown"
            if "field_type" in captures_dict:
                field_type_nodes = captures_dict["field_type"]
                field_type_list = field_type_nodes if isinstance(field_type_nodes, list) else [field_type_nodes]
                field_type = self.extractor.get_node_text(field_type_list[0], source)

            # Extract modifiers
            modifiers = []
            if "modifiers" in captures_dict:
                modifiers_nodes = captures_dict["modifiers"]
                modifiers_list = modifiers_nodes if isinstance(modifiers_nodes, list) else [modifiers_nodes]
                modifiers = self._parse_modifiers(modifiers_list[0], source)

            # Extract annotations - use the field node from the match
            field_node = None
            if "field" in captures_dict:
                field_nodes = captures_dict["field"]
                field_node_list = field_nodes if isinstance(field_nodes, list) else [field_nodes]
                field_node = field_node_list[0]

            annotations = self._extract_annotations(field_node, source) if field_node else []

            fields.append(
                JavaField(
                    name=field_name,
                    type=field_type,
                    modifiers=modifiers,
                    annotations=annotations,
                )
            )

        return fields

    def _extract_methods(self, class_node: Node, source: str) -> List[JavaMethod]:
        """
        Extract all method declarations from a class or interface body.

        Parses name, return type, parameters, modifiers, annotations, body source,
        and line range for each method_declaration in the class body.

        Args:
            class_node: The AST node for the class or interface declaration
            source: The Java source code string

        Returns:
            List of JavaMethod objects; methods without a resolvable node are skipped
        """
        methods = []

        # Find class body
        class_body = self.extractor.find_child_by_type(
            class_node, "class_body"
        ) or self.extractor.find_child_by_type(class_node, "interface_body")
        if not class_body:
            return methods

        query = self.queries.get_method_query()
        cursor = QueryCursor(query)
        matches = cursor.matches(class_body)

        for match in matches:
            captures_dict = match[1]

            # Extract method name
            if "method_name" not in captures_dict:
                continue

            method_name_nodes = captures_dict["method_name"]
            method_name_list = method_name_nodes if isinstance(method_name_nodes, list) else [method_name_nodes]
            method_name = self.extractor.get_node_text(method_name_list[0], source)

            # Extract return type
            return_type = "void"
            if "return_type" in captures_dict:
                return_type_nodes = captures_dict["return_type"]
                return_type_list = return_type_nodes if isinstance(return_type_nodes, list) else [return_type_nodes]
                return_type = self.extractor.get_node_text(return_type_list[0], source)

            # Extract parameters
            parameters = []
            if "params" in captures_dict:
                params_nodes = captures_dict["params"]
                params_list = params_nodes if isinstance(params_nodes, list) else [params_nodes]
                parameters = self._parse_parameters(params_list[0], source)

            # Extract modifiers
            modifiers = []
            if "modifiers" in captures_dict:
                modifiers_nodes = captures_dict["modifiers"]
                modifiers_list = modifiers_nodes if isinstance(modifiers_nodes, list) else [modifiers_nodes]
                modifiers = self._parse_modifiers(modifiers_list[0], source)

            # Extract method node for annotations
            method_node = None
            if "method" in captures_dict:
                method_nodes = captures_dict["method"]
                method_node_list = method_nodes if isinstance(method_nodes, list) else [method_nodes]
                method_node = method_node_list[0]

            annotations = self._extract_annotations(method_node, source) if method_node else []

            # Get method body
            body = ""
            if "body" in captures_dict:
                body_nodes = captures_dict["body"]
                body_list = body_nodes if isinstance(body_nodes, list) else [body_nodes]
                body = self.extractor.get_node_text(body_list[0], source)

            # Build signature
            param_str = ", ".join([f"{p.type} {p.name}" for p in parameters])
            signature = f"{return_type} {method_name}({param_str})"

            if method_node:
                methods.append(
                    JavaMethod(
                        name=method_name,
                        signature=signature,
                        return_type=return_type,
                        parameters=parameters,
                        modifiers=modifiers,
                        annotations=annotations,
                        body=body,
                        start_line=method_node.start_point[0] + 1,
                        end_line=method_node.end_point[0] + 1,
                    )
                )

        return methods

    def _parse_parameters(
        self, params_node: Node, source: str
    ) -> List[JavaParameter]:
        """
        Parse the formal parameter list of a method declaration.

        Handles annotated parameters (e.g., @PathVariable, @RequestBody) and
        extracts each parameter's type and name.  Varargs and spread parameters
        are treated as regular parameters.

        Args:
            params_node: The formal_parameters AST node
            source: The Java source code string

        Returns:
            List of JavaParameter objects; parameters without both type and name are skipped
        """
        parameters = []

        for child in params_node.children:
            if child.type == "formal_parameter":
                param_type = None
                param_name = None
                param_annotations = []

                # Check for annotations on parameter
                modifiers_node = self.extractor.find_child_by_type(child, "modifiers")
                if modifiers_node:
                    param_annotations = self._extract_annotations(child, source)

                for param_child in child.children:
                    if param_child.type in [
                        "type_identifier",
                        "generic_type",
                        "array_type",
                        "integral_type",
                        "floating_point_type",
                        "boolean_type",
                    ]:
                        param_type = self.extractor.get_node_text(param_child, source)
                    elif param_child.type == "identifier":
                        param_name = self.extractor.get_node_text(param_child, source)

                if param_type and param_name:
                    parameters.append(
                        JavaParameter(
                            name=param_name,
                            type=param_type,
                            annotations=param_annotations,
                        )
                    )

        return parameters

    def _categorize_class(
        self, class_name: str, annotations: List[JavaAnnotation], extends: Optional[str]
    ) -> str:
        """
        Determine the initial category of a class from annotations, name, and inheritance.

        Categories are later refined by ClassCategorizer; this method provides a fast
        first-pass classification directly from the AST without deeper analysis.

        Priority: annotation check → name pattern → inheritance check.

        Args:
            class_name: Simple name of the class
            annotations: List of class-level annotations already extracted
            extends: Superclass name, or None if the class has no explicit parent

        Returns:
            Category string: "Controller", "Service", "DAO", "Entity", "Config",
            "Component", "Util", or "Unknown"
        """
        annotation_names = [ann.name for ann in annotations]

        # Check annotations
        if any(a in annotation_names for a in ["RestController", "Controller"]):
            return "Controller"
        elif "Service" in annotation_names:
            return "Service"
        elif "Repository" in annotation_names:
            return "DAO"
        elif any(a in annotation_names for a in ["Entity", "Table"]):
            return "Entity"
        elif "Configuration" in annotation_names:
            return "Config"
        elif "Component" in annotation_names:
            return "Component"

        # Check naming patterns
        if "Controller" in class_name:
            return "Controller"
        elif "Service" in class_name:
            return "Service"
        elif any(x in class_name for x in ["Repository", "DAO", "Dao"]):
            return "DAO"
        elif any(x in class_name for x in ["Entity", "Model"]):
            return "Entity"
        elif any(x in class_name for x in ["Util", "Helper", "Utils"]):
            return "Util"
        elif "Config" in class_name or "Configuration" in class_name:
            return "Config"

        # Check inheritance
        if extends:
            if "JpaRepository" in extends or "CrudRepository" in extends:
                return "DAO"

        return "Unknown"
