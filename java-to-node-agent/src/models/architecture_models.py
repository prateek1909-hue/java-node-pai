"""
Pydantic models representing modern architecture design decisions.
These models define the structure of the generated Node.js/TypeScript application.
"""

from typing import List, Dict, Optional
from enum import Enum
from pydantic import BaseModel, Field


class ArchitecturePattern(str, Enum):
    """Supported architecture patterns."""

    CLEAN_ARCHITECTURE = "clean_architecture"
    HEXAGONAL = "hexagonal"
    ONION = "onion"
    LAYERED = "layered"


class ModuleStructure(BaseModel):
    """Defines the structure of a module within a layer."""

    name: str = Field(..., description="Module name")
    path: str = Field(..., description="Relative path within the project")
    purpose: str = Field(..., description="Purpose of this module")
    files: List[str] = Field(
        default_factory=list, description="Files to be generated in this module"
    )
    dependencies: List[str] = Field(
        default_factory=list, description="Other modules this depends on"
    )

    def __str__(self) -> str:
        return f"Module: {self.name} ({len(self.files)} files)"


class LayerDefinition(BaseModel):
    """Defines a layer in the architecture."""

    name: str = Field(
        ..., description="Layer name (domain, application, infrastructure, presentation)"
    )
    modules: List[ModuleStructure] = Field(
        default_factory=list, description="Modules within this layer"
    )
    responsibilities: List[str] = Field(
        default_factory=list, description="What this layer is responsible for"
    )
    allowed_dependencies: List[str] = Field(
        default_factory=list,
        description="Which layers this layer is allowed to depend on",
    )

    def get_module_by_name(self, name: str) -> Optional[ModuleStructure]:
        """Get module by name."""
        return next((m for m in self.modules if m.name == name), None)

    def __str__(self) -> str:
        return f"Layer: {self.name} ({len(self.modules)} modules)"


class TechStack(BaseModel):
    """Technology stack for the generated application."""

    language: str = Field(default="TypeScript", description="Programming language")
    framework: str = Field(default="Express", description="Web framework")
    orm: str = Field(default="TypeORM", description="ORM/database library")
    validation: str = Field(default="class-validator", description="Validation library")
    testing: str = Field(default="Jest", description="Testing framework")
    documentation: str = Field(default="OpenAPI", description="API documentation tool")
    additional_libraries: Dict[str, str] = Field(
        default_factory=dict, description="Additional libraries with purpose"
    )


class DesignPattern(BaseModel):
    """Design pattern to be used in the generated code."""

    name: str = Field(..., description="Pattern name (e.g., Repository, Factory)")
    purpose: str = Field(..., description="Why this pattern is used")
    implementation_notes: str = Field(
        default="", description="Notes on how to implement this pattern"
    )


class ModernArchitecture(BaseModel):
    """Complete architecture design for the modernized application."""

    pattern: ArchitecturePattern = Field(..., description="Overall architecture pattern")
    rationale: str = Field(..., description="Why this architecture was chosen")
    layers: List[LayerDefinition] = Field(
        default_factory=list, description="Architecture layers"
    )
    folder_structure: Dict = Field(
        default_factory=dict, description="Complete folder structure"
    )
    tech_stack: TechStack = Field(..., description="Technology stack")
    patterns_used: List[DesignPattern] = Field(
        default_factory=list, description="Design patterns to be implemented"
    )
    cross_cutting_concerns: Dict[str, str] = Field(
        default_factory=dict,
        description="How cross-cutting concerns are handled (logging, auth, etc.)",
    )

    def get_layer_by_name(self, name: str) -> Optional[LayerDefinition]:
        """Get layer by name."""
        return next((layer for layer in self.layers if layer.name == name), None)

    def get_all_modules(self) -> List[ModuleStructure]:
        """Get all modules across all layers."""
        modules = []
        for layer in self.layers:
            modules.extend(layer.modules)
        return modules

    def get_pattern_by_name(self, name: str) -> Optional[DesignPattern]:
        """Get design pattern by name."""
        return next((p for p in self.patterns_used if p.name == name), None)

    def __str__(self) -> str:
        return (
            f"ModernArchitecture(pattern={self.pattern.value}, "
            f"layers={len(self.layers)}, "
            f"framework={self.tech_stack.framework})"
        )


# Common folder structures for different architecture patterns
CLEAN_ARCHITECTURE_STRUCTURE = {
    "src": {
        "domain": {
            "entities": {},
            "value-objects": {},
            "repositories": {},
            "services": {},
        },
        "application": {
            "use-cases": {},
            "dtos": {},
            "ports": {},
        },
        "infrastructure": {
            "persistence": {
                "typeorm": {
                    "entities": {},
                    "repositories": {},
                },
                "migrations": {},
            },
            "external-services": {},
        },
        "presentation": {
            "http": {
                "controllers": {},
                "middleware": {},
                "routes": {},
            },
            "api-docs": {},
        },
        "shared": {
            "errors": {},
            "utils": {},
        },
    },
    "tests": {
        "unit": {},
        "integration": {},
        "e2e": {},
    },
}

HEXAGONAL_STRUCTURE = {
    "src": {
        "core": {
            "domain": {
                "models": {},
                "ports": {},
            },
            "application": {
                "services": {},
                "use-cases": {},
            },
        },
        "adapters": {
            "input": {
                "http": {},
                "graphql": {},
            },
            "output": {
                "persistence": {},
                "external-apis": {},
            },
        },
        "config": {},
    },
    "tests": {
        "unit": {},
        "integration": {},
    },
}


def get_default_folder_structure(pattern: ArchitecturePattern) -> Dict:
    """Get the default folder structure for an architecture pattern."""
    if pattern == ArchitecturePattern.CLEAN_ARCHITECTURE:
        return CLEAN_ARCHITECTURE_STRUCTURE.copy()
    elif pattern == ArchitecturePattern.HEXAGONAL:
        return HEXAGONAL_STRUCTURE.copy()
    else:
        # Default to clean architecture
        return CLEAN_ARCHITECTURE_STRUCTURE.copy()
