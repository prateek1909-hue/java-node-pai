"""
LangGraph workflow definition for Java-to-Node.js conversion.
"""

from langgraph.graph import StateGraph, END
from src.graph.state import ConversionState
from src.graph import nodes


def create_conversion_workflow() -> StateGraph:
    """
    Create and configure the LangGraph workflow for Java-to-Node.js conversion.

    Steps:
    1. Scan codebase (parse Java files)
    2. Categorize classes (Controller, Service, Entity, etc.)
    3. Analyze dependencies (build dependency graph)
    4. Design architecture (determine target structure)
    5. Generate domain layer (entities, repositories, DTOs)
    6. Generate application layer (use cases)
    7. Generate infrastructure layer (database config)
    8. Generate presentation layer (controllers, routes)
    9. Generate config files (package.json, tsconfig, etc.)
    10. Write outputs (write all files to disk)
    """
    workflow = StateGraph(ConversionState)

    # Phase 1: Scanning & Analysis
    workflow.add_node("scan_codebase", nodes.scan_codebase)
    workflow.add_node("categorize_classes", nodes.categorize_classes)
    workflow.add_node("analyze_dependencies", nodes.analyze_dependencies)

    # Phase 2: Architecture Design
    workflow.add_node("design_architecture", nodes.design_architecture)

    # Phase 3: Code Generation
    workflow.add_node("generate_domain_layer", nodes.generate_domain_layer)
    workflow.add_node("generate_application_layer", nodes.generate_application_layer)
    workflow.add_node("generate_infrastructure_layer", nodes.generate_infrastructure_layer)
    workflow.add_node("generate_presentation_layer", nodes.generate_presentation_layer)
    workflow.add_node("generate_config_files", nodes.generate_config_files)

    # Phase 4: Output
    workflow.add_node("write_outputs", nodes.write_outputs)

    # Edges
    workflow.set_entry_point("scan_codebase")
    workflow.add_edge("scan_codebase", "categorize_classes")
    workflow.add_edge("categorize_classes", "analyze_dependencies")
    workflow.add_edge("analyze_dependencies", "design_architecture")
    workflow.add_edge("design_architecture", "generate_domain_layer")
    workflow.add_edge("generate_domain_layer", "generate_application_layer")
    workflow.add_edge("generate_application_layer", "generate_infrastructure_layer")
    workflow.add_edge("generate_infrastructure_layer", "generate_presentation_layer")
    workflow.add_edge("generate_presentation_layer", "generate_config_files")
    workflow.add_edge("generate_config_files", "write_outputs")
    workflow.add_edge("write_outputs", END)

    return workflow.compile()


def create_workflow_with_checkpoints(checkpoint_dir: str = "./.checkpoints") -> StateGraph:
    """
    Create a conversion workflow with SQLite-backed checkpointing for resumability.

    If the workflow is interrupted (e.g., due to an LLM timeout), it can be resumed
    from the last completed node by re-invoking with the same thread_id.  Checkpoint
    data is stored in a SQLite database inside checkpoint_dir.

    Args:
        checkpoint_dir: Directory where the SQLite checkpoint database is stored.
            Created automatically if it does not exist.

    Returns:
        Compiled StateGraph with checkpointing enabled
    """
    from langgraph.checkpoint.sqlite import SqliteSaver
    from pathlib import Path

    Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
    checkpointer = SqliteSaver.from_conn_string(f"{checkpoint_dir}/checkpoints.db")

    workflow = StateGraph(ConversionState)

    workflow.add_node("scan_codebase", nodes.scan_codebase)
    workflow.add_node("categorize_classes", nodes.categorize_classes)
    workflow.add_node("analyze_dependencies", nodes.analyze_dependencies)
    workflow.add_node("design_architecture", nodes.design_architecture)
    workflow.add_node("generate_domain_layer", nodes.generate_domain_layer)
    workflow.add_node("generate_application_layer", nodes.generate_application_layer)
    workflow.add_node("generate_infrastructure_layer", nodes.generate_infrastructure_layer)
    workflow.add_node("generate_presentation_layer", nodes.generate_presentation_layer)
    workflow.add_node("generate_config_files", nodes.generate_config_files)
    workflow.add_node("write_outputs", nodes.write_outputs)

    workflow.set_entry_point("scan_codebase")
    workflow.add_edge("scan_codebase", "categorize_classes")
    workflow.add_edge("categorize_classes", "analyze_dependencies")
    workflow.add_edge("analyze_dependencies", "design_architecture")
    workflow.add_edge("design_architecture", "generate_domain_layer")
    workflow.add_edge("generate_domain_layer", "generate_application_layer")
    workflow.add_edge("generate_application_layer", "generate_infrastructure_layer")
    workflow.add_edge("generate_infrastructure_layer", "generate_presentation_layer")
    workflow.add_edge("generate_presentation_layer", "generate_config_files")
    workflow.add_edge("generate_config_files", "write_outputs")
    workflow.add_edge("write_outputs", END)

    return workflow.compile(checkpointer=checkpointer)


# Create default workflow instance
conversion_workflow = create_conversion_workflow()

__all__ = [
    "create_conversion_workflow",
    "create_workflow_with_checkpoints",
    "conversion_workflow",
]
