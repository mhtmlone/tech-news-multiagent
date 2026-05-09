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

from .defaults import (
    DEFAULT_RSS_SOURCES,
    DEFAULT_TECH_KEYWORDS,
    DEFAULT_HTTP_TIMEOUT,
    DEFAULT_FAILURE_LOG_PATH,
)

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

    # Reference defaults from centralized defaults module
    DEFAULT_SOURCES = DEFAULT_RSS_SOURCES
    DEFAULT_KEYWORDS = DEFAULT_TECH_KEYWORDS

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
            with open(path, "r", encoding="utf-8") as f:
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
                        s["url"] if isinstance(s, dict) else s for s in data["sources"]
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
            return int(os.getenv("RSS_CONTENT_TIMEOUT", str(DEFAULT_HTTP_TIMEOUT)))
        except ValueError:
            return DEFAULT_HTTP_TIMEOUT

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
        return os.getenv("RSS_LOG_FILE", DEFAULT_FAILURE_LOG_PATH)

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
            if source and (
                source.startswith("http://") or source.startswith("https://")
            ):
                valid_sources.append(source)
        return valid_sources
