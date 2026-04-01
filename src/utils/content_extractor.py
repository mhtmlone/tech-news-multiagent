"""Content extraction utilities for fetching and parsing article content from URLs.

This module provides reusable functions for extracting article content from web pages
using multiple fallback strategies including Trafilatura, Newspaper3k, Readability,
and BeautifulSoup.
"""
import re
import logging
import asyncio
import aiohttp
from typing import Optional, Tuple
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Sentinel value returned when a hard block (e.g. DataDome) is detected
HARD_BLOCKED = "__HARD_BLOCKED__"


async def fetch_article_content(
    url: str,
    session: Optional[aiohttp.ClientSession] = None,
    timeout: int = 30,
    failure_logger=None,
    verbose: bool = False
) -> str:
    """Fetch and extract full article content from URL with multiple fallback strategies.

    Tries different extraction libraries in order of preference:
    1. Trafilatura (best for news articles)
    2. Newspaper3k (good general purpose)
    3. Readability-lxml (Mozilla's readability algorithm)
    4. BeautifulSoup (fallback with multiple strategies)
    5. Playwright headless browser (for JS-challenge protected sites like AWS WAF)
       Note: Playwright is skipped for DataDome-protected sites (e.g. Reuters)
           because DataDome uses behavioral analysis that blocks headless browsers.

    Args:
        url: URL of the article to fetch
        session: Optional aiohttp.ClientSession to use for requests
        timeout: Request timeout in seconds
        failure_logger: Optional FailureLogger instance for logging failures
        verbose: Whether to print verbose output

    Returns:
        Extracted article content as string, or empty string if extraction failed
    """
    if verbose:
        print(f"    📄 Fetching article content: {url}")

    # First, try to get HTML content via standard HTTP
    html_content = await _fetch_html_content(
        url, session=session, timeout=timeout, failure_logger=failure_logger
    )

    if html_content and html_content != HARD_BLOCKED:
        # Try different extraction methods in order of preference
        content = (
            extract_with_trafilatura(url, html_content) or
            extract_with_newspaper3k(url) or
            extract_with_readability(html_content) or
            extract_with_beautifulsoup(html_content)
        )

        if content:
            content = re.sub(r'\s+', ' ', content).strip()
            return content

    # If hard-blocked (e.g. DataDome), skip Playwright - it won't help
    if html_content == HARD_BLOCKED:
        # Log the hard block failure
        if failure_logger:
            failure_logger.log_content_extraction_failure(
                url=url,
                error_type="hard_block",
                error_message="DataDome or similar bot protection blocked access",
                details={"block_type": "datadome"}
            )
        return ""

    # Fallback: use Playwright headless browser for JS-challenge protected sites
    # (e.g., AWS WAF Bot Control, Cloudflare Bot Management)
    logger.info(
        f"Standard HTTP extraction failed for {url}, trying Playwright headless browser...")
    playwright_html = await _fetch_html_with_playwright(url)

    if playwright_html:
        content = (
            extract_with_trafilatura(url, playwright_html) or
            extract_with_readability(playwright_html) or
            extract_with_beautifulsoup(playwright_html)
        )

        if content:
            content = re.sub(r'\s+', ' ', content).strip()
            return content

    # Log extraction failure if all methods failed
    if failure_logger:
        failure_logger.log_content_extraction_failure(
            url=url,
            error_type="extraction_failed",
            error_message="All content extraction methods failed",
            details={"tried_methods": [
                "trafilatura", "newspaper3k", "readability", "beautifulsoup", "playwright"]}
        )

    return ""


