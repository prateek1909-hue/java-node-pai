"""
LangGraph State Definition for Java-to-Node.js Conversion Workflow.

This module defines the shared state structure that flows through all workflow nodes.
"""

from typing import TypedDict, List, Dict, Optional, Any
from src.models.java_models import JavaClass
from src.models.architecture_models import ModernArchitecture


class ConversionState(TypedDict, total=False):
    """
    State object that flows through the LangGraph workflow.

    This state is updated by each node and passed to the next.
    Using total=False allows optional fields.
    """

    # ============================================================
    # Repository Information
    # ============================================================
    repo_url: Optional[str]  # Git repository URL
    repo_path: str  # Local path to repository (cloned or provided)
    branch: Optional[str]  # Git branch to analyze

    # ============================================================
    # User-Selected Files (from UI)
    # ============================================================
    selected_file_paths: List[str]  # Absolute paths the user chose in the UI

    # ============================================================
    # Scanned Files & Classes
    # ============================================================
    java_files: List[str]  # List of Java file paths found
    java_classes: List[JavaClass]  # Parsed Java class objects
    total_files: int  # Total number of Java files
    parsed_files: int  # Successfully parsed files
    parse_errors: List[Dict[str, str]]  # Parse errors with file path and error message

    # ============================================================
    # Categorization & Dependencies
    # ============================================================
    classes_by_category: Dict[str, List[JavaClass]]  # Grouped by Controller, Service, etc.
    selected_source_classes: Dict[str, str]  # Selected source class names by role
    selected_source_class_files: Dict[str, str]  # Selected source class file paths by role
    selected_source_class_details: Dict[str, Dict[str, Any]]  # Extended selected class metadata
    dependency_graph: Dict[str, List[str]]  # Class-to-class dependencies
    circular_dependencies: List[List[str]]  # Detected circular dependency chains

    # ============================================================
    # Architecture Design
    # ============================================================
    architecture: Optional[ModernArchitecture]  # Target architecture design
    target_framework: str  # express, nestjs, etc.
    target_orm: str  # typeorm, sequelize, prisma

    # ============================================================
    # Generated Code
    # ============================================================
    generated_files: Dict[str, str]  # Map of file_path -> file_content
    output_directory: str  # Where to write generated files

    # ============================================================
    # Metadata & Tracking
    # ============================================================
    current_step: str  # Current workflow step (for debugging)
    errors: List[Dict[str, Any]]  # Errors encountered during workflow
    warnings: List[str]  # Non-fatal warnings
    start_time: Optional[float]  # Workflow start timestamp
    end_time: Optional[float]  # Workflow end timestamp

    # ============================================================
    # Configuration
    # ============================================================
    llm_provider: str  # openai, azure_openai, anthropic
    verbose: bool  # Enable detailed logging
    skip_tests: bool  # Whether to skip test files during scanning


def create_initial_state(
    repo_path: str,
    output_directory: str = "./output",
    repo_url: Optional[str] = None,
    branch: Optional[str] = None,
    target_framework: str = "express",
    target_orm: str = "typeorm",
    llm_provider: str = "openai",
    verbose: bool = False,
    skip_tests: bool = True,
    selected_file_paths: Optional[List[str]] = None,
) -> ConversionState:
    """
    Create the initial state for the workflow.

    Args:
        repo_path: Local path to Java repository
        output_directory: Where to write generated Node.js code
        repo_url: Optional Git URL (if cloning)
        branch: Optional Git branch
        target_framework: Target Node.js framework (express, nestjs)
        target_orm: Target ORM (typeorm, sequelize, prisma)
        llm_provider: LLM provider to use
        verbose: Enable verbose logging
        skip_tests: Skip test files during scanning

    Returns:
        Initial ConversionState object
    """
    import time

    return ConversionState(
        # Repository
        repo_path=repo_path,
        repo_url=repo_url,
        branch=branch,

        # User selection from UI (empty list means "let workflow auto-select")
        selected_file_paths=selected_file_paths or [],

        # Scanned files (initialized empty)
        java_files=[],
        java_classes=[],
        total_files=0,
        parsed_files=0,
        parse_errors=[],

        # Categorization (initialized empty)
        classes_by_category={},
        selected_source_classes={},
        selected_source_class_files={},
        selected_source_class_details={},
        dependency_graph={},
        circular_dependencies=[],

        # Architecture (not yet designed)
        architecture=None,
        target_framework=target_framework,
        target_orm=target_orm,

        # Generated code (empty initially)
        generated_files={},
        output_directory=output_directory,

        # Metadata
        current_step="initialization",
        errors=[],
        warnings=[],
        start_time=time.time(),
        end_time=None,

        # Configuration
        llm_provider=llm_provider,
        verbose=verbose,
        skip_tests=skip_tests,
    )
