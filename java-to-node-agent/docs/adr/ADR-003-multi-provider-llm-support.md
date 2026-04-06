# ADR-003: Multi-Provider LLM Support (OpenAI, Azure, Anthropic)

## Status
Accepted

## Context

Enterprise users operate in environments with different LLM access constraints:
- Some have direct **OpenAI API** access.
- Others are mandated to use **Azure OpenAI** (for data residency, compliance, or corporate procurement reasons), which requires Azure-specific authentication including OAuth 2.0 client-credentials flow via MSAL.
- Some prefer **Anthropic Claude** models for their context length and reasoning quality.

Hardcoding a single provider would exclude a large portion of the user base and make the tool inflexible to organisational policies.

## Decision

Implement a **Strategy Pattern** for LLM providers, with a unified `LLMClient` class acting as the Adapter.

- An `LLMProvider` enum defines the three supported strategies: `OPENAI`, `AZURE_OPENAI`, `ANTHROPIC`.
- `LLMClient._initialize_llm()` acts as a **Factory Method** that instantiates the correct LangChain chat model (`ChatOpenAI`, `AzureChatOpenAI`, or `ChatAnthropic`) based on the configured provider.
- All provider instances are exposed behind a single interface: `generate()`, `generate_json()`, `generate_with_conversation()`.
- Azure authentication is handled transparently via `azure.identity.ClientSecretCredential`. A `token_provider` closure is passed to `AzureChatOpenAI` as `azure_ad_token_provider`, which refreshes the token automatically on each call. A separate `httpx.Client(verify=False)` is used solely for SSL bypass at corporate gateways — tokens are not manually injected into HTTP headers.
- Provider selection is driven entirely by environment variables, requiring no code changes to switch providers.

```python
# All callers use the same interface regardless of provider
client = LLMClient(settings)
response = client.generate(prompt, system_prompt)
```

Reference files:
- [`src/llm/llm_client_provider.py`](../../src/llm/llm_client_provider.py)
- [`src/config/settings.py`](../../src/config/settings.py)

## Consequences

**Positive:**
- The tool works in corporate Azure environments, direct OpenAI access, and Anthropic API access without code changes.
- Adding a new provider (e.g., Google Gemini, Mistral) requires only: adding an enum value, adding a settings block, and adding a branch in `_initialize_llm()`.
- Azure OAuth complexity is encapsulated inside `LLMClient` — callers are unaware of token management.
- Provider-specific parameters (model name, temperature, max tokens) are cleanly separated in `Settings`.

**Negative:**
- Supporting three providers means three sets of environment variables to document and validate.
- Azure OAuth token refresh is not handled automatically; long-running jobs on Azure may encounter token expiry.
- Context length differences between providers (e.g., Claude at 200K vs GPT-4 at 8K) are handled by a static lookup table in `get_max_context_length()`, which must be kept up to date as models evolve.
- SSL verification is disabled for Azure (`verify=False` in `httpx.Client`) to accommodate corporate gateways — this is a security trade-off that should be revisited.
