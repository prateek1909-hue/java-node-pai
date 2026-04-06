"""
Tree-sitter query patterns for Java code parsing.
These queries extract specific syntax elements from the Java AST.
"""

from tree_sitter import Language, Query
import tree_sitter_java as tsjava


class JavaQueries:
    """Predefined tree-sitter queries for Java parsing."""

    def __init__(self) -> None:
        """Initialize the Java language and all queries."""
        self.language = Language(tsjava.language())
        self._init_queries()

    def _init_queries(self) -> None:
        """Initialize all query patterns."""

        # Package declaration query
        self.package_query = Query(
            self.language,
            """
            (package_declaration
                (scoped_identifier) @package_name
            ) @package
            """
        )

        # Import declaration query
        self.import_query = Query(
            self.language,
            """
            (import_declaration
                [
                    (scoped_identifier) @import_path
                    (asterisk) @wildcard
                ]
            ) @import
            """
        )

        # Class declaration query
        self.class_query = Query(
            self.language,
            """
            (class_declaration
                (modifiers)? @modifiers
                name: (identifier) @class_name
                (type_parameters)? @type_params
                (superclass)? @superclass
                (super_interfaces)? @interfaces
                body: (class_body) @body
            ) @class
            """
        )

        # Interface declaration query
        self.interface_query = Query(
            self.language,
            """
            (interface_declaration
                (modifiers)? @modifiers
                name: (identifier) @interface_name
                (type_parameters)? @type_params
                (extends_interfaces)? @extends
                body: (interface_body) @body
            ) @interface
            """
        )

        # Enum declaration query
        self.enum_query = Query(
            self.language,
            """
            (enum_declaration
                (modifiers)? @modifiers
                name: (identifier) @enum_name
                (super_interfaces)? @interfaces
                body: (enum_body) @body
            ) @enum
            """
        )

        # Method declaration query
        self.method_query = Query(
            self.language,
            """
            (method_declaration
                (modifiers)? @modifiers
                (type_parameters)? @type_params
                type: (_) @return_type
                name: (identifier) @method_name
                parameters: (formal_parameters) @params
                (throws)? @throws
                body: (block)? @body
            ) @method
            """
        )

        # Constructor declaration query
        self.constructor_query = Query(
            self.language,
            """
            (constructor_declaration
                (modifiers)? @modifiers
                name: (identifier) @constructor_name
                parameters: (formal_parameters) @params
                (throws)? @throws
                body: (constructor_body) @body
            ) @constructor
            """
        )

        # Field declaration query
        self.field_query = Query(
            self.language,
            """
            (field_declaration
                (modifiers)? @modifiers
                type: (_) @field_type
                declarator: (variable_declarator
                    name: (identifier) @field_name
                    value: (_)? @initializer
                )
            ) @field
            """
        )

        # Annotation query (both marker and full annotations)
        self.annotation_query = Query(
            self.language,
            """
            [
                (marker_annotation
                    name: [
                        (identifier) @annotation_name
                        (scoped_identifier) @annotation_name
                    ]
                ) @annotation
                (annotation
                    name: [
                        (identifier) @annotation_name
                        (scoped_identifier) @annotation_name
                    ]
                    arguments: (annotation_argument_list)? @args
                ) @annotation
            ]
            """
        )

        # Modifier query
        self.modifier_query = Query(
            self.language,
            """
            (modifiers
                [
                    "public" @modifier
                    "private" @modifier
                    "protected" @modifier
                    "static" @modifier
                    "final" @modifier
                    "abstract" @modifier
                    "synchronized" @modifier
                    "volatile" @modifier
                    "transient" @modifier
                    "native" @modifier
                    "strictfp" @modifier
                    "default" @modifier
                ]
            )
            """
        )

        # Parameter query
        self.parameter_query = Query(
            self.language,
            """
            (formal_parameter
                (modifiers)? @param_modifiers
                type: (_) @param_type
                name: (identifier) @param_name
            ) @parameter
            """
        )

        # Superclass query
        self.superclass_query = Query(
            self.language,
            """
            (superclass
                (type_identifier) @superclass_name
            )
            """
        )

        # Interface implementation query
        self.implements_query = Query(
            self.language,
            """
            (super_interfaces
                (type_list
                    [
                        (type_identifier) @interface_name
                        (generic_type
                            (type_identifier) @interface_name
                        )
                    ]
                )
            )
            """
        )

        # Generic type query
        self.generic_query = Query(
            self.language,
            """
            (generic_type
                (type_identifier) @base_type
                (type_arguments
                    (type_identifier) @type_arg
                )
            )
            """
        )

    def get_package_query(self) -> Query:
        """Get the package declaration query."""
        return self.package_query

    def get_import_query(self) -> Query:
        """Get the import declaration query."""
        return self.import_query

    def get_class_query(self) -> Query:
        """Get the class declaration query."""
        return self.class_query

    def get_interface_query(self) -> Query:
        """Get the interface declaration query."""
        return self.interface_query

    def get_enum_query(self) -> Query:
        """Get the enum declaration query."""
        return self.enum_query

    def get_method_query(self) -> Query:
        """Get the method declaration query."""
        return self.method_query

    def get_constructor_query(self) -> Query:
        """Get the constructor declaration query."""
        return self.constructor_query

    def get_field_query(self) -> Query:
        """Get the field declaration query."""
        return self.field_query

    def get_annotation_query(self) -> Query:
        """Get the annotation query."""
        return self.annotation_query

    def get_modifier_query(self) -> Query:
        """Get the modifier query."""
        return self.modifier_query

    def get_parameter_query(self) -> Query:
        """Get the parameter query."""
        return self.parameter_query

    def get_superclass_query(self) -> Query:
        """Get the superclass query."""
        return self.superclass_query

    def get_implements_query(self) -> Query:
        """Get the implements query."""
        return self.implements_query

    def get_generic_query(self) -> Query:
        """Get the generic type query."""
        return self.generic_query
