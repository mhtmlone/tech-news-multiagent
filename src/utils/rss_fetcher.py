"""RSS fetching utilities for fetching and parsing RSS/Atom feeds.

This module provides reusable functions for fetching RSS feeds from various sources,
including fallback mechanisms for sites that require browser automation.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional
import feedparser
import aiohttp

from .content_extractor import fetch_36kr_news_with_playwright

logger = logging.getLogger(__name__)


async def fetch_feed(
    url: str,
    session: Optional[aiohttp.ClientSession] = None,
    failure_logger=None,
    verbose: bool = False,
    timeout: int = 30,
    feed_index: int = 0,
    total_feeds: int = 0
) -> list[dict]:
    """Fetch and parse an RSS/Atom feed from URL.

    Args:
        url: URL of the RSS feed to fetch
        session: Optional aiohttp.ClientSession to use for requests
        failure_logger: Optional FailureLogger instance for logging failures
        verbose: Whether to print verbose output
        timeout: Request timeout in seconds
        feed_index: Index of the feed for progress display
        total_feeds: Total number of feeds for progress display

    Returns:
        List of feed entry dictionaries with title, link, summary, published, source
    """
    entries = []
    is_36kr_feed = "36kr" in url.lower()

    # Create session if not provided
    close_session = False
    if session is None:
        session = aiohttp.ClientSession(
            headers={"User-Agent": "TechNewsAnalyzer/1.0"},
            timeout=aiohttp.ClientTimeout(total=timeout),
        )
        close_session = True

    try:
        feed_progress = f"[{feed_index}/{total_feeds}]" if total_feeds > 0 else ""
        if verbose:
            print(f"  {feed_progress} Fetching RSS feed: {url}")

        async with session.get(url) as response:
            if verbose:
                print(f"    → HTTP {response.status} received")
            if response.status == 200:
                feed_content = await response.text()
                feed = feedparser.parse(feed_content)

                # Check for feed parsing errors
                if feed.bozo and failure_logger:
                    # feedparser sets bozo=1 when there's a parsing error
                    bozo_exception = getattr(feed, 'bozo_exception', None)
                    failure_logger.log_parse_failure(
                        url=url,
                        error_message=str(
                            bozo_exception) if bozo_exception else "Unknown parse error",
                        details={"bozo": True, "exception_type": type(
                            bozo_exception).__name__ if bozo_exception else None}
                    )
                    logger.warning(
                        f"RSS feed parsing error for {url}: {bozo_exception}")

                for entry in feed.entries:
                    published = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        try:
                            published = datetime(
                                *entry.published_parsed[:6])
                        except (TypeError, ValueError):
                            published = datetime.now()
                    elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                        try:
                            published = datetime(*entry.updated_parsed[:6])
                        except (TypeError, ValueError):
                            published = datetime.now()
                    else:
                        published = datetime.now()

                    entries.append(
                        {
                            "title": entry.get("title", ""),
                            "link": entry.get("link", ""),
                            "summary": entry.get("summary", "") or entry.get("description", ""),
                            "published": published,
                            "source": feed.feed.get("title", url),
                        }
                    )
            else:
                # Log non-200 status codes
                if failure_logger:
                    failure_logger.log_rss_fetch_failure(
                        url=url,
                        error_message=f"HTTP {response.status}",
                        details={"status_code": response.status}
                    )
                logger.warning(
                    f"Failed to fetch RSS feed {url}: HTTP {response.status}")

                # Fallback to Playwright for 36kr when RSS fails
                if is_36kr_feed:
                    logger.info(
                        f"Attempting Playwright fallback for 36kr feed...")
                    playwright_entries = await fetch_36kr_news_with_playwright()
                    if playwright_entries:
                        logger.info(
                            f"Playwright fallback successful, got {len(playwright_entries)} entries")
                        return playwright_entries

    except asyncio.TimeoutError:
        if failure_logger:
            failure_logger.log_network_timeout(
                url=url, operation="fetch_feed")
        logger.warning(f"Timeout fetching RSS feed {url}")

        # Fallback to Playwright for 36kr on timeout
        if is_36kr_feed:
            logger.info(
                f"Attempting Playwright fallback for 36kr after timeout...")
            playwright_entries = await fetch_36kr_news_with_playwright()
            if playwright_entries:
                return playwright_entries

    except aiohttp.ClientError as e:
        if failure_logger:
            failure_logger.log_rss_fetch_failure(
                url=url,
                error_message=str(e),
                details={"exception_type": type(e).__name__}
            )
        logger.warning(f"Network error fetching RSS feed {url}: {e}")

        # Fallback to Playwright for 36kr on network error
        if is_36kr_feed:
            logger.info(
                f"Attempting Playwright fallback for 36kr after network error...")
            playwright_entries = await fetch_36kr_news_with_playwright()
            if playwright_entries:
                return playwright_entries

    except Exception as e:
        if failure_logger:
            failure_logger.log_rss_fetch_failure(
                url=url,
                error_message=str(e),
                details={"exception_type": type(e).__name__}
            )
        logger.error(f"Unexpected error fetching RSS feed {url}: {e}")

        # Fallback to Playwright for 36kr on unexpected error
        if is_36kr_feed:
            logger.info(
                f"Attempting Playwright fallback for 36kr after unexpected error...")
            playwright_entries = await fetch_36kr_news_with_playwright()
            if playwright_entries:
                return playwright_entries
    finally:
        if close_session:
            await session.close()

    return entries


async def fetch_all_feeds(
    sources: list[str],
    session: Optional[aiohttp.ClientSession] = None,
    failure_logger=None,
    verbose: bool = False,
    timeout: int = 30
) -> list[dict]:
    """Fetch all RSS feeds from a list of source URLs.

    Args:
        sources: List of RSS feed URLs to fetch
        session: Optional aiohttp.ClientSession to use for requests
        failure_logger: Optional FailureLogger instance for logging failures
        verbose: Whether to print verbose output
        timeout: Request timeout in seconds

    Returns:
        List of all feed entries from all sources
    """
    all_entries = []
    total_feeds = len(sources)

    if verbose:
        print(f"\n  📡 Fetching {total_feeds} RSS feeds...")

    # Create session if not provided
    close_session = False
    if session is None:
        session = aiohttp.ClientSession(
            headers={"User-Agent": "TechNewsAnalyzer/1.0"},
            timeout=aiohttp.ClientTimeout(total=timeout),
        )
        close_session = True

    try:
        # Process feeds sequentially when verbose to show progress
        if verbose:
            for idx, url in enumerate(sources, 1):
                result = await fetch_feed(
                    url, 
                    session=session, 
                    failure_logger=failure_logger, 
                    verbose=verbose,
                    timeout=timeout
                )
                if isinstance(result, list):
                    all_entries.extend(result)
                    print(f"    → Got {len(result)} entries from this feed")
        else:
            # Process feeds in parallel when not verbose (faster)
            tasks = [fetch_feed(url, session=session, failure_logger=failure_logger, 
                                verbose=verbose, timeout=timeout) for url in sources]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, list):
                    all_entries.extend(result)
    finally:
        if close_session:
            await session.close()

    return all_entries
