"""RSS feed configuration module.

This module provides configuration management for RSS feed collection,
allowing users to customize sources, keywords, and other settings via
environment variables or JSON configuration files.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Union
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class RSSConfig:
    """Configuration for RSS feed collection.
    
    This class provides centralized configuration management for the
    NewsCollectorAgent, allowing customization via environment variables,
    JSON configuration files, or programmatic override.
    
    Environment Variables:
        RSS_SOURCES: Comma-separated list of RSS feed URLs (highest priority)
        RSS_SOURCES_FILE: Path to JSON file containing RSS sources
        RSS_KEYWORDS: Comma-separated list of keywords for filtering
        RSS_KEYWORDS_FILE: Path to JSON file containing keywords
        RSS_CONTENT_TIMEOUT: HTTP timeout for content fetching (seconds)
        RSS_LOG_FAILURES: Enable/disable failure logging (true/false)
        RSS_LOG_FILE: Path to the failure log file
    
    JSON Config File Format (RSS_SOURCES_FILE):
        Simple format:
            ["https://example.com/feed1", "https://example.com/feed2"]
        
        Structured format (with metadata):
            {
                "sources": [
                    {"url": "https://example.com/feed", "name": "Example", "category": "tech"}
                ]
            }
    
    Example:
        >>> config = RSSConfig()
        >>> sources = config.get_sources()
        >>> keywords = config.get_keywords()
    """
    
    # Default RSS sources for tech news
    DEFAULT_SOURCES = [
        "https://techcrunch.com/feed/",
        "https://www.theverge.com/rss/index.xml",
        "https://arstechnica.com/feed/",
        "https://www.wired.com/feed/rss",
        "https://news.ycombinator.com/rss",
        "https://www.zdnet.com/news/rss/",
        "https://thenextweb.com/feed/",
    ]
    
    # Default technology keywords for filtering
    DEFAULT_KEYWORDS = [
        # AI/ML
        "AI", "artificial intelligence", "machine learning", "deep learning",
        "neural network", "LLM", "large language model", "transformer",
        "diffusion model", "generative AI", "computer vision", "NLP",
        "RAG", "agent", "multi-agent", "GPT", "ChatGPT", "Claude", "Gemini",
        "OpenAI", "Anthropic", "Hugging Face",
        
        # Quantum Computing
        "quantum computing", "quantum", "qubit", "quantum supremacy",
        "quantum error correction", "IBM Quantum", "Google Quantum",
        
        # Blockchain/Web3
        "blockchain", "cryptocurrency", "web3", "crypto", "NFT", "DeFi",
        "smart contract", "Bitcoin", "Ethereum", "Solana",
        
        # Robotics
        "robotics", "robot", "autonomous", "humanoid", "automation",
        "Boston Dynamics", "Tesla Optimus",
        
        # Cloud/Infrastructure
        "cloud computing", "edge computing", "serverless", "kubernetes",
        "microservices", "devops", "API", "AWS", "Azure", "Google Cloud",
        
        # Cybersecurity
        "cybersecurity", "zero trust", "encryption", "authentication",
        "security", "data breach", "hacking",
        
        # Telecommunications
        "5G", "6G", "telecommunications", "network", "Starlink",
        
        # IoT
        "IoT", "Internet of Things", "sensor", "connected devices",
        
        # AR/VR/MR
        "augmented reality", "virtual reality", "AR", "VR", "mixed reality",
        "metaverse", "Apple Vision Pro", "Meta Quest",
        
        # Biotech
        "biotech", "gene editing", "CRISPR", "synthetic biology",
        "biomedical", "mRNA",
        
        # Energy/Cleantech
        "battery technology", "renewable energy", "solar", "fusion",
        "hydrogen fuel", "carbon capture", "climate tech", "EV", "electric vehicle",
        
        # Semiconductors
        "semiconductor", "chip", "processor", "GPU", "NVIDIA", "AMD", "Intel",
        "TSMC", "ARM", "RISC-V",
        
        # Software Development
        "software development", "programming", "developer", "API",
        "open source", "GitHub", "GitLab",
    ]
    
    @classmethod
    def _load_json_file(cls, file_path: str) -> Optional[Union[Dict, List]]:
        """Load and parse a JSON configuration file.
        
        Args:
            file_path: Path to the JSON file (relative or absolute).
            
        Returns:
            Parsed JSON data as dict or list, or None if file doesn't exist.
        """
        path = Path(file_path)
        if not path.is_absolute():
            # Try relative to project root
            path = Path(__file__).parent.parent.parent / file_path
        
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    @classmethod
    def get_sources(cls) -> List[str]:
        """Get RSS sources from environment, config file, or defaults.
        
        Priority:
        1. RSS_SOURCES env var (comma-separated URLs)
        2. RSS_SOURCES_FILE env var (path to JSON config file)
        3. DEFAULT_SOURCES
        
        Returns:
            List of RSS feed URLs.
        """
        # First check for comma-separated sources (highest priority)
        sources = os.getenv("RSS_SOURCES", "")
        if sources:
            return [s.strip() for s in sources.split(",") if s.strip()]
        
        # Then check for config file
        sources_file = os.getenv("RSS_SOURCES_FILE", "")
        if sources_file:
            data = cls._load_json_file(sources_file)
            if data:
                # Support both simple list and structured format
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and "sources" in data:
                    # Extract URLs from structured format
                    return [
                        s["url"] if isinstance(s, dict) else s
                        for s in data["sources"]
                    ]
        
        return cls.DEFAULT_SOURCES.copy()
    
    @classmethod
    def get_keywords(cls) -> List[str]:
        """Get keywords from environment, config file, or defaults.
        
        Priority:
        1. RSS_KEYWORDS env var (comma-separated keywords)
        2. RSS_KEYWORDS_FILE env var (path to JSON config file)
        3. DEFAULT_KEYWORDS
        
        Returns:
            List of keywords for article filtering.
        """
        # First check for comma-separated keywords (highest priority)
        keywords = os.getenv("RSS_KEYWORDS", "")
        if keywords:
            return [k.strip() for k in keywords.split(",") if k.strip()]
        
        # Then check for config file
        keywords_file = os.getenv("RSS_KEYWORDS_FILE", "")
        if keywords_file:
            data = cls._load_json_file(keywords_file)
            if data:
                # Support both simple list and structured format
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and "keywords" in data:
                    return data["keywords"]
        
        return cls.DEFAULT_KEYWORDS.copy()
    
    @classmethod
    def get_timeout(cls) -> int:
        """Get HTTP timeout in seconds.
        
        Returns:
            Timeout in seconds for HTTP requests.
        """
        try:
            return int(os.getenv("RSS_CONTENT_TIMEOUT", "30"))
        except ValueError:
            return 30
    
    @classmethod
    def is_failure_logging_enabled(cls) -> bool:
        """Check if failure logging is enabled.
        
        Returns:
            True if failure logging is enabled, False otherwise.
        """
        return os.getenv("RSS_LOG_FAILURES", "true").lower() == "true"
    
    @classmethod
    def get_log_file(cls) -> str:
        """Get path to failure log file.
        
        Returns:
            Path to the failure log file.
        """
        return os.getenv("RSS_LOG_FILE", "./logs/rss_failures.log")
    
    @classmethod
    def validate_sources(cls, sources: List[str]) -> List[str]:
        """Validate and filter RSS sources.
        
        Args:
            sources: List of RSS source URLs to validate.
            
        Returns:
            List of valid RSS source URLs.
        """
        valid_sources = []
        for source in sources:
            source = source.strip()
            if source and (source.startswith("http://") or source.startswith("https://")):
                valid_sources.append(source)
        return valid_sources
    
    @classmethod
    def get_llm_provider(cls) -> str:
        """Get LLM provider for technology classification.
        
        Supported providers:
        - "openrouter": OpenRouter API (OpenAI-compatible)
        - "openai": OpenAI API
        - "anthropic": Anthropic API (via LangChain)
        - "none": Disable LLM-based classification (use keyword matching)
        
        Returns:
            LLM provider name.
        """
        return os.getenv("RSS_LLM_PROVIDER", "none").lower()
    
    @classmethod
    def get_llm_model(cls) -> str:
        """Get LLM model name for technology classification.
        
        Default models per provider:
        - openrouter: "qwen/qwen3.5-27b"
        - openai: "gpt-4o-mini"
        - anthropic: "claude-3-haiku-20240307"
        
        Returns:
            LLM model name.
        """
        provider = cls.get_llm_provider()
        default_models = {
            "openrouter": "qwen/qwen3.5-27b",
            "openai": "gpt-4o-mini",
            "anthropic": "claude-3-haiku-20240307",
        }
        return os.getenv("RSS_LLM_MODEL", default_models.get(provider, "gpt-4o-mini"))
    
    @classmethod
    def get_llm_api_key(cls) -> Optional[str]:
        """Get LLM API key for technology classification.
        
        Priority:
        1. RSS_LLM_API_KEY env var
        2. OPENAI_API_KEY env var (for OpenAI/OpenRouter)
        3. ANTHROPIC_API_KEY env var (for Anthropic)
        
        Returns:
            API key string or None if not configured.
        """
        # Check for specific LLM API key first
        api_key = os.getenv("RSS_LLM_API_KEY", "")
        if api_key:
            return api_key
        
        # Fall back to provider-specific keys
        provider = cls.get_llm_provider()
        if provider in ("openrouter", "openai"):
            return os.getenv("OPENAI_API_KEY")
        elif provider == "anthropic":
            return os.getenv("ANTHROPIC_API_KEY")
        
        return None
    
    @classmethod
    def get_llm_base_url(cls) -> Optional[str]:
        """Get LLM base URL for API calls.
        
        This is useful for:
        - OpenRouter: "https://openrouter.ai/api/v1"
        - Custom endpoints
        
        Returns:
            Base URL string or None for default.
        """
        base_url = os.getenv("RSS_LLM_BASE_URL", "")
        if base_url:
            return base_url
        
        # Auto-configure for OpenRouter
        provider = cls.get_llm_provider()
        if provider == "openrouter":
            return "https://openrouter.ai/api/v1"
        
        return None
    
    @classmethod
    def is_llm_classification_enabled(cls) -> bool:
        """Check if LLM-based technology classification is enabled.
        
        Returns:
            True if LLM classification is enabled and configured, False otherwise.
        """
        provider = cls.get_llm_provider()
        if provider == "none" or not provider:
            return False
        
        # Check if API key is available
        api_key = cls.get_llm_api_key()
        return api_key is not None and len(api_key) > 0
    
    @classmethod
    def get_llm_temperature(cls) -> float:
        """Get LLM temperature for classification.
        
        Returns:
            Temperature value (0.0 to 1.0).
        """
        try:
            return float(os.getenv("RSS_LLM_TEMPERATURE", "0.3"))
        except ValueError:
            return 0.3
    
    @classmethod
    def get_llm_max_tokens(cls) -> int:
        """Get maximum tokens for LLM response.
        
        Returns:
            Maximum tokens for LLM response.
        """
        try:
            return int(os.getenv("RSS_LLM_MAX_TOKENS", "500"))
        except ValueError:
            return 500
    
    @classmethod
    def get_config_summary(cls) -> dict:
        """Get a summary of current configuration.
        
        Returns:
            Dictionary containing current configuration values.
        """
        return {
            "sources_count": len(cls.get_sources()),
            "keywords_count": len(cls.get_keywords()),
            "timeout": cls.get_timeout(),
            "failure_logging_enabled": cls.is_failure_logging_enabled(),
            "log_file": cls.get_log_file(),
            "llm_classification_enabled": cls.is_llm_classification_enabled(),
            "llm_provider": cls.get_llm_provider(),
            "llm_model": cls.get_llm_model(),
        }
