from .base import BaseAgent
from ..utils.failure_logger import FailureLogger
from ..config.llm_config import LLMConfig
from ..config.rss_config import RSSConfig
from ..utils.entity_extractor import EntityExtractor
from ..storage.sqlite_store import SQLiteStore
from ..models.schemas import TechnologyMention
import asyncio
import aiohttp
import feedparser
import logging
from datetime import datetime, timedelta
from typing import Optional
from bs4 import BeautifulSoup
import re
import uuid

logger = logging.getLogger(__name__)


# Default fallback sources (used when .env is not configured)
DEFAULT_TECH_NEWS_SOURCES = [
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://arstechnica.com/feed/",
    "https://www.wired.com/feed/rss",
    "https://news.ycombinator.com/rss",
    "https://www.zdnet.com/news/rss/",
    "https://thenextweb.com/feed/",
]

# Default fallback keywords (used when .env is not configured)
DEFAULT_TECH_KEYWORDS = [
    "AI",
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "neural network",
    "LLM",
    "large language model",
    "quantum computing",
    "blockchain",
    "cryptocurrency",
    "web3",
    "metaverse",
    "robotics",
    "autonomous",
    "edge computing",
    "cloud computing",
    "serverless",
    "kubernetes",
    "microservices",
    "API",
    "devops",
    "cybersecurity",
    "zero trust",
    "5G",
    "6G",
    "IoT",
    "Internet of Things",
    "augmented reality",
    "virtual reality",
    "AR",
    "VR",
    "mixed reality",
    "biotech",
    "gene editing",
    "CRISPR",
    "nanotechnology",
    "battery technology",
    "renewable energy",
    "solar",
    "fusion",
    "semiconductor",
    "chip",
    "processor",
    "GPU",
    "TPU",
    "neuromorphic",
    "brain-computer interface",
    "autonomous vehicle",
    "electric vehicle",
    "EV",
    "hydrogen fuel",
    "carbon capture",
    "climate tech",
    "agritech",
    "food tech",
    "space technology",
    "satellite",
    "rocket",
    "3D printing",
    "additive manufacturing",
    "material science",
    "graphene",
    "superconductor",
    "RAG",
    "agent",
    "multi-agent",
    "transformer",
    "diffusion model",
    "generative AI",
    "computer vision",
    "NLP",
    "natural language processing",
]