async def _fetch_html_content(
    url: str,
    session: Optional[aiohttp.ClientSession] = None,
    timeout: int = 30,
    failure_logger=None
) -> str:
    """Fetch raw HTML content from URL.

    Returns empty string if the response is a bot-detection challenge page
    (e.g., AWS WAF HTTP 202 challenge, Cloudflare challenge, DataDome HTTP 401).
    Returns HARD_BLOCKED sentinel value if DataDome or similar protection is detected.
    """
    import aiohttp

    # Create session if not provided
    close_session = False
    if session is None:
        session = aiohttp.ClientSession(
            headers={"User-Agent": "TechNewsAnalyzer/1.0"},
            timeout=aiohttp.ClientTimeout(total=timeout),
        )
        close_session = True

    try:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.text()
            elif response.status == 202:
                # HTTP 202 is commonly used by AWS WAF for JS challenges
                # Check if it's a WAF challenge page
                text = await response.text()
                waf_indicators = [
                    'awsWafCookieDomainList',
                    'AwsWafIntegration',
                    'challenge.js',
                    '__cf_chl',  # Cloudflare challenge
                    'cf-challenge',
                ]
                if any(indicator in text for indicator in waf_indicators):
                    logger.debug(
                        f"AWS WAF challenge detected for {url} (HTTP 202), will try Playwright")
                    return ""  # Signal to use Playwright fallback
                # If it's a real 202 response with content, return it
                return text
            elif response.status == 401:
                # DataDome bot protection returns HTTP 401 with x-datadome header
                if 'x-datadome' in response.headers:
                    dd_action = response.headers.get('x-dd-b', 'unknown')
                    logger.warning(
                        f"DataDome bot protection blocked access to {url} "
                        f"(action={dd_action}). This site requires a real browser "
                        f"with behavioral analysis bypass. Content extraction not possible."
                    )
                    return HARD_BLOCKED  # DataDome cannot be bypassed with Playwright alone
                # Other 401 errors
                logger.debug(f"HTTP 401 for {url}, skipping")
                return ""
            elif response.status == 403:
                # Forbidden - often due to bot detection
                if failure_logger:
                    failure_logger.log_content_extraction_failure(
                        url=url,
                        error_type="forbidden",
                        error_message=f"HTTP 403 Forbidden - possible bot detection",
                        details={"status_code": 403}
                    )
                logger.debug(f"HTTP 403 for {url}, skipping")
                return ""
            elif response.status == 429:
                # Rate limited
                if failure_logger:
                    failure_logger.log_rate_limit(
                        url=url,
                        retry_after=response.headers.get('Retry-After')
                    )
                logger.debug(f"HTTP 429 rate limited for {url}, skipping")
                return ""
            else:
                logger.debug(f"HTTP {response.status} for {url}, skipping")
    except asyncio.TimeoutError:
        if failure_logger:
            failure_logger.log_network_timeout(
                url=url, operation="fetch_html")
        logger.warning(f"Timeout fetching HTML from {url}")
    except aiohttp.ClientError as e:
        if failure_logger:
            failure_logger.log_content_extraction_failure(
                url=url,
                error_type="network_error",
                error_message=str(e),
                details={"exception_type": type(e).__name__}
            )
        logger.warning(f"Network error fetching HTML from {url}: {e}")
    except Exception as e:
        if failure_logger:
            failure_logger.log_content_extraction_failure(
                url=url,
                error_type="unexpected_error",
                error_message=str(e),
                details={"exception_type": type(e).__name__}
            )
        logger.error(f"Unexpected error fetching HTML from {url}: {e}")
    finally:
        if close_session:
            await session.close()

    return ""


