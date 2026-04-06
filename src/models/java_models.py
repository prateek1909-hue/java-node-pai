"""
Pydantic models representing Java code structures.
These models are populated by the tree-sitter parser.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class JavaAnnotation(BaseModel):
    """Represents a Java annotation (e.g., @RestController, @GetMapping)."""

    name: str = Field(..., description="Annotation name without @ symbol")
    arguments: str = Field(default="", description="Annotation arguments as string")

    def __str__(self) -> str:
        if self.arguments:
            return f"@{self.name}({self.arguments})"
        return f"@{self.name}"


class JavaParameter(BaseModel):
    """Represents a method parameter."""

    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Parameter type")
    annotations: List[JavaAnnotation] = Field(
        default_factory=list, description="Parameter annotations (e.g., @PathVariable)"
    )

    def has_annotation(self, annotation_name: str) -> bool:
        """Check if parameter has a specific annotation."""
        return any(ann.name == annotation_name for ann in self.annotations)

    def __str__(self) -> str:
        return f"{self.type} {self.name}"


class JavaMethod(BaseModel):
    """Represents a Java method."""

    name: str = Field(..., description="Method name")
    signature: str = Field(..., description="Full method signature")
    return_type: str = Field(..., description="Return type")
    parameters: List[JavaParameter] = Field(
        default_factory=list, description="Method parameters"
    )
    modifiers: List[str] = Field(
        default_factory=list, description="Access modifiers (public, private, static, etc.)"
    )
    annotations: List[JavaAnnotation] = Field(
        default_factory=list, description="Method annotations"
    )
    body: str = Field(default="", description="Method body source code")
    start_line: int = Field(..., description="Starting line number in source file")
    end_line: int = Field(..., description="Ending line number in source file")

    # LLM-enhanced fields (populated during analysis)
    description: Optional[str] = Field(
        default=None, description="LLM-generated method description"
    )
    complexity: Optional[str] = Field(
        default=None, description="Complexity estimate: Low, Medium, or High"
    )

    def has_annotation(self, annotation_name: str) -> bool:
        """Check if method has a specific annotation."""
        return any(ann.name == annotation_name for ann in self.annotations)

    def is_public(self) -> bool:
        """Check if method is public."""
        return "public" in self.modifiers

    def is_static(self) -> bool:
        """Check if method is static."""
        return "static" in self.modifiers

    def __str__(self) -> str:
        return self.signature


class JavaField(BaseModel):
    """Represents a class field/member variable."""

    name: str = Field(..., description="Field name")
    type: str = Field(..., description="Field type")
    modifiers: List[str] = Field(
        default_factory=list, description="Access modifiers (public, private, static, final, etc.)"
    )
    annotations: List[JavaAnnotation] = Field(
        default_factory=list, description="Field annotations (e.g., @Autowired, @Column)"
    )

    def has_annotation(self, annotation_name: str) -> bool:
        """Check if field has a specific annotation."""
        return any(ann.name == annotation_name for ann in self.annotations)

    def is_private(self) -> bool:
        """Check if field is private."""
        return "private" in self.modifiers

    def is_final(self) -> bool:
        """Check if field is final."""
        return "final" in self.modifiers

    def __str__(self) -> str:
        return f"{self.type} {self.name}"


class JavaClass(BaseModel):
    """Represents a complete Java class or interface."""

    name: str = Field(..., description="Class name")
    type: str = Field(..., description="Type: class, interface, enum, or annotation")
    package: str = Field(..., description="Package declaration")
    imports: List[str] = Field(default_factory=list, description="Import statements")
    annotations: List[JavaAnnotation] = Field(
        default_factory=list, description="Class-level annotations"
    )
    modifiers: List[str] = Field(
        default_factory=list, description="Class modifiers (public, abstract, final, etc.)"
    )
    extends: Optional[str] = Field(default=None, description="Parent class (if extends)")
    implements: List[str] = Field(
        default_factory=list, description="Implemented interfaces"
    )
    fields: List[JavaField] = Field(default_factory=list, description="Class fields")
    methods: List[JavaMethod] = Field(default_factory=list, description="Class methods")
    file_path: str = Field(..., description="Source file path")
    category: str = Field(
        ..., description="Category: Controller, Service, DAO, Entity, Config, Util, Unknown"
    )
    source_code: str = Field(..., description="Complete source code")
    start_line: int = Field(..., description="Starting line number")
    end_line: int = Field(..., description="Ending line number")

    # LLM-enhanced fields (populated during analysis)
    description: Optional[str] = Field(
        default=None, description="LLM-generated class description"
    )
    dependencies: List[str] = Field(
        default_factory=list, description="Other classes this class depends on"
    )

    def has_annotation(self, annotation_name: str) -> bool:
        """Check if class has a specific annotation."""
        return any(ann.name == annotation_name for ann in self.annotations)

    def is_controller(self) -> bool:
        """Check if this is a Spring Controller class."""
        return self.category == "Controller" or self.has_annotation(
            "RestController"
        ) or self.has_annotation("Controller")

    def is_service(self) -> bool:
        """Check if this is a Spring Service class."""
        return self.category == "Service" or self.has_annotation("Service")

    def is_repository(self) -> bool:
        """Check if this is a Spring Repository/DAO class."""
        return self.category == "DAO" or self.has_annotation("Repository")

    def is_entity(self) -> bool:
        """Check if this is a JPA Entity class."""
        return self.category == "Entity" or self.has_annotation("Entity")

    def get_public_methods(self) -> List[JavaMethod]:
        """Get all public methods."""
        return [m for m in self.methods if m.is_public()]

    def get_rest_endpoints(self) -> List[JavaMethod]:
        """Get all REST endpoint methods (for controllers)."""
        rest_annotations = [
            "GetMapping",
            "PostMapping",
            "PutMapping",
            "DeleteMapping",
            "PatchMapping",
            "RequestMapping",
        ]
        return [
            m for m in self.methods if any(m.has_annotation(ann) for ann in rest_annotations)
        ]

    def __str__(self) -> str:
        return f"{self.category}: {self.package}.{self.name}"

    def __repr__(self) -> str:
        return f"JavaClass(name='{self.name}', category='{self.category}', methods={len(self.methods)})"
