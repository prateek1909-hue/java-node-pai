"""
LLM client wrapper for OpenAI and Anthropic APIs.
"""

from typing import Optional, List, Dict, Any
from enum import Enum
import logging
import httpx
from azure.identity import ClientSecretCredential
from langchain_openai import ChatOpenAI, AzureChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.language_models import BaseChatModel

from src.config.settings import Settings

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    ANTHROPIC = "anthropic"


class LLMClient:
    """
    Unified client for interacting with LLM providers.
    Supports OpenAI (GPT-4) and Anthropic (Claude).
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        """
        Initialize the LLM client.

        Args:
            settings: Application settings (uses default if not provided)
        """
        self.settings = settings or Settings()
        self._oauth_token = None
        self.llm = self._initialize_llm()

    def _get_azure_oauth_token(self) -> str:
        """
        Get OAuth token for Azure using ClientSecretCredential (azure-identity).

        Returns:
            OAuth access token
        """
        credential = ClientSecretCredential(
            tenant_id=self.settings.tenant_id,
            client_id=self.settings.client_id,
            client_secret=self.settings.client_secret,
        )
        return credential.get_token(self.settings.scope).token

    def _create_azure_http_client(self) -> httpx.Client:
        """
        Create HTTP client for Azure (SSL verification disabled for gateway compatibility).

        Returns:
            Configured HTTP client
        """
        return httpx.Client(verify=False, timeout=120.0)

    def _initialize_llm(self) -> BaseChatModel:
        """
        Initialize the appropriate LLM based on settings.

        Returns:
            Initialized LLM client

        Raises:
            ValueError: If provider is not supported or API key is missing
        """
        provider = self.settings.llm_provider

        if provider == LLMProvider.OPENAI:
            if not self.settings.openai_api_key:
                raise ValueError(
                    "OpenAI API key is required. Set OPENAI_API_KEY environment variable."
                )

            # Build kwargs for ChatOpenAI
            openai_kwargs = {
                "model": self.settings.openai_model,
                "temperature": self.settings.temperature,
                "max_tokens": self.settings.max_tokens,
                "api_key": self.settings.openai_api_key,
            }
            
            # Add base_url if specified (for OpenRouter, etc.)
            if self.settings.openai_api_base:
                openai_kwargs["base_url"] = self.settings.openai_api_base
            
            return ChatOpenAI(**openai_kwargs)

        elif provider == LLMProvider.AZURE_OPENAI:
            endpoint = self.settings.azure_endpoint or self.settings.azure_openai_endpoint
            deployment = self.settings.model_name  # Checks MODEL_NAME -> deployment_name -> "gpt-4"
            api_ver = self.settings.api_version or self.settings.azure_openai_api_version

            if not endpoint:
                raise ValueError(
                    "Azure endpoint required. Set AZURE_ENDPOINT or AZURE_OPENAI_ENDPOINT."
                )
            if not deployment:
                raise ValueError(
                    "Azure deployment name required. Set MODEL_NAME or AZURE_OPENAI_DEPLOYMENT_NAME."
                )

            # Use ClientSecretCredential so the token is refreshed automatically on each call
            credential = ClientSecretCredential(
                tenant_id=self.settings.tenant_id,
                client_id=self.settings.client_id,
                client_secret=self.settings.client_secret,
            )

            def token_provider() -> str:
                return credential.get_token(self.settings.scope).token

            return AzureChatOpenAI(
                azure_deployment=deployment,
                azure_endpoint=endpoint,
                api_version=api_ver,
                api_key="oauth-placeholder",  # Required by constructor; overridden by token provider
                azure_ad_token_provider=token_provider,
                http_client=httpx.Client(verify=False, timeout=120.0),
                temperature=self.settings.temperature,
                max_tokens=self.settings.max_tokens,
            )

        elif provider == LLMProvider.ANTHROPIC:
            if not self.settings.anthropic_api_key:
                raise ValueError(
                    "Anthropic API key is required. Set ANTHROPIC_API_KEY environment variable."
                )

            return ChatAnthropic(
                model=self.settings.anthropic_model,
                temperature=self.settings.temperature,
                max_tokens=self.settings.max_tokens,
                api_key=self.settings.anthropic_api_key,
            )

        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Generate a response from the LLM.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt to set context
            temperature: Optional temperature override
            max_tokens: Optional max tokens override

        Returns:
            The LLM's response as a string
        """
        # Guard against prompts that exceed the model's context window.
        # Reserve space for the output (max_tokens) and truncate the user
        # prompt if the combined input would overflow.
        effective_max_tokens = max_tokens if max_tokens is not None else self.settings.max_tokens
        max_input_tokens = self.get_max_context_length() - effective_max_tokens
        prompt = self._truncate_prompt(prompt, system_prompt, max_input_tokens)

        messages = []

        # Add system message if provided
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))

        # Add user message
        messages.append(HumanMessage(content=prompt))

        # Override settings if provided
        kwargs = {}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        # Generate response
        if kwargs:
            # Create a new instance with overridden parameters
            llm = self.llm.bind(**kwargs)
            response = llm.invoke(messages)
        else:
            response = self.llm.invoke(messages)

        return response.content

    def generate_with_conversation(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Generate a response using a conversation history.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
                     Role can be 'system', 'user', or 'assistant'
            temperature: Optional temperature override
            max_tokens: Optional max tokens override

        Returns:
            The LLM's response as a string
        """
        # Convert message dicts to LangChain message objects
        langchain_messages = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")

            if role == "system":
                langchain_messages.append(SystemMessage(content=content))
            elif role == "user":
                langchain_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                langchain_messages.append(AIMessage(content=content))
            else:
                raise ValueError(f"Unknown message role: {role}")

        # Override settings if provided
        kwargs = {}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        # Generate response
        if kwargs:
            llm = self.llm.bind(**kwargs)
            response = llm.invoke(langchain_messages)
        else:
            response = self.llm.invoke(langchain_messages)

        return response.content

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Generate a JSON response from the LLM.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            temperature: Optional temperature override

        Returns:
            Parsed JSON response as a dictionary
        """
        import json

        # Add JSON formatting instruction to prompt
        json_instruction = "\n\nPlease respond with valid JSON only. Do not include any explanation or markdown formatting."
        enhanced_prompt = prompt + json_instruction

        response = self.generate(
            prompt=enhanced_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
        )

        # Try to parse JSON from response
        # Handle cases where LLM returns markdown code blocks
        response = response.strip()

        if response.startswith("```json"):
            response = response[7:]  # Remove ```json
        elif response.startswith("```"):
            response = response[3:]  # Remove ```

        if response.endswith("```"):
            response = response[:-3]  # Remove closing ```

        response = response.strip()

        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {e}\nResponse: {response}")

    def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in a text string.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        # Use the LLM's token counter
        return self.llm.get_num_tokens(text)

    def _truncate_prompt(
        self,
        prompt: str,
        system_prompt: Optional[str],
        max_input_tokens: int,
    ) -> str:
        """
        Truncate the user prompt so that (system + user) tokens fit within
        max_input_tokens.  Uses tiktoken with cl100k_base encoding, which is a
        close approximation for GPT-4, GPT-3.5, and Claude models.

        If tiktoken is unavailable or raises an error the original prompt is
        returned unchanged (fail-open — the API will surface a context-length
        error if the prompt is genuinely too long).

        Args:
            prompt: The user prompt to (potentially) truncate.
            system_prompt: The system prompt (counted but not truncated).
            max_input_tokens: Maximum number of tokens allowed for the combined
                              system + user prompt.

        Returns:
            The original prompt, or a truncated version with a trailing note.
        """
        try:
            import tiktoken
            enc = tiktoken.get_encoding("cl100k_base")

            system_tokens = len(enc.encode(system_prompt)) if system_prompt else 0
            available = max_input_tokens - system_tokens

            if available <= 0:
                # System prompt alone is too large — pass through and let the
                # API surface the error with its full diagnostic message.
                return prompt

            prompt_token_ids = enc.encode(prompt)
            if len(prompt_token_ids) <= available:
                return prompt  # No truncation needed.

            # Decode a candidate slice, then back up to the last newline so we
            # never cut through a JSON object or array mid-structure.
            # Reserve 20 tokens for the trailing note.
            candidate = enc.decode(prompt_token_ids[: available - 20])
            last_nl = candidate.rfind("\n")
            # Only snap to the newline if it's in the last 30 % of the string
            # (prevents cutting off so much that we lose critical context).
            if last_nl > int(len(candidate) * 0.70):
                candidate = candidate[:last_nl]

            logger.warning(
                "Prompt truncated from %d to ~%d tokens to fit context window "
                "(model context: %d, max_tokens reserved for output: %d). "
                "Check generator token-budget settings if this fires repeatedly.",
                len(prompt_token_ids),
                len(enc.encode(candidate)),
                self.get_max_context_length(),
                self.settings.max_tokens,
            )
            return candidate + "\n[... input truncated to fit context window ...]"
        except Exception as exc:  # noqa: BLE001
            logger.debug("Prompt truncation skipped (%s); passing prompt as-is.", exc)
            return prompt

    def get_model_name(self) -> str:
        """
        Get the name of the current model.

        Returns:
            Model name
        """
        # AzureChatOpenAI uses deployment_name; ChatOpenAI/ChatAnthropic use model_name
        return getattr(self.llm, "deployment_name", None) or getattr(self.llm, "model_name", "unknown")

    def get_provider(self) -> str:
        """
        Get the current LLM provider.

        Returns:
            Provider name
        """
        return self.settings.llm_provider

    def get_max_context_length(self) -> int:
        """
        Get the maximum context length for the current model.

        Returns:
            Maximum context length in tokens
        """
        # Common context lengths for different models
        model_contexts = {
            # OpenAI
            "gpt-4": 8192,
            "gpt-4-turbo": 128000,
            "gpt-4-turbo-preview": 128000,
            "gpt-4o": 128000,
            "gpt-4o-mini": 128000,
            "gpt-3.5-turbo": 16385,
            "gpt-35-turbo": 16385,  # Azure naming
            # Anthropic
            "claude-3-opus-20240229": 200000,
            "claude-3-sonnet-20240229": 200000,
            "claude-3-haiku-20240307": 200000,
            "claude-3-5-sonnet-20240620": 200000,
        }

        model_name = self.get_model_name()

        # For Azure, the deployment name might not match standard model names
        # Try to infer from deployment name if available
        if self.settings.llm_provider == "azure_openai":
            deployment_name = self.settings.azure_openai_deployment_name or ""
            # Check if deployment name contains known model identifiers
            for known_model in model_contexts.keys():
                if known_model.replace("-", "").replace(".", "") in deployment_name.replace("-", "").replace(".", "").lower():
                    return model_contexts[known_model]
            # Default for Azure GPT-4
            return 128000

        return model_contexts.get(model_name, 8192)  # Default to 8K if unknown