async def _fetch_html_with_playwright(url: str) -> str:
    """Fetch HTML content using Playwright headless browser.

    Used as a fallback for sites protected by JavaScript challenges
    such as AWS WAF Bot Control or Cloudflare Bot Management.
    The headless browser executes the challenge JavaScript, obtains
    the required cookies, and then loads the actual page content.
    """
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.0.0 Safari/537.36'
                ),
                viewport={'width': 1280, 'height': 800},
                java_script_enabled=True,
            )
            page = await context.new_page()

            try:
                # Navigate and wait for DOM to be ready
                await page.goto(url, wait_until='domcontentloaded', timeout=30000)

                # Wait for WAF challenge JS to execute and trigger page reload
                # AWS WAF challenge.js runs, sets a cookie, then reloads the page
                await page.wait_for_timeout(5000)

                # Get the rendered HTML content
                html_content = await page.content()

                # Verify we got past the WAF challenge
                waf_indicators = [
                    'awsWafCookieDomainList',
                    'AwsWafIntegration',
                    '__cf_chl',
                ]
                if any(indicator in html_content for indicator in waf_indicators):
                    # Still on challenge page, wait a bit more
                    logger.debug(
                        f"Still on WAF challenge page for {url}, waiting longer...")
                    await page.wait_for_timeout(5000)
                    html_content = await page.content()

                # Check if we successfully got the real page
                if not any(indicator in html_content for indicator in waf_indicators):
                    logger.info(
                        f"Playwright successfully bypassed WAF for {url}")
                    return html_content
                else:
                    logger.warning(
                        f"Playwright could not bypass WAF for {url}")
                    return ""

            except Exception as e:
                logger.warning(
                    f"Playwright page navigation failed for {url}: {e}")
                return ""
            finally:
                await browser.close()

    except ImportError:
        logger.debug(
            "Playwright not installed, skipping headless browser fallback")
    except Exception as e:
        logger.warning(f"Playwright extraction failed for {url}: {e}")
    return ""


async def fetch_36kr_news_with_playwright(max_items: int = 20) -> list[dict]:
    """Fetch news from 36kr using Playwright browser automation.

    This is a fallback method for when the RSS feed is unavailable or blocked.
    36kr.com uses CAPTCHA protection (ByteDance TTGCaptcha) that blocks direct
    HTTP requests, but can be bypassed with a headless browser.

    Args:
        max_items: Maximum number of news items to fetch (default 20)

    Returns:
        List of news entry dictionaries with title, link, summary, published, source
    """
    from datetime import datetime
    entries = []

    try:
        from playwright.async_api import async_playwright

        logger.info(
            "Fetching 36kr news using Playwright browser automation...")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.0.0 Safari/537.36'
                ),
                viewport={'width': 1920, 'height': 1080},
                java_script_enabled=True,
            )
            page = await context.new_page()

            try:
                # Navigate to 36kr newsflashes page
                await page.goto(
                    "https://36kr.com/newsflashes",
                    wait_until='networkidle',
                    timeout=60000
                )

                # Wait for content to load
                await page.wait_for_timeout(3000)

                # Extract news items using the newsflash-item selector
                items = await page.query_selector_all('.newsflash-item')

                for i, item in enumerate(items[:max_items]):
                    try:
                        # Extract title and link
                        title_elem = await item.query_selector('.newsflash-time a')
                        content_elem = await item.query_selector('.newsflash-content')
                        time_elem = await item.query_selector('.newsflash-time')

                        title = ""
                        link = ""
                        summary = ""
                        published = datetime.now()

                        if title_elem:
                            title = await title_elem.inner_text()
                            href = await title_elem.get_attribute('href')
                            if href:
                                # Handle relative URLs
                                if href.startswith('/'):
                                    link = f"https://36kr.com{href}"
                                else:
                                    link = href

                        if content_elem:
                            summary = await content_elem.inner_text()
                            # Use summary as title if no title found
                            if not title:
                                title = summary[:100] + \
                                    "..." if len(
                                        summary) > 100 else summary

                        if title and link:
                            entries.append({
                                "title": title.strip(),
                                "link": link.strip(),
                                "summary": summary.strip(),
                                "published": published,
                                "source": "36kr",
                            })

                    except Exception as e:
                        logger.debug(
                            f"Error extracting 36kr item {i}: {e}")
                        continue

                logger.info(
                    f"Successfully extracted {len(entries)} news items from 36kr via Playwright")

            except Exception as e:
                logger.warning(f"Error navigating 36kr page: {e}")
            finally:
                await browser.close()

    except ImportError:
        logger.warning(
            "Playwright not installed, cannot fetch 36kr news via browser")
    except Exception as e:
        logger.error(f"Failed to fetch 36kr news with Playwright: {e}")

    return entries


