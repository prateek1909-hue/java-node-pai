"""
Pydantic models for code generation inputs.
These models describe the domain objects passed to LLM code generators.
"""

from typing import List, Dict, Optional
from enum import Enum
from pydantic import BaseModel, Field


class DomainEntityType(str, Enum):
    """Type of domain entity."""

    ENTITY = "entity"
    VALUE_OBJECT = "value_object"
    AGGREGATE_ROOT = "aggregate_root"


class DomainEntity(BaseModel):
    """Represents a domain entity used for code generation."""

    name: str = Field(..., description="Entity name")
    type: DomainEntityType = Field(..., description="Entity type classification")
    properties: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Entity properties with name, type, and constraints",
    )
    business_rules: List[str] = Field(
        default_factory=list, description="Business rules governing this entity"
    )
    relationships: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Relationships to other entities (target, type, cardinality)",
    )
    validation_rules: List[str] = Field(
        default_factory=list, description="Validation rules for entity properties"
    )
    lifecycle: Optional[str] = Field(
        default=None, description="Entity lifecycle rules"
    )

    def __str__(self) -> str:
        return f"{self.type.value}: {self.name}"


class APIEndpoint(BaseModel):
    """Represents a REST API endpoint extracted from a controller."""

    path: str = Field(..., description="Endpoint path (e.g., /api/customers/{id})")
    method: str = Field(..., description="HTTP method (GET, POST, PUT, DELETE, etc.)")
    description: str = Field(default="", description="What this endpoint does")
    business_operation: str = Field(
        default="", description="Business operation this endpoint represents"
    )
    request_schema: Optional[Dict] = Field(default=None)
    response_schema: Optional[Dict] = Field(default=None)
    path_parameters: List[Dict[str, str]] = Field(default_factory=list)
    query_parameters: List[Dict[str, str]] = Field(default_factory=list)
    validation_rules: List[str] = Field(default_factory=list)
    error_scenarios: List[Dict[str, str]] = Field(default_factory=list)
    business_logic_summary: str = Field(default="")

    def __str__(self) -> str:
        return f"{self.method} {self.path}"


class UseCase(BaseModel):
    """Represents a business use case for code generation."""

    name: str = Field(..., description="Use case name")
    description: str = Field(default="", description="What this use case accomplishes")
    actors: List[str] = Field(default_factory=list)
    preconditions: List[str] = Field(default_factory=list)
    steps: List[str] = Field(default_factory=list)
    postconditions: List[str] = Field(default_factory=list)
    entities_involved: List[str] = Field(default_factory=list)
    error_scenarios: List[str] = Field(default_factory=list)

    def __str__(self) -> str:
        return f"UseCase: {self.name}"
