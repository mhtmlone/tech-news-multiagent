from .base import BaseAgent
from ..utils.failure_logger import FailureLogger
from ..config.llm_config import LLMConfig
from ..config.rss_config import RSSConfig
from ..config.defaults import SENTIMENT_POSITIVE_WORDS, SENTIMENT_NEGATIVE_WORDS
from ..utils.entity_extractor import EntityExtractor
from ..utils.content_extractor import (
    fetch_article_content as util_fetch_article_content,
    fetch_36kr_news_with_playwright as util_fetch_36kr_news,
)
from ..utils.rss_fetcher import fetch_all_feeds
from ..storage.sqlite_store import SQLiteStore
from ..models.schemas import TechnologyMention
import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import Optional
import re
import uuid

logger = logging.getLogger(__name__)


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

        # Initialize LLM analyzer for technology classification if enabled
        self.llm_analyzer = None
        if LLMConfig.is_enabled():
            from ..utils.llm_analyzer import LLMAnalyzer
            llm_kwargs = LLMConfig.create_llm_kwargs("news_collector")
            llm_kwargs["verbose"] = self.verbose
            self.llm_analyzer = LLMAnalyzer(**llm_kwargs)
            logger.info(
                f"LLM-based technology classification enabled: "
                f"provider={LLMConfig.get_provider()}, "
                f"model={LLMConfig.get_model('news_collector')}"
            )

        # Initialize entity extractor with LLM support if available
        self.entity_extractor = EntityExtractor(
            use_llm=self.llm_analyzer is not None,
            llm_analyzer=self.llm_analyzer
        ) if extract_entities else None

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
        return await util_fetch_article_content(
            url=url,
            session=self.session,
            timeout=self.rss_config.get_timeout(),
            failure_logger=self.failure_logger,
            verbose=self.verbose
        )

    async def fetch_all_feeds(self) -> list[dict]:
        """Fetch all RSS feeds from configured sources.
        
        Returns:
            List of all feed entries from all sources
        """
        await self._ensure_session()
        total_feeds = len(self.sources)

        if self.verbose:
            print(f"\n  📡 Fetching {total_feeds} RSS feeds...")

        return await fetch_all_feeds(
            sources=self.sources,
            session=self.session,
            failure_logger=self.failure_logger,
            verbose=self.verbose,
            timeout=self.rss_config.get_timeout()
        )

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
        use analyze_article_relevance() instead.

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

    async def analyze_article_relevance(
        self,
        title: str,
        summary: str = ""
    ) -> tuple[bool, list[str], float]:
        """Analyze if an article is technology-related and calculate its relevance.

        Combines technology classification and relevance calculation into a single
        method for efficiency. If LLM is enabled, makes a single LLM call instead
        of two separate calls.

        Args:
            title: Article title to analyze.
            summary: Optional article summary for additional context.

        Returns:
            Tuple of (is_tech_related: bool, tech_topics: list[str], relevance_score: float)
        """
        # Use LLM if available and configured - single call for both classification and relevance
        if self.llm_analyzer is not None:
            try:
                is_tech, topics, relevance = await self.llm_analyzer.analyze_article_relevance(
                    title, summary
                )
                logger.debug(
                    f"LLM analysis for '{title[:50]}...': is_tech={is_tech}, "
                    f"topics={topics}, relevance={relevance:.2f}"
                )
                return is_tech, topics, relevance
            except Exception as e:
                logger.warning(
                    f"LLM analysis failed, falling back to keywords: {e}")
                # Fall through to keyword-based matching

        # Fallback to keyword-based matching
        combined_text = f"{title} {summary}"
        is_tech, topics = self.is_technology_related(combined_text)
        relevance = self.calculate_relevance(combined_text, topics)
        return is_tech, topics, relevance

    def calculate_relevance(self, text: str, matched_keywords: list[str]) -> float:
        """Calculate relevance score using keyword-based matching.

        This is the synchronous keyword-based method. For LLM-based assessment,
        use analyze_article_relevance() instead.

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

    async def analyze_sentiment(self, text: str) -> float:
        text_lower = text.lower()
        positive_count = sum(
            1 for word in SENTIMENT_POSITIVE_WORDS if word in text_lower)
        negative_count = sum(
            1 for word in SENTIMENT_NEGATIVE_WORDS if word in text_lower)

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
            print(
                f"  ✓ Fetched {len(entries)} total entries from {len(self.sources)} sources")

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
                title_preview = entry['title'][:60] + \
                    "..." if len(entry['title']) > 60 else entry['title']
                print(f"  [{idx}/{len(entries)}] Analyzing: {title_preview}")

            # Use combined LLM-based analysis if available, otherwise fall back to keywords
            is_tech, tech_topics, relevance = await self.analyze_article_relevance(
                entry['title'], entry['summary']
            )

            if self.verbose:
                if is_tech:
                    print(
                        f"      → Tech article (relevance: {relevance:.2f}, topics: {', '.join(tech_topics[:3])}{'...' if len(tech_topics) > 3 else ''})")
                else:
                    print(f"      → Non-tech article (stored for deduplication)")

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

            sentiment = await self.analyze_sentiment(full_text)

            # Store ALL articles in SQLite for deduplication purposes
            # This ensures we don't re-process non-tech or low-relevance articles
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
                "is_tech_related": is_tech,  # Track whether article is tech-related
                "keywords": tech_topics,  # Technology topics identified by LLM or keyword matching
            }

            article_id = self.sqlite_store.store_article(article_data)
            stored_article_ids.append(article_id)

            # Only create technology mentions and extract entities for tech-related articles
            if is_tech and relevance >= 0.1:
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

                # Extract and store entities from full content using unified extraction
                if self.extract_entities and self.entity_extractor:
                    # Use unified extraction that gets technologies, companies, and countries
                    entities = await self.entity_extractor.extract_all_unified(
                        title=entry['title'],
                        content=full_text,
                        summary=entry.get('summary', '')
                    )

                    # Store companies and link to article
                    company_ids = []
                    company_data = []
                    for company in entities.get("companies", []):
                        company_id = self.sqlite_store.store_company({
                            "name": company["name"],
                            "country": company.get("country"),
                            "industry": company.get("industry"),
                        })
                        company_ids.append(company_id)
                        company_data.append({
                            "company_id": company_id,
                            "relevance": company.get("relevance", 0.5),
                            "context": company.get("context", ""),
                        })

                    # Store countries and link to article
                    country_ids = []
                    country_data = []
                    for country in entities.get("countries", []):
                        country_id = self.sqlite_store.store_country({
                            "name": country["name"],
                            "code": country.get("code"),
                        })
                        country_ids.append(country_id)
                        country_data.append({
                            "country_id": country_id,
                            "relevance": country.get("relevance", 0.5),
                            "context": country.get("context", ""),
                        })

                    # Store technologies and link to article
                    technology_ids = []
                    technology_data = []
                    for tech in entities.get("technologies", []):
                        technology_id = self.sqlite_store.store_technology({
                            "name": tech["name"],
                            "category": tech.get("category", "General Technology"),
                        })
                        technology_ids.append(technology_id)
                        technology_data.append({
                            "technology_id": technology_id,
                            "relevance": tech.get("relevance", 0.5),
                            "context": tech.get("context", ""),
                        })

                    # Link article with companies
                    if company_ids:
                        self.sqlite_store.link_article_companies(
                            article_id, company_ids, company_data
                        )

                    # Link article with countries
                    if country_ids:
                        self.sqlite_store.link_article_countries(
                            article_id, country_ids, country_data
                        )

                    # Link article with technologies
                    if technology_ids:
                        self.sqlite_store.link_article_technologies(
                            article_id, technology_ids, technology_data
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