def extract_with_trafilatura(url: str, html_content: str) -> str:
    """Extract content using Trafilatura library.

    Trafilatura is specifically designed for news article extraction
    and typically produces the cleanest results.
    """
    try:
        import trafilatura

        # Try extracting from HTML content first
        if html_content:
            content = trafilatura.extract(
                html_content,
                url=url,
                include_comments=False,
                include_tables=False,
                no_fallback=False
            )
            if content and len(content) > 200:
                return content

        # Fallback: fetch directly with trafilatura
        content = trafilatura.fetch_url(url)
        if content:
            extracted = trafilatura.extract(
                content, include_comments=False)
            if extracted and len(extracted) > 200:
                return extracted
    except ImportError:
        print("Trafilatura not installed, skipping...")
    except Exception as e:
        print(f"Trafilatura extraction failed for {url}: {e}")
    return ""


def extract_with_newspaper3k(url: str) -> str:
    """Extract content using Newspaper3k library.

    Newspaper3k is a popular library for article extraction with
    good support for various news sites.
    """
    try:
        from newspaper import Article

        article = Article(url)
        article.download()
        article.parse()

        if article.text and len(article.text) > 200:
            return article.text
    except ImportError:
        print("Newspaper3k not installed, skipping...")
    except Exception as e:
        print(f"Newspaper3k extraction failed for {url}: {e}")
    return ""


def extract_with_readability(html_content: str) -> str:
    """Extract content using Readability-lxml.

    Uses Mozilla's Readability algorithm ported to Python.
    Good for extracting main content from any webpage.
    """
    try:
        from readability import Document

        doc = Document(html_content)
        content = doc.summary()

        # Readability returns HTML, need to extract text
        soup = BeautifulSoup(content, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)

        if text and len(text) > 200:
            return text
    except ImportError:
        print("Readability-lxml not installed, skipping...")
    except Exception as e:
        print(f"Readability extraction failed: {e}")
    return ""