class NewsCollectorAgent(BaseAgent):
    def __init__(
        self,
        sqlite_store: SQLiteStore = None,
        extract_entities: bool = True,
        rss_config: RSSConfig = None,
        verbose: bool = False,
        **kwargs
    ):
        super().__init__(name="NewsCollectorAgent", **kwargs)

        # Initialize RSS configuration (from .env or defaults)
        self.rss_config = rss_config or RSSConfig()
        self.sources = self.rss_config.get_sources()
        self.keywords = self.rss_config.get_keywords()
        self.verbose = verbose

        # Initialize failure logger if enabled
        self.failure_logger = FailureLogger(
        ) if self.rss_config.is_failure_logging_enabled() else None

        self.session: Optional[aiohttp.ClientSession] = None
        self.sqlite_store = sqlite_store or SQLiteStore()
        self.extract_entities = extract_entities
        self.entity_extractor = EntityExtractor() if extract_entities else None

        # Initialize LLM analyzer for technology classification if enabled
        self.llm_analyzer = None
        if LLMConfig.is_enabled():
            from ..utils.llm_analyzer import LLMAnalyzer
            llm_kwargs = LLMConfig.create_llm_kwargs("news_collector")
            self.llm_analyzer = LLMAnalyzer(**llm_kwargs)
            logger.info(
                f"LLM-based technology classification enabled: "
                f"provider={LLMConfig.get_provider()}, "
                f"model={LLMConfig.get_model('news_collector')}"
            )

        # Log configuration on startup
        logger.info(
            f"NewsCollectorAgent initialized with {len(self.sources)} sources, "
            f"{len(self.keywords)} keywords, "
            f"failure logging: {'enabled' if self.failure_logger else 'disabled'}"
        )

    async def _ensure_session(self):
        if self.session is None or self.session.closed:
            timeout = self.rss_config.get_timeout()
            self.session = aiohttp.ClientSession(
                headers={"User-Agent": "TechNewsAnalyzer/1.0"},
                timeout=aiohttp.ClientTimeout(total=timeout),
            )

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    # Sentinel value returned by _fetch_html_content when a hard block (e.g. DataDome)
    # is detected, to skip the Playwright fallback which won't help in that case.
    _HARD_BLOCKED = "__HARD_BLOCKED__"

    async def fetch_article_content(self, url: str) -> str:
        """Fetch and extract full article content from URL with multiple fallback strategies.

        Tries different extraction libraries in order of preference:
        1. Trafilatura (best for news articles)
        2. Newspaper3k (good general purpose)
        3. Readability-lxml (Mozilla's readability algorithm)
        4. BeautifulSoup (fallback with multiple strategies)
        5. Playwright headless browser (for JS-challenge protected sites like AWS WAF)
           Note: Playwright is skipped for DataDome-protected sites (e.g. Reuters)
               because DataDome uses behavioral analysis that blocks headless browsers.
        """
        if self.verbose:
            print(f"    📄 Fetching article content: {url}")
        
        # First, try to get HTML content via standard HTTP
        html_content = await self._fetch_html_content(url)

        if html_content and html_content != self._HARD_BLOCKED:
            # Try different extraction methods in order of preference
            content = (
                self._extract_with_trafilatura(url, html_content) or
                self._extract_with_newspaper3k(url) or
                self._extract_with_readability(html_content) or
                self._extract_with_beautifulsoup(html_content)
            )

            if content:
                content = re.sub(r'\s+', ' ', content).strip()
                return content

        # If hard-blocked (e.g. DataDome), skip Playwright - it won't help
        if html_content == self._HARD_BLOCKED:
            # Log the hard block failure
            if self.failure_logger:
                self.failure_logger.log_content_extraction_failure(
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
        playwright_html = await self._fetch_html_with_playwright(url)

        if playwright_html:
            content = (
                self._extract_with_trafilatura(url, playwright_html) or
                self._extract_with_readability(playwright_html) or
                self._extract_with_beautifulsoup(playwright_html)
            )

            if content:
                content = re.sub(r'\s+', ' ', content).strip()
                return content

        # Log extraction failure if all methods failed
        if self.failure_logger:
            self.failure_logger.log_content_extraction_failure(
                url=url,
                error_type="extraction_failed",
                error_message="All content extraction methods failed",
                details={"tried_methods": [
                    "trafilatura", "newspaper3k", "readability", "beautifulsoup", "playwright"]}
            )

        return ""

    async def _fetch_html_content(self, url: str) -> str:
        """Fetch raw HTML content from URL.

        Returns empty string if the response is a bot-detection challenge page
        (e.g., AWS WAF HTTP 202 challenge, Cloudflare challenge, DataDome HTTP 401).
        """
        await self._ensure_session()
        try:
            async with self.session.get(url) as response:
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
                        return self._HARD_BLOCKED  # DataDome cannot be bypassed with Playwright alone
                    # Other 401 errors
                    logger.debug(f"HTTP 401 for {url}, skipping")
                    return ""
                elif response.status == 403:
                    # Forbidden - often due to bot detection
                    if self.failure_logger:
                        self.failure_logger.log_content_extraction_failure(
                            url=url,
                            error_type="forbidden",
                            error_message=f"HTTP 403 Forbidden - possible bot detection",
                            details={"status_code": 403}
                        )
                    logger.debug(f"HTTP 403 for {url}, skipping")
                    return ""
                elif response.status == 429:
                    # Rate limited
                    if self.failure_logger:
                        self.failure_logger.log_rate_limit(
                            url=url,
                            retry_after=response.headers.get('Retry-After')
                        )
                    logger.debug(f"HTTP 429 rate limited for {url}, skipping")
                    return ""
                else:
                    logger.debug(f"HTTP {response.status} for {url}, skipping")
        except asyncio.TimeoutError:
            if self.failure_logger:
                self.failure_logger.log_network_timeout(
                    url=url, operation="fetch_html")
            logger.warning(f"Timeout fetching HTML from {url}")
        except aiohttp.ClientError as e:
            if self.failure_logger:
                self.failure_logger.log_content_extraction_failure(
                    url=url,
                    error_type="network_error",
                    error_message=str(e),
                    details={"exception_type": type(e).__name__}
                )
            logger.warning(f"Network error fetching HTML from {url}: {e}")
        except Exception as e:
            if self.failure_logger:
                self.failure_logger.log_content_extraction_failure(
                    url=url,
                    error_type="unexpected_error",
                    error_message=str(e),
                    details={"exception_type": type(e).__name__}
                )
            logger.error(f"Unexpected error fetching HTML from {url}: {e}")
        return ""

    async def _fetch_html_with_playwright(self, url: str) -> str:
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

    async def fetch_36kr_news_with_playwright(self, max_items: int = 20) -> list[dict]:
        """Fetch news from 36kr using Playwright browser automation.

        This is a fallback method for when the RSS feed is unavailable or blocked.
        36kr.com uses CAPTCHA protection (ByteDance TTGCaptcha) that blocks direct
        HTTP requests, but can be bypassed with a headless browser.

        Args:
            max_items: Maximum number of news items to fetch (default 20)

        Returns:
            List of news entry dictionaries with title, link, summary, published, source
        """
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

    def _extract_with_trafilatura(self, url: str, html_content: str) -> str:
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

    def _extract_with_newspaper3k(self, url: str) -> str:
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

    def _extract_with_readability(self, html_content: str) -> str:
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

    def _extract_with_beautifulsoup(self, html_content: str) -> str:
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
                self._extract_from_article_tag(soup) or
                self._extract_from_main_tag(soup) or
                self._extract_from_content_div(soup) or
                self._extract_from_schema_org(soup) or
                self._extract_from_meta_tags(soup) or
                self._extract_from_paragraphs(soup) or
                self._extract_from_readability_style(soup)
            )

            return content
        except Exception as e:
            print(f"BeautifulSoup extraction failed: {e}")
        return ""

    def _extract_from_article_tag(self, soup: BeautifulSoup) -> str:
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

    def _extract_from_main_tag(self, soup: BeautifulSoup) -> str:
        """Extract content from <main> tag."""
        main = soup.find('main')
        if main:
            for element in main(['script', 'style', 'aside']):
                element.decompose()
            text = main.get_text(separator=' ', strip=True)
            if len(text) > 200:
                return text
        return ""

    def _extract_from_content_div(self, soup: BeautifulSoup) -> str:
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

    def _extract_from_schema_org(self, soup: BeautifulSoup) -> str:
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

    def _extract_from_meta_tags(self, soup: BeautifulSoup) -> str:
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

    def _extract_from_paragraphs(self, soup: BeautifulSoup) -> str:
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

    def _extract_from_readability_style(self, soup: BeautifulSoup) -> str:
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

    async def fetch_feed(self, url: str, feed_index: int = 0, total_feeds: int = 0) -> list[dict]:
        await self._ensure_session()
        entries = []
        is_36kr_feed = "36kr" in url.lower()
        
        if self.verbose:
            feed_progress = f"[{feed_index}/{total_feeds}]" if total_feeds > 0 else ""
            print(f"  {feed_progress} Fetching RSS feed: {url}")

        try:
            async with self.session.get(url) as response:
                if self.verbose:
                    print(f"    → HTTP {response.status} received")
                if response.status == 200:
                    feed_content = await response.text()
                    feed = feedparser.parse(feed_content)

                    # Check for feed parsing errors
                    if feed.bozo and self.failure_logger:
                        # feedparser sets bozo=1 when there's a parsing error
                        bozo_exception = getattr(feed, 'bozo_exception', None)
                        self.failure_logger.log_parse_failure(
                            url=url,
                            error_message=str(
                                bozo_exception) if bozo_exception else "Unknown parse error",
                            details={"bozo": True, "exception_type": type(
                                bozo_exception).__name__ if bozo_exception else None}
                        )
                        logger.warning(
                            f"RSS feed parsing error for {url}: {bozo_exception}")

                    for entry in feed.entries[:20]:
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
                    if self.failure_logger:
                        self.failure_logger.log_rss_fetch_failure(
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
                        playwright_entries = await self.fetch_36kr_news_with_playwright()
                        if playwright_entries:
                            logger.info(
                                f"Playwright fallback successful, got {len(playwright_entries)} entries")
                            return playwright_entries

        except asyncio.TimeoutError:
            if self.failure_logger:
                self.failure_logger.log_network_timeout(
                    url=url, operation="fetch_feed")
            logger.warning(f"Timeout fetching RSS feed {url}")

            # Fallback to Playwright for 36kr on timeout
            if is_36kr_feed:
                logger.info(
                    f"Attempting Playwright fallback for 36kr after timeout...")
                playwright_entries = await self.fetch_36kr_news_with_playwright()
                if playwright_entries:
                    return playwright_entries

        except aiohttp.ClientError as e:
            if self.failure_logger:
                self.failure_logger.log_rss_fetch_failure(
                    url=url,
                    error_message=str(e),
                    details={"exception_type": type(e).__name__}
                )
            logger.warning(f"Network error fetching RSS feed {url}: {e}")

            # Fallback to Playwright for 36kr on network error
            if is_36kr_feed:
                logger.info(
                    f"Attempting Playwright fallback for 36kr after network error...")
                playwright_entries = await self.fetch_36kr_news_with_playwright()
                if playwright_entries:
                    return playwright_entries

        except Exception as e:
            if self.failure_logger:
                self.failure_logger.log_rss_fetch_failure(
                    url=url,
                    error_message=str(e),
                    details={"exception_type": type(e).__name__}
                )
            logger.error(f"Unexpected error fetching RSS feed {url}: {e}")

            # Fallback to Playwright for 36kr on unexpected error
            if is_36kr_feed:
                logger.info(
                    f"Attempting Playwright fallback for 36kr after unexpected error...")
                playwright_entries = await self.fetch_36kr_news_with_playwright()
                if playwright_entries:
                    return playwright_entries

        return entries

    async def fetch_all_feeds(self) -> list[dict]:
        await self._ensure_session()
        all_entries = []
        total_feeds = len(self.sources)
        
        if self.verbose:
            print(f"\n  📡 Fetching {total_feeds} RSS feeds...")

        # Process feeds sequentially when verbose to show progress
        if self.verbose:
            for idx, url in enumerate(self.sources, 1):
                result = await self.fetch_feed(url, feed_index=idx, total_feeds=total_feeds)
                if isinstance(result, list):
                    all_entries.extend(result)
                    print(f"    → Got {len(result)} entries from this feed")
        else:
            # Process feeds in parallel when not verbose (faster)
            tasks = [self.fetch_feed(url) for url in self.sources]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, list):
                    all_entries.extend(result)

        return all_entries

    def filter_new_entries(self, entries: list[dict]) -> list[dict]:
        """Filter out entries with URLs that have already been collected.

        Uses batch URL checking against the SQLite database for efficiency.
        Logs duplicate URLs if failure logging is enabled.

        Args:
            entries: List of entry dictionaries with 'link' keys

        Returns:
            List of entries with new (not previously collected) URLs
        """
        if not entries:
            return []

        # Extract all URLs from entries
        urls = [entry.get("link") for entry in entries if entry.get("link")]

        if not urls:
            return entries

        # Batch check which URLs already exist in the database
        existing_urls = self.sqlite_store.get_urls_batch(urls)

        # Filter entries to only those with new URLs
        new_entries = []
        duplicate_count = 0

        for entry in entries:
            url = entry.get("link")
            if url and url in existing_urls:
                duplicate_count += 1
                # Log the duplicate
                if self.failure_logger:
                    self.failure_logger.log_url_duplicate(
                        url=url,
                        title=entry.get("title", ""),
                        source=entry.get("source", "")
                    )
                logger.debug(f"Skipping duplicate URL: {url}")
            else:
                new_entries.append(entry)

        if duplicate_count > 0:
            logger.info(
                f"Filtered out {duplicate_count} duplicate URLs, {len(new_entries)} new entries remaining")

        return new_entries

    def is_technology_related(self, text: str) -> tuple[bool, list[str]]:
        """Check if text is technology-related using keyword matching.

        This is the synchronous keyword-based method. For LLM-based classification,
        use is_technology_related_async() instead.

        Args:
            text: Text to analyze for technology keywords.

        Returns:
            Tuple of (is_tech_related: bool, matched_keywords: list[str])
        """
        text_lower = text.lower()
        matched_keywords = []

        for keyword in self.keywords:
            if keyword.lower() in text_lower:
                matched_keywords.append(keyword)

        return len(matched_keywords) > 0, matched_keywords

    async def is_technology_related_async(self, title: str, summary: str = "") -> tuple[bool, list[str]]:
        """Check if an article is technology-related using LLM or keyword matching.

        If LLM classification is enabled (via RSS_LLM_PROVIDER), uses the LLM
        to analyze the article title and summary. Otherwise, falls back to
        keyword-based matching.

        Args:
            title: Article title to analyze.
            summary: Optional article summary for additional context.

        Returns:
            Tuple of (is_tech_related: bool, tech_topics: list[str])
        """
        # Use LLM if available and configured
        if self.llm_analyzer is not None:
            try:
                is_tech, topics = await self.llm_analyzer.is_technology_related(title, summary)
                logger.debug(
                    f"LLM classification for '{title[:50]}...': is_tech={is_tech}, topics={topics}")
                return is_tech, topics
            except Exception as e:
                logger.warning(
                    f"LLM classification failed, falling back to keywords: {e}")
                # Fall through to keyword-based matching

        # Fallback to keyword-based matching
        combined_text = f"{title} {summary}"
        return self.is_technology_related(combined_text)

    def calculate_relevance(self, text: str, matched_keywords: list[str]) -> float:
        """Calculate relevance score using keyword-based matching.

        This is the synchronous keyword-based method. For LLM-based assessment,
        use calculate_relevance_async() instead.

        Args:
            text: Text to analyze.
            matched_keywords: List of matched technology keywords.

        Returns:
            Relevance score (0.0 to 1.0).
        """
        if not matched_keywords:
            return 0.0

        text_lower = text.lower()
        score = 0.0

        for keyword in matched_keywords:
            count = text_lower.count(keyword.lower())
            weight = 1.0 if len(keyword.split()) > 1 else 0.5
            score += count * weight

        score = min(score / 10.0, 1.0)
        return score

    async def calculate_relevance_async(
        self,
        title: str,
        content: str = "",
        tech_topics: list[str] = None
    ) -> float:
        """Calculate relevance score using LLM or keyword-based matching.

        If LLM classification is enabled (via RSS_LLM_PROVIDER), uses the LLM
        to assess article relevance. Otherwise, falls back to keyword-based
        matching.

        Args:
            title: Article title to analyze.
            content: Optional article content or summary.
            tech_topics: Optional list of technology topics already identified.

        Returns:
            Relevance score (0.0 to 1.0).
        """
        # Use LLM if available and configured
        if self.llm_analyzer is not None:
            try:
                result = await self.llm_analyzer.calculate_relevance(
                    title=title,
                    content=content,
                    tech_topics=tech_topics
                )
                score = result.get("relevance_score", 0.5)
                logger.debug(
                    f"LLM relevance for '{title[:50]}...': score={score:.2f}, "
                    f"reasoning={result.get('reasoning', 'N/A')}"
                )
                return score
            except Exception as e:
                logger.warning(
                    f"LLM relevance calculation failed, falling back to keywords: {e}")
                # Fall through to keyword-based matching

        # Fallback to keyword-based matching
        combined_text = f"{title} {content}"
        return self.calculate_relevance(combined_text, tech_topics or [])

    async def analyze_sentiment(self, text: str) -> float:
        positive_words = [
            "breakthrough",
            "innovative",
            "revolutionary",
            "promising",
            "exciting",
            "impressive",
            "advanced",
            "successful",
            "growth",
            "improve",
            "better",
            "faster",
            "efficient",
            "powerful",
            "leading",
            "cutting-edge",
            "game-changing",
            "transformative",
        ]

        negative_words = [
            "failed",
            "failure",
            "concern",
            "risk",
            "threat",
            "problem",
            "issue",
            "challenge",
            "decline",
            "slow",
            "weak",
            "lagging",
            "controversial",
            "criticism",
            "lawsuit",
            "ban",
            "investigation",
        ]

        text_lower = text.lower()
        positive_count = sum(
            1 for word in positive_words if word in text_lower)
        negative_count = sum(
            1 for word in negative_words if word in text_lower)

        total = positive_count + negative_count
        if total == 0:
            return 0.0

        score = (positive_count - negative_count) / total
        return max(-1.0, min(1.0, score))

    async def process(self, input_data: Optional[dict] = None) -> list[TechnologyMention]:
        config = input_data or {}
        max_age_days = config.get("max_age_days", 7)
        custom_sources = config.get("sources", self.sources)

        if custom_sources:
            self.sources = custom_sources

        cutoff_date = datetime.now() - timedelta(days=max_age_days)

        # Fetch all RSS feed entries
        if self.verbose:
            print("\n📡 Fetching RSS feeds...")
        entries = await self.fetch_all_feeds()
        logger.info(
            f"Fetched {len(entries)} total entries from {len(self.sources)} sources")
        
        if self.verbose:
            print(f"  ✓ Fetched {len(entries)} total entries from {len(self.sources)} sources")

        # Filter out entries with URLs that have already been collected
        entries = self.filter_new_entries(entries)
        logger.info(
            f"Processing {len(entries)} new entries after deduplication")
        
        if self.verbose:
            print(f"  ✓ {len(entries)} new entries after deduplication")

        technology_mentions = []
        stored_article_ids = []
        
        if self.verbose and entries:
            print(f"\n📰 Processing {len(entries)} articles...")

        for idx, entry in enumerate(entries, 1):
            if entry["published"] and entry["published"] < cutoff_date:
                continue

            if self.verbose:
                title_preview = entry['title'][:60] + "..." if len(entry['title']) > 60 else entry['title']
                print(f"  [{idx}/{len(entries)}] Analyzing: {title_preview}")

            # Use LLM-based classification if available, otherwise fall back to keywords
            is_tech, tech_topics = await self.is_technology_related_async(
                entry['title'], entry['summary']
            )

            if not is_tech:
                if self.verbose:
                    print(f"      → Skipped (not tech-related)")
                continue

            # Use LLM-based relevance assessment if available, otherwise fall back to keywords
            relevance = await self.calculate_relevance_async(
                entry['title'], entry['summary'], tech_topics
            )

            if relevance < 0.1:
                if self.verbose:
                    print(f"      → Skipped (relevance too low: {relevance:.2f})")
                continue

            sentiment = await self.analyze_sentiment(f"{entry['title']} {entry['summary']}")
            
            if self.verbose:
                print(f"      → Tech article found (relevance: {relevance:.2f}, topics: {', '.join(tech_topics[:3])}{'...' if len(tech_topics) > 3 else ''})")

            # Fetch full article content
            article_content = await self.fetch_article_content(entry["link"])

            # Log articles where content extraction failed
            if not article_content:
                logger.warning(
                    "Failed to extract article content - URL: %s, Title: %s, Source: %s",
                    entry["link"],
                    entry["title"],
                    entry["source"]
                )

            # Use full content for summary if available, otherwise fall back to RSS summary
            full_text = article_content if article_content else entry["summary"]
            summary_for_mention = full_text if full_text else ""

            mention = TechnologyMention(
                source=entry["source"],
                url=entry["link"],
                title=entry["title"],
                published_date=entry["published"],
                summary=summary_for_mention,
                sentiment_score=sentiment,
                relevance_score=relevance,
            )

            technology_mentions.append(mention)

            # Store article in SQLite with full content
            article_data = {
                "id": str(uuid.uuid4()),
                "title": entry["title"],
                "url": entry["link"],
                "source": entry["source"],
                "published_date": entry["published"].isoformat() if entry["published"] else None,
                "summary": entry["summary"] if entry["summary"] else "",
                "content": article_content,  # Store full article content
                "sentiment_score": sentiment,
                "relevance_score": relevance,
                "keywords": tech_topics,  # Technology topics identified by LLM or keyword matching
            }

            article_id = self.sqlite_store.store_article(article_data)
            stored_article_ids.append(article_id)

            # Extract and store entities from full content
            if self.extract_entities and self.entity_extractor:
                text = f"{entry['title']} {full_text}"
                entities = self.entity_extractor.extract_all(text)

                company_ids = []
                for company in entities.get("companies", []):
                    company_id = self.sqlite_store.store_company({
                        "name": company["name"],
                        "country": company.get("country"),
                    })
                    company_ids.append(company_id)

                country_ids = []
                for country in entities.get("countries", []):
                    country_id = self.sqlite_store.store_country({
                        "name": country["name"],
                        "code": country.get("code"),
                    })
                    country_ids.append(country_id)

                # Link article with entities
                if company_ids or country_ids:
                    self.sqlite_store.link_article_entities(
                        article_id, company_ids, country_ids
                    )

        technology_mentions.sort(key=lambda x: (
            x.relevance_score, x.published_date), reverse=True)

        self.send_message(
            recipient="TechnologyAnalyzerAgent",
            message_type="news_mentions",
            content={
                "mentions": [mention.model_dump(mode="json") for mention in technology_mentions],
                "count": len(technology_mentions),
                "collected_at": datetime.now().isoformat(),
                "stored_article_ids": stored_article_ids,
            },
        )

        await self.close()

        return technology_mentions
