"""LLM configuration module.

This module provides centralized configuration management for LLM usage
across all agents and utilities in the system.

Environment Variables:
    LLM_BASE_URL: Base URL for API calls (required for LLM features)
    LLM_API_KEY: API key for the LLM provider (optional for local providers)
    LLM_MODEL: Default model to use (falls back to LLM_MODEL or built-in default)
    LLM_TEMPERATURE: Temperature for LLM responses (default: 0.7)

    Component-specific model configuration:
    NEWS_COLLECTOR_LLM_MODEL: Model for news collector agent
    REPORT_GENERATOR_LLM_MODEL: Model for report generator agent
    ENTITY_EXTRACTOR_LLM_MODEL: Model for entity extraction
    TECHNOLOGY_ANALYZER_LLM_MODEL: Model for technology analyzer

    Fallback model configuration (for 40x errors):
    LLM_FALLBACK_MODEL: Fallback model for all LLM calls when primary model fails
    LLM_FALLBACK_BASE_URL: Fallback base URL for API calls (optional)
"""

import os
from typing import Optional
from dotenv import load_dotenv

from .defaults import (
    DEFAULT_LLM_MODEL,
    DEFAULT_FALLBACK_MODEL,
    DEFAULT_LLM_TEMPERATURE,
    LLM_COMPONENT_MODEL_VARS,
    LLM_FUNCTION_MODEL_VARS,
)

# Load environment variables
load_dotenv()


class LLMConfig:
    """Centralized LLM configuration for all components.

    This class provides a unified way to configure LLM settings across
    the entire application. Each component can use a specific model
    while sharing common settings like base URL and API key.

    LLM features are enabled when LLM_BASE_URL is set (pointing to
    an OpenAI-compatible endpoint) or when an API key is available.

    Example:
        >>> config = LLMConfig()
        >>> model = config.get_model("news_collector")
        >>> api_key = config.get_api_key()
        >>> base_url = config.get_base_url()
    """

    DEFAULT_MODEL = DEFAULT_LLM_MODEL
    COMPONENT_MODEL_VARS = LLM_COMPONENT_MODEL_VARS
    FUNCTION_MODEL_VARS = LLM_FUNCTION_MODEL_VARS
    FALLBACK_MODEL = DEFAULT_FALLBACK_MODEL

    @classmethod
    def is_enabled(cls) -> bool:
        """Check if LLM features are enabled.

        LLM is enabled when either a base URL or an API key is configured.

        Returns:
            True if LLM is enabled and configured, False otherwise.
        """
        if cls.get_base_url():
            return True
        api_key = cls.get_api_key()
        return api_key is not None and len(api_key) > 0

    @classmethod
    def get_api_key(cls) -> Optional[str]:
        """Get LLM API key.

        Priority:
        1. LLM_API_KEY env var
        2. OPENAI_API_KEY env var
        3. ANTHROPIC_API_KEY env var

        Returns:
            API key string or None if not configured.
        """
        api_key = os.getenv("LLM_API_KEY", "")
        if api_key:
            return api_key

        api_key = os.getenv("OPENAI_API_KEY", "")
        if api_key:
            return api_key

        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if api_key:
            return api_key

        return None

    @classmethod
    def get_base_url(cls) -> Optional[str]:
        """Get LLM base URL for API calls.

        Returns:
            Base URL string or None if not configured.
        """
        base_url = os.getenv("LLM_BASE_URL", "")
        if base_url:
            return base_url
        return None

    @classmethod
    def get_temperature(cls) -> float:
        """Get LLM temperature.

        Returns:
            Temperature value (default: 0.7).
        """
        try:
            return float(os.getenv("LLM_TEMPERATURE", str(DEFAULT_LLM_TEMPERATURE)))
        except ValueError:
            return DEFAULT_LLM_TEMPERATURE

    @classmethod
    def get_model(cls, component: str) -> str:
        """Get the model for a specific component.

        Each component can have its own model configured via environment
        variables. If not set, falls back to LLM_MODEL, then the default.

        Args:
            component: Component name (e.g., "news_collector", "report_generator").

        Returns:
            Model name for the component.
        """
        # Check for component-specific model
        env_var = cls.COMPONENT_MODEL_VARS.get(component)
        if env_var:
            model = os.getenv(env_var, "")
            if model:
                return model

        # Fall back to generic LLM_MODEL env var
        model = os.getenv("LLM_MODEL", "")
        if model:
            return model

        return cls.DEFAULT_MODEL

    @classmethod
    def get_function_model(cls, function_name: str) -> Optional[str]:
        """Get the model for a specific LLMAnalyzer function.

        Each function can have its own model configured via environment
        variables. If not set, returns None to use the default model.

        Args:
            function_name: Function name (e.g., "executive_summary", "significance").

        Returns:
            Model name for the function or None if not configured.
        """
        env_var = cls.FUNCTION_MODEL_VARS.get(function_name)
        if env_var:
            model = os.getenv(env_var, "")
            if model:
                return model
        return None

    @classmethod
    def get_fallback_model(cls) -> str:
        """Get the fallback model for 40x error retries.

        Returns:
            Fallback model name.
        """
        model = os.getenv("LLM_FALLBACK_MODEL", "")
        if model:
            return model

        return cls.FALLBACK_MODEL

    @classmethod
    def get_fallback_base_url(cls) -> Optional[str]:
        """Get the fallback base URL for 40x error retries.

        Returns:
            Fallback base URL or None to use the primary base URL.
        """
        fallback_url = os.getenv("LLM_FALLBACK_BASE_URL", "")
        if fallback_url:
            return fallback_url

        return None

    @classmethod
    def get_fallback_api_key(cls) -> Optional[str]:
        """Get the fallback API key for 40x error retries.

        Returns:
            Fallback API key or None to use the primary API key.
        """
        fallback_key = os.getenv("LLM_FALLBACK_API_KEY", "")
        if fallback_key:
            return fallback_key

        return cls.get_api_key()

    @classmethod
    def create_llm_kwargs(cls, component: str) -> dict:
        """Create kwargs for LLMAnalyzer initialization.

        Args:
            component: Component name for model selection.

        Returns:
            Dictionary with api_key, model, base_url, and temperature.
        """
        api_key = cls.get_api_key()
        if api_key is None:
            api_key = "not-required"

        return {
            "api_key": api_key,
            "model": cls.get_model(component),
            "base_url": cls.get_base_url(),
            "temperature": cls.get_temperature(),
        }
