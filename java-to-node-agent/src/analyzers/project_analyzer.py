"""
Project analyzer that orchestrates the complete analysis of a Java codebase.
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree

from src.analyzers.code_scanner import CodeScanner
from src.analyzers.class_categorizer import ClassCategorizer
from src.analyzers.dependency_mapper import DependencyMapper, DependencyGraph
from src.models.java_models import JavaClass


@dataclass
class ProjectAnalysis:
    """Complete analysis results for a Java project."""

    project_path: str
    java_classes: List[JavaClass]
    dependency_graph: DependencyGraph
    statistics: Dict
    categories: Dict[str, List[JavaClass]]


class ProjectAnalyzer:
    """
    Orchestrates the complete analysis of a Java project.
    Combines scanning, categorization, and dependency mapping.
    """

    def __init__(self, repository_path: str) -> None:
        """
        Initialize the project analyzer.

        Args:
            repository_path: Path to the Java repository to analyze
        """
        self.repository_path = Path(repository_path)
        self.console = Console()
        self.scanner = CodeScanner(str(self.repository_path))
        self.categorizer = ClassCategorizer()
        self.dependency_mapper: Optional[DependencyMapper] = None
        self.analysis: Optional[ProjectAnalysis] = None

    def analyze(self, verbose: bool = True) -> ProjectAnalysis:
        """
        Perform complete analysis of the Java project.

        Args:
            verbose: Whether to show progress and results

        Returns:
            ProjectAnalysis object containing all analysis results
        """
        if verbose:
            self.console.print(
                Panel.fit(
                    f"[bold cyan]Analyzing Java Project[/bold cyan]\n"
                    f"Path: {self.repository_path}",
                    border_style="cyan",
                )
            )

        # Step 1: Scan and parse all Java files
        if verbose:
            self.console.print("\n[bold]Step 1:[/bold] Scanning Java files...")

        java_classes = self.scanner.scan_repository(verbose=verbose)

        if not java_classes:
            self.console.print("[yellow]No Java classes found. Analysis stopped.[/yellow]")
            return ProjectAnalysis(
                project_path=str(self.repository_path),
                java_classes=[],
                dependency_graph=DependencyGraph(dependencies=[], class_map={}),
                statistics={},
                categories={},
            )

        # Step 2: Enhanced categorization
        if verbose:
            self.console.print("\n[bold]Step 2:[/bold] Categorizing classes...")

        self._categorize_classes(java_classes, verbose=verbose)

        # Step 3: Map dependencies
        if verbose:
            self.console.print("\n[bold]Step 3:[/bold] Mapping dependencies...")

        self.dependency_mapper = DependencyMapper(java_classes)
        dependency_graph = self.dependency_mapper.map_dependencies()

        if verbose:
            self.console.print(
                f"[green]Found {len(dependency_graph.dependencies)} dependencies[/green]"
            )

        # Step 4: Gather statistics
        if verbose:
            self.console.print("\n[bold]Step 4:[/bold] Gathering statistics...")

        statistics = self._gather_statistics(java_classes, dependency_graph)

        # Step 5: Categorize classes
        categories = self._group_by_category(java_classes)

        # Create analysis result
        self.analysis = ProjectAnalysis(
            project_path=str(self.repository_path),
            java_classes=java_classes,
            dependency_graph=dependency_graph,
            statistics=statistics,
            categories=categories,
        )

        if verbose:
            self._print_analysis_summary()

        return self.analysis

    def _categorize_classes(
        self, java_classes: List[JavaClass], verbose: bool = False
    ) -> None:
        """Apply enhanced categorization to all classes."""
        recategorized = 0

        for java_class in java_classes:
            original_category = java_class.category
            new_category = self.categorizer.categorize(java_class)

            if new_category != original_category:
                java_class.category = new_category
                recategorized += 1

        if verbose and recategorized > 0:
            self.console.print(
                f"[green]Recategorized {recategorized} classes with enhanced analysis[/green]"
            )

    def _gather_statistics(
        self, java_classes: List[JavaClass], dependency_graph: DependencyGraph
    ) -> Dict:
        """Gather comprehensive statistics about the project."""
        scanner_stats = self.scanner.get_statistics()
        dep_stats = self.dependency_mapper.get_dependency_statistics() if self.dependency_mapper else {}

        # Additional statistics
        total_annotations = sum(len(cls.annotations) for cls in java_classes)
        total_rest_endpoints = sum(
            len([m for m in cls.methods if any(
                ann.name in {"GetMapping", "PostMapping", "PutMapping", "DeleteMapping", "RequestMapping"}
                for ann in m.annotations
            )])
            for cls in java_classes
        )

        return {
            **scanner_stats,
            **dep_stats,
            "total_annotations": total_annotations,
            "total_rest_endpoints": total_rest_endpoints,
        }

    def _group_by_category(self, java_classes: List[JavaClass]) -> Dict[str, List[JavaClass]]:
        """Group classes by their category."""
        categories: Dict[str, List[JavaClass]] = {}

        for java_class in java_classes:
            category = java_class.category
            if category not in categories:
                categories[category] = []
            categories[category].append(java_class)

        return categories

    def _print_analysis_summary(self) -> None:
        """Print a comprehensive summary of the analysis."""
        if not self.analysis:
            return

        self.console.print("\n")
        self.console.print(
            Panel.fit(
                "[bold green]Analysis Complete[/bold green]",
                border_style="green",
            )
        )

        # Print statistics table
        self._print_statistics_table()

        # Print category breakdown
        self._print_category_tree()

        # Print dependency insights
        self._print_dependency_insights()

    def _print_statistics_table(self) -> None:
        """Print a table of project statistics."""
        if not self.analysis:
            return

        stats = self.analysis.statistics

        table = Table(title="Project Statistics", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="green")

        table.add_row("Total Files", str(stats.get("total_files", 0)))
        table.add_row("Parsed Successfully", str(stats.get("parsed_successfully", 0)))
        table.add_row("Total Classes", str(stats.get("total_classes", 0)))
        table.add_row("Total Interfaces", str(stats.get("total_interfaces", 0)))
        table.add_row("Total Enums", str(stats.get("total_enums", 0)))
        table.add_row("Total Methods", str(stats.get("total_methods", 0)))
        table.add_row("Total Fields", str(stats.get("total_fields", 0)))
        table.add_row("Total Annotations", str(stats.get("total_annotations", 0)))
        table.add_row("REST Endpoints", str(stats.get("total_rest_endpoints", 0)))
        table.add_row("Total Dependencies", str(stats.get("total_dependencies", 0)))
        table.add_row("Injection Dependencies", str(stats.get("injection_dependencies", 0)))

        self.console.print()
        self.console.print(table)

    def _print_category_tree(self) -> None:
        """Print a tree view of classes by category."""
        if not self.analysis:
            return

        tree = Tree("[bold cyan]Classes by Category[/bold cyan]")

        for category, classes in sorted(self.analysis.categories.items()):
            category_node = tree.add(f"[yellow]{category}[/yellow] ({len(classes)})")

            # Show up to 5 classes per category
            for java_class in classes[:5]:
                category_node.add(f"[green]{java_class.name}[/green]")

            if len(classes) > 5:
                category_node.add(f"[dim]... and {len(classes) - 5} more[/dim]")

        self.console.print()
        self.console.print(tree)

    def _print_dependency_insights(self) -> None:
        """Print insights about dependencies."""
        if not self.analysis or not self.dependency_mapper:
            return

        stats = self.analysis.statistics

        self.console.print()
        self.console.print("[bold cyan]Dependency Insights:[/bold cyan]")

        # Most dependent classes
        most_dependent = stats.get("most_dependent_classes", [])
        if most_dependent:
            self.console.print("\n[yellow]Most Dependent Classes (highest outgoing dependencies):[/yellow]")
            for class_name, count in most_dependent:
                self.console.print(f"  • {class_name}: [cyan]{count}[/cyan] dependencies")

        # Most depended upon classes
        most_depended = stats.get("most_depended_upon_classes", [])
        if most_depended:
            self.console.print("\n[yellow]Most Depended Upon Classes (highest incoming dependencies):[/yellow]")
            for class_name, count in most_depended:
                self.console.print(f"  • {class_name}: [cyan]{count}[/cyan] dependents")

        # Circular dependencies
        circular_count = stats.get("circular_dependencies", 0)
        if circular_count > 0:
            self.console.print(
                f"\n[red]Warning: Found {circular_count} circular dependency cycles[/red]"
            )

    def get_controllers(self) -> List[JavaClass]:
        """Get all controller classes."""
        return self.analysis.categories.get("Controller", []) if self.analysis else []

    def get_services(self) -> List[JavaClass]:
        """Get all service classes."""
        return self.analysis.categories.get("Service", []) if self.analysis else []

    def get_repositories(self) -> List[JavaClass]:
        """Get all repository/DAO classes."""
        return self.analysis.categories.get("DAO", []) if self.analysis else []

    def get_entities(self) -> List[JavaClass]:
        """Get all entity classes."""
        return self.analysis.categories.get("Entity", []) if self.analysis else []

    def export_analysis(self, output_path: str) -> None:
        """
        Export the analysis results to a JSON file.

        Args:
            output_path: Path to save the JSON output
        """
        if not self.analysis:
            raise ValueError("No analysis has been performed yet. Call analyze() first.")

        import json

        output_data = {
            "project_path": self.analysis.project_path,
            "statistics": self.analysis.statistics,
            "categories": {
                category: [cls.model_dump() for cls in classes]
                for category, classes in self.analysis.categories.items()
            },
            "dependencies": [
                {
                    "from": dep.from_class,
                    "to": dep.to_class,
                    "type": dep.dependency_type,
                    "field_name": dep.field_name,
                    "method_name": dep.method_name,
                }
                for dep in self.analysis.dependency_graph.dependencies
            ],
        }

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with output_file.open("w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)

        self.console.print(f"\n[green]Analysis exported to: {output_path}[/green]")
