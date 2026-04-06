"""
Base generator class with common utilities for code generation.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from pathlib import Path
import re


class BaseGenerator(ABC):
    """
    Abstract base class for all code generators.

    Provides common utilities for:
    - Code formatting
    - File path generation
    - Template rendering
    - TypeScript/JavaScript helpers
    """

    def __init__(self, output_dir: str = "./output", language: str = "typescript"):
        """
        Initialize the base generator.

        Args:
            output_dir: Root directory for generated code
            language: Output language ('typescript' or 'javascript')
        """
        self.output_dir = Path(output_dir)
        self.language = language
        self.file_extension = ".js" if language == "javascript" else ".ts"

    @abstractmethod
    def generate(self) -> Dict[str, str]:
        """
        Generate code files.

        Returns:
            Dictionary mapping file paths to file contents
        """
        pass

    # ============================================================
    # Formatting Utilities
    # ============================================================

    def format_typescript(self, code: str) -> str:
        """
        Format TypeScript code with proper indentation.

        Args:
            code: Raw TypeScript code

        Returns:
            Formatted code
        """
        # Remove leading/trailing whitespace
        lines = code.strip().split('\n')

        # Remove common leading whitespace
        if lines:
            # Find minimum indentation (excluding empty lines)
            min_indent = float('inf')
            for line in lines:
                if line.strip():
                    indent = len(line) - len(line.lstrip())
                    min_indent = min(min_indent, indent)

            if min_indent < float('inf'):
                lines = [line[min_indent:] if line.strip() else '' for line in lines]

        return '\n'.join(lines)

    def indent(self, text: str, spaces: int = 2) -> str:
        """
        Indent text by specified number of spaces.

        Args:
            text: Text to indent
            spaces: Number of spaces to indent

        Returns:
            Indented text
        """
        indent_str = ' ' * spaces
        return '\n'.join(indent_str + line if line.strip() else line
                        for line in text.split('\n'))

    def to_camel_case(self, snake_str: str) -> str:
        """
        Convert snake_case to camelCase.

        Args:
            snake_str: String in snake_case

        Returns:
            String in camelCase
        """
        components = snake_str.split('_')
        return components[0] + ''.join(x.title() for x in components[1:])

    def to_pascal_case(self, snake_str: str) -> str:
        """
        Convert snake_case to PascalCase.

        Args:
            snake_str: String in snake_case

        Returns:
            String in PascalCase
        """
        return ''.join(x.title() for x in snake_str.split('_'))

    def to_kebab_case(self, text: str) -> str:
        """
        Convert text to kebab-case.

        Args:
            text: Input text

        Returns:
            String in kebab-case
        """
        # Replace spaces and underscores with hyphens
        text = re.sub(r'[\s_]+', '-', text)
        # Insert hyphen before capital letters
        text = re.sub(r'([a-z])([A-Z])', r'\1-\2', text)
        return text.lower()

    # ============================================================
    # TypeScript Type Mapping
    # ============================================================

    def map_java_type_to_typescript(self, java_type: str) -> str:
        """
        Map Java type to TypeScript type.

        Args:
            java_type: Java type string

        Returns:
            TypeScript type string
        """
        # Handle generics
        if '<' in java_type:
            # Extract base type and generic parameter
            base = java_type.split('<')[0].strip()
            generic = java_type.split('<')[1].split('>')[0].strip()

            # Map base type
            base_mapped = self._map_simple_type(base)
            generic_mapped = self.map_java_type_to_typescript(generic)

            # Handle common generic types
            if base in ['List', 'ArrayList', 'Set', 'HashSet', 'Collection']:
                return f"{generic_mapped}[]"
            elif base in ['Map', 'HashMap']:
                return f"Record<string, {generic_mapped}>"
            elif base == 'Optional':
                return f"{generic_mapped} | null"
            else:
                return f"{base_mapped}<{generic_mapped}>"

        return self._map_simple_type(java_type)

    def _map_simple_type(self, java_type: str) -> str:
        """Map simple Java type to TypeScript type."""
        type_map = {
            # Primitives
            'int': 'number',
            'Integer': 'number',
            'long': 'number',
            'Long': 'number',
            'double': 'number',
            'Double': 'number',
            'float': 'number',
            'Float': 'number',
            'boolean': 'boolean',
            'Boolean': 'boolean',
            'char': 'string',
            'Character': 'string',
            'String': 'string',
            'byte': 'number',
            'Byte': 'number',
            'short': 'number',
            'Short': 'number',

            # Date/Time
            'Date': 'Date',
            'LocalDate': 'Date',
            'LocalDateTime': 'Date',
            'Instant': 'Date',

            # Collections (fallback for non-generic)
            'List': 'any[]',
            'Set': 'any[]',
            'Map': 'Record<string, any>',

            # Other
            'Object': 'any',
            'void': 'void',
            'Void': 'void',
        }

        return type_map.get(java_type, java_type)

    # ============================================================
    # File Path Utilities
    # ============================================================

    def get_entity_path(self, entity_name: str) -> str:
        """
        Get file path for a domain entity.

        Args:
            entity_name: Name of the entity

        Returns:
            Relative file path
        """
        filename = self.to_kebab_case(entity_name)
        return f"src/domain/entities/{filename}.entity{self.file_extension}"

    def get_repository_interface_path(self, entity_name: str) -> str:
        """
        Get file path for a repository interface.

        Args:
            entity_name: Name of the entity

        Returns:
            Relative file path
        """
        filename = self.to_kebab_case(entity_name)
        return f"src/domain/repositories/{filename}.repository{self.file_extension}"

    def get_repository_impl_path(self, entity_name: str) -> str:
        """
        Get file path for a repository implementation.

        Args:
            entity_name: Name of the entity

        Returns:
            Relative file path
        """
        filename = self.to_kebab_case(entity_name)
        return f"src/infrastructure/repositories/{filename}.repository{self.file_extension}"

    def get_use_case_path(self, use_case_name: str) -> str:
        """
        Get file path for a use case.

        Args:
            use_case_name: Name of the use case

        Returns:
            Relative file path
        """
        filename = self.to_kebab_case(use_case_name)
        return f"src/application/use-cases/{filename}.use-case{self.file_extension}"

    def get_dto_path(self, dto_name: str) -> str:
        """
        Get file path for a DTO.

        Args:
            dto_name: Name of the DTO

        Returns:
            Relative file path
        """
        filename = self.to_kebab_case(dto_name)
        return f"src/application/dtos/{filename}.dto{self.file_extension}"

    def get_controller_path(self, controller_name: str) -> str:
        """
        Get file path for a controller.

        Args:
            controller_name: Name of the controller

        Returns:
            Relative file path
        """
        filename = self.to_kebab_case(controller_name)
        return f"src/presentation/controllers/{filename}.controller{self.file_extension}"

    # ============================================================
    # Template Rendering
    # ============================================================

    def render_imports(self, imports: List[Dict[str, str]]) -> str:
        """
        Render TypeScript import statements.

        Args:
            imports: List of import dicts with 'names' and 'from' keys

        Returns:
            Formatted import statements
        """
        if not imports:
            return ""

        lines = []
        for imp in imports:
            names = imp.get('names', [])
            from_path = imp.get('from', '')

            if isinstance(names, list):
                names_str = ', '.join(names)
                lines.append(f"import {{ {names_str} }} from '{from_path}';")
            else:
                lines.append(f"import {names} from '{from_path}';")

        return '\n'.join(lines)

    def render_class_header(
        self,
        class_name: str,
        decorators: Optional[List[str]] = None,
        extends: Optional[str] = None,
        implements: Optional[List[str]] = None,
        is_export: bool = True,
        is_abstract: bool = False,
    ) -> str:
        """
        Render TypeScript class header.

        Args:
            class_name: Name of the class
            decorators: List of decorator strings
            extends: Parent class name
            implements: List of interface names
            is_export: Whether to export the class
            is_abstract: Whether the class is abstract

        Returns:
            Formatted class header
        """
        lines = []

        # Add decorators
        if decorators:
            for decorator in decorators:
                lines.append(decorator)

        # Build class declaration
        parts = []
        if is_export:
            parts.append('export')
        if is_abstract:
            parts.append('abstract')
        parts.append('class')
        parts.append(class_name)

        if extends:
            parts.append(f'extends {extends}')

        if implements:
            parts.append(f"implements {', '.join(implements)}")

        lines.append(' '.join(parts) + ' {')

        return '\n'.join(lines)

    def wrap_in_try_catch(self, code: str, error_message: str = "Operation failed") -> str:
        """
        Wrap code in try-catch block.

        Args:
            code: Code to wrap
            error_message: Error message prefix

        Returns:
            Code wrapped in try-catch
        """
        return f"""try {{
{self.indent(code, 2)}
}} catch (error) {{
  throw new Error('{error_message}: ' + (error as Error).message);
}}"""
