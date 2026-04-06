"""
Configuration settings for the Java to Node.js converter.
Loads settings from environment variables using pydantic-settings.
"""

from typing import Literal, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    # LLM Provider Configuration — defaults to azure_openai
    llm_provider: Literal["openai", "azure_openai", "anthropic"] = Field(
        default="azure_openai", description="LLM provider to use"
    )

    # OpenAI Configuration
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    openai_api_base: Optional[str] = Field(default=None, description="OpenAI API base URL (for OpenRouter, etc.)")
    openai_model: str = Field(
        default="gpt-4-turbo-preview", description="OpenAI model to use"
    )
    openai_temperature: float = Field(
        default=0.2, ge=0.0, le=2.0, description="OpenAI temperature parameter"
    )

    # Azure OpenAI Configuration
    azure_openai_api_key: Optional[str] = Field(
        default=None, description="Azure OpenAI API key"
    )
    azure_openai_endpoint: Optional[str] = Field(
        default=None, description="Azure OpenAI endpoint URL"
    )
    azure_openai_deployment_name: Optional[str] = Field(
        default=None, description="Azure OpenAI deployment name"
    )
    azure_openai_api_version: str = Field(
        default="2024-02-15-preview", description="Azure OpenAI API version"
    )
    azure_openai_temperature: float = Field(
        default=0.2, ge=0.0, le=2.0, description="Azure OpenAI temperature parameter"
    )

    # Azure Authentication Configuration (current solution env var names)
    tenant_id: Optional[str] = Field(default=None, description="Azure Tenant ID")
    client_id: Optional[str] = Field(default=None, description="Azure Client ID")
    client_secret: Optional[str] = Field(default=None, description="Azure Client Secret")
    scope: Optional[str] = Field(default=None, description="Azure OAuth Scope")
    azure_endpoint: Optional[str] = Field(default=None, description="Azure Gateway Endpoint")
    api_version: Optional[str] = Field(default=None, description="Azure API Version")

    # Aliases for current solution's env var names (MODEL_NAME, TEMPERATURE, MAX_TOKENS)
    model_name_override: Optional[str] = Field(
        default=None, alias="MODEL_NAME", description="Alias for MODEL_NAME env var"
    )
    temperature_override: Optional[float] = Field(
        default=None, alias="TEMPERATURE", description="Temperature override"
    )
    max_tokens_override: Optional[int] = Field(
        default=None, alias="MAX_TOKENS", description="Max tokens override"
    )

    # Anthropic Configuration
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API key")
    anthropic_model: str = Field(
        default="claude-sonnet-4", description="Anthropic model to use"
    )
    anthropic_temperature: float = Field(
        default=0.2, ge=0.0, le=1.0, description="Anthropic temperature parameter"
    )

    # Application Configuration
    max_tokens_per_request: int = Field(
        default=3000, gt=0, description="Maximum tokens per LLM request"
    )
    output_dir: str = Field(default="./output", description="Output directory path")

    # Architecture Preferences
    architecture_pattern: Literal[
        "clean_architecture", "hexagonal", "onion", "layered"
    ] = Field(default="clean_architecture", description="Architecture pattern to use")

    nodejs_framework: Literal["express", "nestjs"] = Field(
        default="express", description="Node.js framework for generated code"
    )

    orm_preference: Literal["typeorm", "sequelize"] = Field(
        default="typeorm", description="ORM to use in generated code"
    )

    # Language Preference
    language: Literal["typescript", "javascript"] = Field(
        default="javascript", description="Output language for generated code (TypeScript or JavaScript)"
    )

    # Multi-pass generation
    enable_multi_pass: bool = Field(
        default=True,
        description=(
            "If True, run additional LLM passes when methods are dropped by the token "
            "budget or the prompt is truncated, then merge all passes into one file. "
            "Set ENABLE_MULTI_PASS=false to restore single-pass behaviour."
        ),
    )
    max_passes: int = Field(
        default=10,
        gt=1,
        description=(
            "Maximum number of LLM passes (including the first) per generated file. "
            "Each extra pass handles the remainder of methods that did not fit in the "
            "previous pass. Caps at 10 to prevent runaway API costs."
        ),
    )

    # Logging Configuration
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="Logging level"
    )


    @field_validator("openai_api_key", "anthropic_api_key")
    @classmethod
    def validate_api_keys(cls, v: Optional[str], info) -> Optional[str]:  # type: ignore
        """
        Pydantic field validator placeholder for API key fields.

        Actual key presence checking is deferred to the api_key property and to
        _initialize_llm in LLMClient, where the active provider is known.  This
        validator exists as an extension point for future field-level checks.
        """
        return v

    @property
    def api_key(self) -> str:
        """Get the appropriate API key based on the selected provider."""
        if self.llm_provider == "openai":
            if not self.openai_api_key:
                raise ValueError("OPENAI_API_KEY must be set when using OpenAI provider")
            return self.openai_api_key
        elif self.llm_provider == "azure_openai":
            # When using OAuth (tenant_id/client_id/client_secret), no API key needed
            if all([self.tenant_id, self.client_id, self.client_secret]):
                return "oauth-placeholder"  # Not used; azure_ad_token_provider overrides it
            if not self.azure_openai_api_key:
                raise ValueError(
                    "AZURE_OPENAI_API_KEY must be set when not using OAuth "
                    "(set TENANT_ID, CLIENT_ID, CLIENT_SECRET for OAuth)"
                )
            return self.azure_openai_api_key
        elif self.llm_provider == "anthropic":
            if not self.anthropic_api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY must be set when using Anthropic provider"
                )
            return self.anthropic_api_key
        else:
            raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")

    @property
    def model_name(self) -> str:
        """Get the appropriate model name based on the selected provider."""
        if self.llm_provider == "openai":
            return self.openai_model
        elif self.llm_provider == "azure_openai":
            # MODEL_NAME env var takes precedence, then deployment name, then default
            return (
                self.model_name_override
                or self.azure_openai_deployment_name
                or "gpt-4"
            )
        elif self.llm_provider == "anthropic":
            return self.anthropic_model
        else:
            raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")

    @property
    def temperature(self) -> float:
        """Get the appropriate temperature based on the selected provider."""
        if self.llm_provider == "openai":
            return self.openai_temperature
        elif self.llm_provider == "azure_openai":
            # TEMPERATURE env var takes precedence
            return self.temperature_override if self.temperature_override is not None else self.azure_openai_temperature
        elif self.llm_provider == "anthropic":
            return self.anthropic_temperature
        else:
            raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")

    @property
    def max_tokens(self) -> int:
        """Get the maximum tokens per request."""
        # MAX_TOKENS env var takes precedence over max_tokens_per_request
        return self.max_tokens_override if self.max_tokens_override is not None else self.max_tokens_per_request


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get the global settings instance.
    Creates it if it doesn't exist.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """
    Reload settings from environment variables.
    Useful for testing or when environment changes.
    """
    global _settings
    _settings = Settings()
    return _settings
