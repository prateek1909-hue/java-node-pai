"""
Pydantic models representing generated output and conversion results.
"""

from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class FileType(str, Enum):
    """Type of generated file."""

    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    JSON = "json"
    MARKDOWN = "markdown"
    YAML = "yaml"
    CONFIG = "config"


class GeneratedFile(BaseModel):
    """Represents a single generated file."""

    path: str = Field(..., description="Relative path to the file")
    content: str = Field(..., description="File content")
    file_type: FileType = Field(..., description="Type of file")
    layer: Optional[str] = Field(default=None, description="Architecture layer (if applicable)")
    description: str = Field(default="", description="What this file does")
    source_java_file: Optional[str] = Field(
        default=None, description="Original Java file (if converted)"
    )

    def __str__(self) -> str:
        return f"GeneratedFile: {self.path}"


class GeneratedModule(BaseModel):
    """Represents a generated module (collection of related files)."""

    name: str = Field(..., description="Module name")
    path: str = Field(..., description="Module directory path")
    files: List[GeneratedFile] = Field(default_factory=list, description="Files in this module")
    purpose: str = Field(..., description="Module purpose")

    def add_file(self, file: GeneratedFile) -> None:
        """Add a file to this module."""
        self.files.append(file)

    def get_file_by_name(self, filename: str) -> Optional[GeneratedFile]:
        """Get file by filename."""
        return next((f for f in self.files if f.path.endswith(filename)), None)

    def __str__(self) -> str:
        return f"Module: {self.name} ({len(self.files)} files)"


class ConversionMetadata(BaseModel):
    """Metadata about the conversion process."""

    timestamp: datetime = Field(default_factory=datetime.now, description="When conversion ran")
    java_repository_url: str = Field(..., description="Source Java repository URL")
    java_files_analyzed: int = Field(default=0, description="Number of Java files analyzed")
    llm_provider: str = Field(..., description="LLM provider used (openai/anthropic)")
    llm_model: str = Field(..., description="Specific model used")
    total_llm_calls: int = Field(default=0, description="Total LLM API calls made")
    total_tokens_used: int = Field(default=0, description="Total tokens consumed")
    estimated_cost: Optional[float] = Field(default=None, description="Estimated cost in USD")
    errors_encountered: List[str] = Field(
        default_factory=list, description="Errors during conversion"
    )
    warnings: List[str] = Field(default_factory=list, description="Warnings during conversion")


class ConversionResult(BaseModel):
    """Complete result of Java to Node.js conversion."""

    # Metadata
    metadata: ConversionMetadata = Field(..., description="Conversion metadata")

    # Generated code organization
    generated_modules: List[GeneratedModule] = Field(
        default_factory=list, description="All generated modules"
    )

    # Special files
    package_json: Optional[GeneratedFile] = Field(
        default=None, description="Generated package.json"
    )
    tsconfig: Optional[GeneratedFile] = Field(
        default=None, description="Generated tsconfig.json"
    )
    readme: Optional[GeneratedFile] = Field(default=None, description="Generated README.md")

    # Analysis outputs
    domain_knowledge_json: Optional[GeneratedFile] = Field(
        default=None, description="Domain knowledge JSON file"
    )
    architecture_json: Optional[GeneratedFile] = Field(
        default=None, description="Architecture design JSON file"
    )
    api_documentation: Optional[GeneratedFile] = Field(
        default=None, description="API documentation file"
    )

    def add_module(self, module: GeneratedModule) -> None:
        """Add a generated module."""
        self.generated_modules.append(module)

    def get_all_files(self) -> List[GeneratedFile]:
        """Get all generated files across all modules."""
        files = []
        for module in self.generated_modules:
            files.extend(module.files)
        if self.package_json:
            files.append(self.package_json)
        if self.tsconfig:
            files.append(self.tsconfig)
        if self.readme:
            files.append(self.readme)
        if self.domain_knowledge_json:
            files.append(self.domain_knowledge_json)
        if self.architecture_json:
            files.append(self.architecture_json)
        if self.api_documentation:
            files.append(self.api_documentation)
        return files

    def get_module_by_name(self, name: str) -> Optional[GeneratedModule]:
        """Get module by name."""
        return next((m for m in self.generated_modules if m.name == name), None)

    def get_files_by_layer(self, layer: str) -> List[GeneratedFile]:
        """Get all files in a specific layer."""
        return [f for f in self.get_all_files() if f.layer == layer]

    def __str__(self) -> str:
        return (
            f"ConversionResult(modules={len(self.generated_modules)}, "
            f"total_files={len(self.get_all_files())}, "
            f"llm_calls={self.metadata.total_llm_calls})"
        )


class ProjectOutput(BaseModel):
    """Complete project output including all generated files and documentation."""

    project_name: str = Field(..., description="Generated project name")
    output_directory: str = Field(..., description="Output directory path")
    conversion_result: ConversionResult = Field(..., description="Conversion result")

    # File paths for easy access
    source_files_path: str = Field(
        default="src/", description="Path to generated source files"
    )
    tests_path: str = Field(default="tests/", description="Path to generated tests")
    docs_path: str = Field(default="docs/", description="Path to documentation")
    analysis_path: str = Field(
        default="analysis/", description="Path to analysis outputs"
    )

    def get_total_files_count(self) -> int:
        """Get total number of generated files."""
        return len(self.conversion_result.get_all_files())

    def get_typescript_files_count(self) -> int:
        """Get count of TypeScript files."""
        return len(
            [
                f
                for f in self.conversion_result.get_all_files()
                if f.file_type == FileType.TYPESCRIPT
            ]
        )

    def __str__(self) -> str:
        return (
            f"ProjectOutput(name={self.project_name}, "
            f"files={self.get_total_files_count()})"
        )
