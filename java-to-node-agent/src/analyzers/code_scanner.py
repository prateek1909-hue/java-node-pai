"""
Code scanner for discovering and parsing Java files in a repository.
"""

from pathlib import Path
from typing import List, Optional, Dict
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from src.parsers.tree_sitter_parser import TreeSitterJavaParser
from src.models.java_models import JavaClass


class CodeScanner:
    """Scans a Java repository and parses all Java files."""

    def __init__(self, repository_path: str) -> None:
        """
        Initialize the code scanner.

        Args:
            repository_path: Path to the Java repository to scan
        """
        self.repository_path = Path(repository_path)
        self.parser = TreeSitterJavaParser()
        self.console = Console()
        self.java_classes: List[JavaClass] = []
        self.errors: Dict[str, str] = {}

        if not self.repository_path.exists():
            raise ValueError(f"Repository path does not exist: {repository_path}")

        if not self.repository_path.is_dir():
            raise ValueError(f"Repository path is not a directory: {repository_path}")

    def find_java_files(self) -> List[Path]:
        """
        Recursively find all .java files in the repository.

        Returns:
            List of Path objects for all .java files found
        """
        java_files = list(self.repository_path.rglob("*.java"))

        # Filter out common directories to exclude
        excluded_dirs = {
            "target",
            "build",
            "out",
            ".git",
            "node_modules",
            ".idea",
            ".vscode",
        }

        filtered_files = []
        for file_path in java_files:
            # Check if any part of the path contains excluded directories
            if not any(excluded in file_path.parts for excluded in excluded_dirs):
                filtered_files.append(file_path)

        return filtered_files

    def scan_repository(self, verbose: bool = True) -> List[JavaClass]:
        """
        Scan the entire repository and parse all Java files.

        Args:
            verbose: Whether to show progress information

        Returns:
            List of JavaClass objects representing all parsed classes
        """
        java_files = self.find_java_files()

        if verbose:
            self.console.print(
                f"\n[bold cyan]Scanning repository:[/bold cyan] {self.repository_path}"
            )
            self.console.print(f"[green]Found {len(java_files)} Java files[/green]\n")

        if not java_files:
            self.console.print("[yellow]No Java files found in repository[/yellow]")
            return []

        # Parse all Java files with progress tracking
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
        ) as progress:
            task = progress.add_task(
                "[cyan]Parsing Java files...", total=len(java_files)
            )

            for file_path in java_files:
                try:
                    content = file_path.read_text(encoding="utf-8")
                    java_class = self.parser.parse_file(str(file_path), content)
                    self.java_classes.append(java_class)
                except Exception as e:
                    self.errors[str(file_path)] = str(e)
                    if verbose:
                        self.console.print(
                            f"[red]Error parsing {file_path.name}: {str(e)}[/red]"
                        )

                progress.update(task, advance=1)

        if verbose:
            self._print_summary()

        return self.java_classes

    def _print_summary(self) -> None:
        """Print a summary of the scanning results."""
        self.console.print("\n[bold green]Scanning Complete[/bold green]")
        self.console.print(f"Successfully parsed: [green]{len(self.java_classes)}[/green] classes")

        if self.errors:
            self.console.print(f"Errors encountered: [red]{len(self.errors)}[/red] files")

        # Categorize and count classes
        categories: Dict[str, int] = {}
        types: Dict[str, int] = {}

        for java_class in self.java_classes:
            categories[java_class.category] = categories.get(java_class.category, 0) + 1
            types[java_class.type] = types.get(java_class.type, 0) + 1

        if categories:
            self.console.print("\n[bold cyan]Classes by Category:[/bold cyan]")
            for category, count in sorted(categories.items()):
                self.console.print(f"  {category}: [cyan]{count}[/cyan]")

        if types:
            self.console.print("\n[bold cyan]Classes by Type:[/bold cyan]")
            for type_name, count in sorted(types.items()):
                self.console.print(f"  {type_name}: [cyan]{count}[/cyan]")

    def get_classes_by_category(self, category: str) -> List[JavaClass]:
        """
        Get all classes of a specific category.

        Args:
            category: The category to filter by (e.g., "Controller", "Service")

        Returns:
            List of JavaClass objects in the specified category
        """
        return [cls for cls in self.java_classes if cls.category == category]

    def get_classes_by_type(self, type_name: str) -> List[JavaClass]:
        """
        Get all classes of a specific type.

        Args:
            type_name: The type to filter by (e.g., "class", "interface")

        Returns:
            List of JavaClass objects of the specified type
        """
        return [cls for cls in self.java_classes if cls.type == type_name]

    def get_class_by_name(self, name: str) -> Optional[JavaClass]:
        """
        Get a class by its name.

        Args:
            name: The class name to search for

        Returns:
            JavaClass object if found, None otherwise
        """
        for java_class in self.java_classes:
            if java_class.name == name:
                return java_class
        return None

    def get_controllers(self) -> List[JavaClass]:
        """Get all controller classes."""
        return self.get_classes_by_category("Controller")

    def get_services(self) -> List[JavaClass]:
        """Get all service classes."""
        return self.get_classes_by_category("Service")

    def get_repositories(self) -> List[JavaClass]:
        """Get all repository/DAO classes."""
        return self.get_classes_by_category("DAO")

    def get_entities(self) -> List[JavaClass]:
        """Get all entity classes."""
        return self.get_classes_by_category("Entity")

    def get_statistics(self) -> Dict:
        """
        Get detailed statistics about the scanned codebase.

        Returns:
            Dictionary containing various statistics
        """
        total_methods = sum(len(cls.methods) for cls in self.java_classes)
        total_fields = sum(len(cls.fields) for cls in self.java_classes)

        return {
            "total_files": len(self.java_classes) + len(self.errors),
            "parsed_successfully": len(self.java_classes),
            "parsing_errors": len(self.errors),
            "total_classes": len([cls for cls in self.java_classes if cls.type == "class"]),
            "total_interfaces": len([cls for cls in self.java_classes if cls.type == "interface"]),
            "total_enums": len([cls for cls in self.java_classes if cls.type == "enum"]),
            "total_methods": total_methods,
            "total_fields": total_fields,
            "controllers": len(self.get_controllers()),
            "services": len(self.get_services()),
            "repositories": len(self.get_repositories()),
            "entities": len(self.get_entities()),
            "categories": self._get_category_counts(),
        }

    def _get_category_counts(self) -> Dict[str, int]:
        """Get counts of classes by category."""
        categories: Dict[str, int] = {}
        for java_class in self.java_classes:
            categories[java_class.category] = categories.get(java_class.category, 0) + 1
        return categories
