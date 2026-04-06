# ADR-010: Environment-Based Configuration with pydantic-settings

## Status
Accepted

## Context

The agent requires runtime configuration for:
- LLM provider selection and API credentials (OpenAI, Azure OpenAI, Anthropic)
- Azure-specific OAuth parameters (tenant ID, client ID, client secret, scope)
- Model selection, temperature, and token limits per provider
- Output directory and architecture preferences
- Output language (TypeScript or JavaScript)
- Logging level

This configuration must be:
- Securable (API keys must not be hardcoded or committed to source control)
- Overridable per-environment without code changes (local dev vs CI vs production)
- Self-documenting (defaults and descriptions should be visible to operators)
- Validated at startup (fail fast if required credentials are missing)

**Alternatives considered:**

| Option | Reason Rejected |
|---|---|
| YAML/JSON config files | Requires custom loading code; secrets still need environment variable indirection |
| `argparse` / `click` parameters only | CLI flags are impractical for 20+ settings; secrets in shell history |
| `configparser` (INI) | Weak typing; no automatic validation |
| Direct `os.environ` access | No validation, no defaults, no documentation, no type coercion |

## Decision

Use **`pydantic-settings`** (`pydantic-settings>=2.0.0`) via the `Settings` class inheriting from `BaseSettings`.

- All settings are defined as typed fields with `Field(default=..., description=...)`.
- Values are loaded automatically from environment variables (case-insensitive) and from a `.env` file if present.
- A module-level `_settings` singleton is managed by `get_settings()` / `reload_settings()` to avoid repeated instantiation.
- Provider-specific properties (`api_key`, `model_name`, `temperature`) are exposed as computed `@property` methods that select the correct field based on the active `llm_provider`, keeping call sites clean.

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # Default provider is azure_openai (not openai)
    llm_provider: Literal["openai", "azure_openai", "anthropic"] = "azure_openai"
    language: Literal["typescript", "javascript"] = "javascript"

    # OpenAI
    openai_api_key: Optional[str] = Field(default=None)
    openai_api_base: Optional[str] = Field(default=None)  # for OpenRouter etc.
    openai_model: str = Field(default="gpt-4-turbo-preview")
    openai_temperature: float = Field(default=0.2, ge=0.0, le=2.0)

    # Azure OpenAI
    azure_openai_api_key: Optional[str] = Field(default=None)
    azure_openai_endpoint: Optional[str] = Field(default=None)
    azure_openai_deployment_name: Optional[str] = Field(default=None)
    azure_openai_api_version: str = Field(default="2024-02-15-preview")
    azure_openai_temperature: float = Field(default=0.2, ge=0.0, le=2.0)

    # Azure OAuth (ClientSecretCredential)
    tenant_id: Optional[str] = Field(default=None)
    client_id: Optional[str] = Field(default=None)
    client_secret: Optional[str] = Field(default=None)
    scope: Optional[str] = Field(default=None)
    azure_endpoint: Optional[str] = Field(default=None)
    api_version: Optional[str] = Field(default=None)

    # Env-var aliases (MODEL_NAME, TEMPERATURE, MAX_TOKENS)
    model_name_override: Optional[str] = Field(default=None, alias="MODEL_NAME")
    temperature_override: Optional[float] = Field(default=None, alias="TEMPERATURE")
    max_tokens_override: Optional[int] = Field(default=None, alias="MAX_TOKENS")

    # Anthropic
    anthropic_api_key: Optional[str] = Field(default=None)
    anthropic_model: str = Field(default="claude-sonnet-4")
    anthropic_temperature: float = Field(default=0.2, ge=0.0, le=1.0)

    # Application
    max_tokens_per_request: int = Field(default=3000, gt=0)
    output_dir: str = Field(default="./output")
    architecture_pattern: Literal["clean_architecture", "hexagonal", "onion", "layered"] = "clean_architecture"
    nodejs_framework: Literal["express", "nestjs"] = "express"
    orm_preference: Literal["typeorm", "sequelize"] = "typeorm"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Multi-pass generation (see ADR-012)
    enable_multi_pass: bool = Field(default=True)   # ENABLE_MULTI_PASS=false → single-pass
    max_passes: int = Field(default=10, gt=1)        # MAX_PASSES — cap on LLM calls per file



    @property
    def api_key(self) -> str:
        # Returns the correct key based on llm_provider
        ...

    @property
    def model_name(self) -> str:
        # MODEL_NAME env var takes precedence for Azure; provider-specific model otherwise
        ...

    @property
    def temperature(self) -> float:
        # TEMPERATURE env var takes precedence; provider-specific default otherwise
        ...

    @property
    def max_tokens(self) -> int:
        # MAX_TOKENS env var takes precedence over max_tokens_per_request
        ...
```

Reference files:
- [`src/config/settings.py`](../../src/config/settings.py)

## Consequences

**Positive:**
- API keys are loaded from environment variables or `.env` — they never appear in source code.
- Pydantic validates types and constraints (e.g., `ge=0.0, le=2.0` on temperature) at application startup, failing fast with clear error messages before any LLM calls are made.
- The `Settings` class serves as the single source of truth for all configuration — new settings are added in one place and automatically available via environment variable.
- `.env` file support simplifies local development without polluting the shell environment.
- `reload_settings()` enables testing with different configurations without restarting the process.

**Negative:**
- The `_settings` global singleton is a form of global state — it makes testing require explicit `reload_settings()` calls between tests that modify the environment.
- Validation of inter-field constraints (e.g., "if `llm_provider=azure_openai`, then `azure_openai_endpoint` must be set") is deferred to `LLMClient._initialize_llm()` rather than enforced in `Settings` — this means the error surfaces later than ideal.
- The `.env` file must not be committed to source control; this is a team discipline requirement, not a technical enforcement (a `.gitignore` entry is the mitigation).

**Update (ADR-012):** Two new fields were added to support multi-pass token recovery: `enable_multi_pass` (env var `ENABLE_MULTI_PASS`, default `true`) and `max_passes` (env var `MAX_PASSES`, default `10`). These follow the same pattern as all other settings — typed, described, and loaded from environment or `.env`.
