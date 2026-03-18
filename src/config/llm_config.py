"""LLM configuration module.

This module provides centralized configuration management for LLM usage
across all agents and utilities in the system.

Environment Variables:
    LLM_PROVIDER: The LLM provider to use (openrouter, openai, anthropic, none)
    LLM_API_KEY: API key for the LLM provider
    LLM_BASE_URL: Base URL for API calls (auto-configured for openrouter)
    LLM_TEMPERATURE: Temperature for LLM responses (default: 0.7)
    
    Component-specific model configuration:
    NEWS_COLLECTOR_LLM_MODEL: Model for news collector agent
    REPORT_GENERATOR_LLM_MODEL: Model for report generator agent
    ENTITY_EXTRACTOR_LLM_MODEL: Model for entity extraction
    TECHNOLOGY_ANALYZER_LLM_MODEL: Model for technology analyzer
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class LLMConfig:
    """Centralized LLM configuration for all components.
    
    This class provides a unified way to configure LLM settings across
    the entire application. Each component can use a specific model
    while sharing common settings like API key and provider.
    
    Example:
        >>> config = LLMConfig()
        >>> # Get settings for news collector
        >>> model = config.get_model("news_collector")
        >>> api_key = config.get_api_key()
        >>> base_url = config.get_base_url()
    """
    
    # Default models for each provider
    DEFAULT_MODELS = {
        "openrouter": "qwen/qwen3.5-27b",
        "openai": "gpt-4o-mini",
        "anthropic": "claude-3-haiku-20240307",
    }
    
    # Component-specific model env var names
    COMPONENT_MODEL_VARS = {
        "news_collector": "NEWS_COLLECTOR_LLM_MODEL",
        "report_generator": "REPORT_GENERATOR_LLM_MODEL",
        "entity_extractor": "ENTITY_EXTRACTOR_LLM_MODEL",
        "technology_analyzer": "TECHNOLOGY_ANALYZER_LLM_MODEL",
    }
    
    @classmethod
    def get_provider(cls) -> str:
        """Get LLM provider.
        
        Supported providers:
        - "openrouter": OpenRouter API (OpenAI-compatible)
        - "openai": OpenAI API
        - "anthropic": Anthropic API (via LangChain)
        - "none": Disable LLM features
        
        Returns:
            LLM provider name (lowercase).
        """
        return os.getenv("LLM_PROVIDER", "none").lower()
    
    @classmethod
    def is_enabled(cls) -> bool:
        """Check if LLM features are enabled.
        
        Returns:
            True if LLM is enabled and configured, False otherwise.
        """
        provider = cls.get_provider()
        if provider == "none" or not provider:
            return False
        
        # Check if API key is available
        api_key = cls.get_api_key()
        return api_key is not None and len(api_key) > 0
    
    @classmethod
    def get_api_key(cls) -> Optional[str]:
        """Get LLM API key.
        
        Priority:
        1. LLM_API_KEY env var
        2. OPENAI_API_KEY env var (for OpenAI/OpenRouter)
        3. ANTHROPIC_API_KEY env var (for Anthropic)
        
        Returns:
            API key string or None if not configured.
        """
        # Check for generic LLM API key first
        api_key = os.getenv("LLM_API_KEY", "")
        if api_key:
            return api_key
        
        # Fall back to provider-specific keys
        provider = cls.get_provider()
        if provider in ("openrouter", "openai"):
            return os.getenv("OPENAI_API_KEY")
        elif provider == "anthropic":
            return os.getenv("ANTHROPIC_API_KEY")
        
        return None
    
    @classmethod
    def get_base_url(cls) -> Optional[str]:
        """Get LLM base URL for API calls.
        
        This is useful for:
        - OpenRouter: "https://openrouter.ai/api/v1"
        - Custom endpoints
        
        Returns:
            Base URL string or None for default.
        """
        base_url = os.getenv("LLM_BASE_URL", "")
        if base_url:
            return base_url
        
        # Auto-configure for OpenRouter
        provider = cls.get_provider()
        if provider == "openrouter":
            return "https://openrouter.ai/api/v1"
        
        return None
    
    @classmethod
    def get_temperature(cls) -> float:
        """Get LLM temperature.
        
        Returns:
            Temperature value (default: 0.7).
        """
        try:
            return float(os.getenv("LLM_TEMPERATURE", "0.7"))
        except ValueError:
            return 0.7
    
    @classmethod
    def get_default_model(cls) -> str:
        """Get the default model for the current provider.
        
        Returns:
            Default model name for the configured provider.
        """
        provider = cls.get_provider()
        return cls.DEFAULT_MODELS.get(provider, "gpt-4o-mini")
    
    @classmethod
    def get_model(cls, component: str) -> str:
        """Get the model for a specific component.
        
        Each component can have its own model configured via environment
        variables. If not set, falls back to the provider's default model.
        
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
        
        # Fall back to default model for provider
        return cls.get_default_model()
    
    @classmethod
    def create_llm_kwargs(cls, component: str) -> dict:
        """Create kwargs for LLMAnalyzer initialization.
        
        This is a convenience method that creates a dictionary with all
        the necessary parameters for initializing an LLMAnalyzer instance.
        
        Args:
            component: Component name for model selection.
            
        Returns:
            Dictionary with api_key, model, base_url, and temperature.
        """
        return {
            "api_key": cls.get_api_key(),
            "model": cls.get_model(component),
            "base_url": cls.get_base_url(),
            "temperature": cls.get_temperature(),
        }
