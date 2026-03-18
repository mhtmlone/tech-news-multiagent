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
        url: str,
        error_message: str,
        details: Optional[dict] = None
    ):
        """Log RSS feed fetch failure.

        This logs failures when attempting to fetch an RSS feed URL,
        such as network errors, timeouts, or HTTP errors.

        Args:
            url: The RSS feed URL that failed to fetch.
            error_message: Human-readable error message.
            details: Optional dictionary with additional context (e.g., status_code, exception_type).
        """
        details_str = ""
        if details:
            details_parts = [f"{k}={v}" for k,
                             v in details.items() if v is not None]
            details_str = " | " + \
                " | ".join(details_parts) if details_parts else ""

        self.logger.warning(
            f"RSS_FETCH_FAILURE | url={url} | "
            f"error={error_message}{details_str}"
        )

    def log_content_extraction_failure(
        self,
        url: str,
        error_type: str,
        error_message: str,
        details: Optional[dict] = None
    ):
        """Log article content extraction failure.

        This logs failures when content extraction fails for any reason,
        including network errors, bot detection, or extraction method failures.

        Args:
            url: The URL that failed extraction.
            error_type: Type of error (e.g., "hard_block", "extraction_failed",
                        "forbidden", "network_error", "unexpected_error").
            error_message: Human-readable error message.
            details: Optional dictionary with additional context.
        """
        details_str = ""
        if details:
            # Format details as key=value pairs
            details_parts = [f"{k}={v}" for k,
                             v in details.items() if v is not None]
            details_str = " | " + \
                " | ".join(details_parts) if details_parts else ""

        self.logger.warning(
            f"CONTENT_EXTRACTION_FAILURE | url={url} | "
            f"error_type={error_type} | error_message={error_message}{details_str}"
        )

    def log_parse_failure(
        self,
        url: str,
        error_message: str,
        details: Optional[dict] = None
    ):
        """Log RSS feed parsing failure.

        This logs failures when an RSS feed cannot be parsed, such as
        malformed XML or encoding issues.

        Args:
            url: The RSS feed URL that failed to parse.
            error_message: Human-readable error message.
            details: Optional dictionary with additional context (e.g., bozo, exception_type).
        """
        details_str = ""
        if details:
            details_parts = [f"{k}={v}" for k,
                             v in details.items() if v is not None]
            details_str = " | " + \
                " | ".join(details_parts) if details_parts else ""

        self.logger.warning(
            f"RSS_PARSE_FAILURE | url={url} | "
            f"error={error_message}{details_str}"
        )

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
        operation: str = "fetch"
    ):
        """Log network timeout errors.

        Args:
            url: The URL that timed out.
            operation: The operation that timed out (fetch, extract, etc.).
        """
        self.logger.warning(
            f"NETWORK_TIMEOUT | url={url} | operation={operation}"
        )

    def log_rate_limit(
        self,
        url: str,
        retry_after: Optional[str] = None
    ):
        """Log rate limiting errors.

        Args:
            url: The URL that was rate-limited.
            retry_after: Seconds to wait before retrying (if provided).
        """
        retry_str = f"{retry_after}s" if retry_after else "unknown"
        self.logger.warning(
            f"RATE_LIMIT | url={url} | retry_after={retry_str}"
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