def extract_with_beautifulsoup(html_content: str) -> str:
    """Extract content using BeautifulSoup with multiple fallback strategies.

    This is the final fallback when other libraries fail.
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove script, style, and other non-content elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'advertisement', 'noscript']):
            element.decompose()

        # Try multiple extraction strategies in order of preference
        content = (
            extract_from_article_tag(soup) or
            extract_from_main_tag(soup) or
            extract_from_content_div(soup) or
            extract_from_schema_org(soup) or
            extract_from_meta_tags(soup) or
            extract_from_paragraphs(soup) or
            extract_from_readability_style(soup)
        )

        return content
    except Exception as e:
        print(f"BeautifulSoup extraction failed: {e}")
    return ""


def extract_from_article_tag(soup: BeautifulSoup) -> str:
    """Extract content from <article> tag."""
    article = soup.find('article')
    if article:
        # Remove unwanted elements within article
        for element in article(['script', 'style', 'aside', 'figure', 'figcaption']):
            element.decompose()
        text = article.get_text(separator=' ', strip=True)
        if len(text) > 200:  # Ensure meaningful content
            return text
    return ""


def extract_from_main_tag(soup: BeautifulSoup) -> str:
    """Extract content from <main> tag."""
    main = soup.find('main')
    if main:
        for element in main(['script', 'style', 'aside']):
            element.decompose()
        text = main.get_text(separator=' ', strip=True)
        if len(text) > 200:
            return text
    return ""


def extract_from_content_div(soup: BeautifulSoup) -> str:
    """Extract content from common content container divs."""
    # Common content container patterns
    content_patterns = [
        {'class_': re.compile(
            r'article|content|post|entry|story|body|text', re.I)},
        {'id': re.compile(
            r'article|content|post|entry|story|body|text', re.I)},
        {'class_': re.compile(
            r'article-body|post-content|entry-content|story-content', re.I)},
        {'itemprop': 'articleBody'},
        {'role': 'article'},
        {'class_': re.compile(r'prose|rich-text|editor-content', re.I)},
    ]

    for pattern in content_patterns:
        element = soup.find('div', **pattern)
        if element:
            for unwanted in element(['script', 'style', 'aside', 'figure']):
                unwanted.decompose()
            text = element.get_text(separator=' ', strip=True)
            if len(text) > 200:
                return text
    return ""


def extract_from_schema_org(soup: BeautifulSoup) -> str:
    """Extract content from JSON-LD structured data (Schema.org)."""
    import json

    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        try:
            data = json.loads(script.string)
            # Handle both single objects and arrays
            if isinstance(data, list):
                data = data[0] if data else {}

            # Check for Article or NewsArticle schema
            schema_type = data.get('@type', '')
            if schema_type in ['Article', 'NewsArticle', 'BlogPosting', 'TechArticle']:
                # Try various content fields
                content = (
                    data.get('articleBody') or
                    data.get('text') or
                    data.get('description') or
                    ''
                )
                if content and len(content) > 200:
                    return content
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue
    return ""


def extract_from_meta_tags(soup: BeautifulSoup) -> str:
    """Extract content from meta tags (Open Graph, Twitter Cards, etc.)."""
    # Try Open Graph description
    og_description = soup.find('meta', property='og:description')
    if og_description and og_description.get('content'):
        content = og_description['content']
        if len(content) > 100:
            return content

    # Try Twitter description
    twitter_description = soup.find(
        'meta', attrs={'name': 'twitter:description'})
    if twitter_description and twitter_description.get('content'):
        content = twitter_description['content']
        if len(content) > 100:
            return content

    # Try standard meta description
    meta_description = soup.find('meta', attrs={'name': 'description'})
    if meta_description and meta_description.get('content'):
        content = meta_description['content']
        if len(content) > 100:
            return content

    return ""


def extract_from_paragraphs(soup: BeautifulSoup) -> str:
    """Extract content from all paragraphs as a fallback."""
    paragraphs = soup.find_all('p')
    if paragraphs:
        # Filter out very short paragraphs (likely navigation or ads)
        meaningful_paragraphs = [p.get_text(
            strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 50]
        if meaningful_paragraphs:
            text = ' '.join(meaningful_paragraphs)
            if len(text) > 200:
                return text
    return ""


def extract_from_readability_style(soup: BeautifulSoup) -> str:
    """Extract content using a readability-style approach - find the largest text block."""
    # Get all text-containing elements
    text_elements = soup.find_all(
        ['p', 'div', 'section', 'article', 'span'])

    # Score each element by text length and paragraph count
    best_element = None
    best_score = 0

    for element in text_elements:
        # Skip very short elements
        text = element.get_text(separator=' ', strip=True)
        if len(text) < 200:
            continue

        # Count paragraphs within the element
        p_count = len(element.find_all('p'))

        # Score based on text length and paragraph count
        score = len(text) + (p_count * 100)

        # Bonus for certain class names
        class_attr = element.get('class', [])
        if class_attr:
            class_str = ' '.join(class_attr).lower()
            if any(kw in class_str for kw in ['content', 'article', 'post', 'story', 'body', 'text']):
                score += 500

        # Bonus for certain IDs
        id_attr = element.get('id', '')
        if id_attr and any(kw in id_attr.lower() for kw in ['content', 'article', 'post', 'story', 'body']):
            score += 500

        if score > best_score:
            best_score = score
            best_element = element

    if best_element:
        # Clean up the element
        for unwanted in best_element(['script', 'style', 'aside', 'nav', 'header', 'footer']):
            unwanted.decompose()
        text = best_element.get_text(separator=' ', strip=True)
        if len(text) > 200:
            return text

    return ""
