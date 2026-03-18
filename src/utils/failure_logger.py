"""Failure logging module for RSS feed collection.

This module provides file-based logging for all failures that occur during
RSS feed collection, including fetch failures, parse failures, and content
extraction failures.
"""

import logging
from datetime import datetime
from typing import Optional, List
from pathlib import Path


class FailureLogger:
    """File-based failure logging for RSS feed collection.
    
    This class provides a simple, lightweight approach to logging failures
    without database overhead. All failures are written to a dedicated log file
    with structured formatting for easy debugging and monitoring.
    
    Log Format:
        TIMESTAMP - LEVEL - FAILURE_TYPE | key=value | key=value ...
    
    Example:
        >>> logger = FailureLogger("./logs/rss_failures.log")
        >>> logger.log_rss_fetch_failure(
        ...     source_url="https://example.com/feed",
        ...     error=Exception("Connection timeout"),
        ...     http_status=None
        ... )
    """
    
    def __init__(self, log_file: str = "./logs/rss_failures.log"):
        """Initialize the failure logger.
        
        Args:
            log_file: Path to the log file. Parent directories will be created
                automatically if they don't exist.
        """
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Setup file logger
        self.logger = logging.getLogger("rss_failures")
        self.logger.setLevel(logging.WARNING)
        
        # Remove existing handlers to avoid duplicates
        self.logger.handlers = []
        
        # File handler for persistent logging
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        self.logger.addHandler(file_handler)
        
        # Console handler for immediate feedback
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        self.logger.addHandler(console_handler)
    
    def log_rss_fetch_failure(
        self,
        source_url: str,
        error: Exception,
        http_status: Optional[int] = None
    ):
        """Log RSS feed fetch failure.
        
        This logs failures when attempting to fetch an RSS feed URL,
        such as network errors, timeouts, or HTTP errors.
        
        Args:
            source_url: The RSS feed URL that failed to fetch.
            error: The exception that occurred.
            http_status: HTTP status code if available (e.g., 403, 500).
        """
        status_str = str(http_status) if http_status else "N/A"
        self.logger.warning(
            f"RSS_FETCH_FAILURE | source={source_url} | "
            f"status={status_str} | error={self._format_error(error)}"
        )
    
    def log_content_extraction_failure(
        self,
        article_url: str,
        article_title: str,
        source: str,
        extraction_methods_tried: Optional[List[str]] = None
    ):
        """Log article content extraction failure.
        
        This logs failures when all content extraction methods fail
        to extract meaningful content from an article URL.
        
        Args:
            article_url: The article URL that failed extraction.
            article_title: The title of the article (truncated if too long).
            source: The RSS source where the article was found.
            extraction_methods_tried: List of extraction methods attempted.
        """
        # Truncate title if too long
        title_display = article_title[:50] + "..." if len(article_title) > 50 else article_title
        methods_str = ", ".join(extraction_methods_tried) if extraction_methods_tried else "all methods"
        
        self.logger.warning(
            f"CONTENT_EXTRACTION_FAILURE | url={article_url} | "
            f"title={title_display} | source={source} | methods_tried={methods_str}"
        )
    
    def log_parse_failure(
        self,
        source_url: str,
        error: Exception,
        raw_content_sample: Optional[str] = None
    ):
        """Log RSS feed parsing failure.
        
        This logs failures when an RSS feed cannot be parsed, such as
        malformed XML or encoding issues.
        
        Args:
            source_url: The RSS feed URL that failed to parse.
            error: The exception that occurred during parsing.
            raw_content_sample: Optional sample of the raw content for debugging.
        """
        message = (
            f"RSS_PARSE_FAILURE | source={source_url} | "
            f"error={self._format_error(error)}"
        )
        
        if raw_content_sample:
            # Include first 200 chars of raw content for debugging
            sample = raw_content_sample[:200].replace('\n', ' ')
            message += f" | content_sample={sample}..."
        
        self.logger.warning(message)
    
    def log_keyword_filter_failure(
        self,
        source_url: str,
        entries_count: int,
        filtered_count: int
    ):
        """Log when keyword filtering results in no articles.
        
        This is an informational log when a feed is successfully fetched
        but no articles match the configured keywords.
        
        Args:
            source_url: The RSS feed URL.
            entries_count: Total number of entries in the feed.
            filtered_count: Number of entries after filtering (typically 0).
        """
        if filtered_count == 0 and entries_count > 0:
            self.logger.info(
                f"KEYWORD_FILTER_RESULT | source={source_url} | "
                f"total_entries={entries_count} | filtered_count={filtered_count} | "
                f"note='No articles matched keywords'"
            )
    
    def log_url_duplicate(
        self,
        url: str,
        source: str,
        title: Optional[str] = None
    ):
        """Log when a duplicate URL is detected.
        
        This logs when an article URL has already been collected
        and is skipped.
        
        Args:
            url: The duplicate article URL.
            source: The RSS source where the article was found.
            title: Optional title of the duplicate article.
        """
        title_str = ""
        if title:
            # Truncate title if too long
            title_display = title[:50] + "..." if len(title) > 50 else title
            title_str = f" | title={title_display}"
        
        self.logger.info(
            f"URL_DUPLICATE | url={url} | source={source}{title_str} | action='skipped'"
        )
    
    def log_network_timeout(
        self,
        url: str,
        timeout_seconds: int,
        operation: str = "fetch"
    ):
        """Log network timeout errors.
        
        Args:
            url: The URL that timed out.
            timeout_seconds: The timeout duration in seconds.
            operation: The operation that timed out (fetch, extract, etc.).
        """
        self.logger.warning(
            f"NETWORK_TIMEOUT | url={url} | operation={operation} | "
            f"timeout={timeout_seconds}s"
        )
    
    def log_rate_limit(
        self,
        source_url: str,
        retry_after: Optional[int] = None
    ):
        """Log rate limiting errors.
        
        Args:
            source_url: The URL that was rate-limited.
            retry_after: Seconds to wait before retrying (if provided).
        """
        retry_str = f"{retry_after}s" if retry_after else "unknown"
        self.logger.warning(
            f"RATE_LIMIT | source={source_url} | retry_after={retry_str}"
        )
    
    def _format_error(self, error: Exception) -> str:
        """Format an exception for logging.
        
        Args:
            error: The exception to format.
            
        Returns:
            Formatted error string.
        """
        error_type = type(error).__name__
        error_msg = str(error).replace('\n', ' ')[:200]
        return f"{error_type}: {error_msg}"
    
    def get_log_file_path(self) -> Path:
        """Get the path to the log file.
        
        Returns:
            Path object for the log file.
        """
        return self.log_file
    
    def read_recent_failures(self, lines: int = 100) -> List[str]:
        """Read recent failures from the log file.
        
        Args:
            lines: Number of lines to read from the end of the file.
            
        Returns:
            List of log lines, most recent last.
        """
        if not self.log_file.exists():
            return []
        
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                return all_lines[-lines:] if len(all_lines) > lines else all_lines
        except Exception:
            return []
