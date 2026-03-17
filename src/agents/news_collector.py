import asyncio
import aiohttp
import feedparser
from datetime import datetime, timedelta
from typing import Optional
from bs4 import BeautifulSoup
import re
import uuid

from ..models.schemas import TechnologyMention
from ..storage.sqlite_store import SQLiteStore
from ..utils.entity_extractor import EntityExtractor
from .base import BaseAgent


TECH_NEWS_SOURCES = [
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://arstechnica.com/feed/",
    "https://www.wired.com/feed/rss",
    "https://news.ycombinator.com/rss",
    "https://www.zdnet.com/news/rss/",
    "https://thenextweb.com/feed/",
]

TECH_KEYWORDS = [
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
        **kwargs
    ):
        super().__init__(name="NewsCollectorAgent", **kwargs)
        self.sources = TECH_NEWS_SOURCES
        self.keywords = TECH_KEYWORDS
        self.session: Optional[aiohttp.ClientSession] = None
        self.sqlite_store = sqlite_store or SQLiteStore()
        self.extract_entities = extract_entities
        self.entity_extractor = EntityExtractor() if extract_entities else None

    async def _ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={"User-Agent": "TechNewsAnalyzer/1.0"},
                timeout=aiohttp.ClientTimeout(total=30),
            )

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def fetch_article_content(self, url: str) -> str:
        """Fetch and extract full article content from URL."""
        await self._ensure_session()
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Remove script, style, and other non-content elements
                    for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'advertisement']):
                        element.decompose()
                    
                    # Try to find the main article content
                    article_body = (
                        soup.find('article') or
                        soup.find('main') or
                        soup.find('div', class_=re.compile(r'article|content|post|entry', re.I)) or
                        soup.find('div', {'id': re.compile(r'article|content|post|entry', re.I)})
                    )
                    
                    if article_body:
                        # Extract text and clean up whitespace
                        text = article_body.get_text(separator=' ', strip=True)
                        # Remove excessive whitespace
                        text = re.sub(r'\s+', ' ', text)
                        return text[:10000]  # Limit to 10000 chars to avoid huge content
                    else:
                        # Fallback: get all paragraph text
                        paragraphs = soup.find_all('p')
                        text = ' '.join(p.get_text(strip=True) for p in paragraphs)
                        return text[:10000]
        except Exception as e:
            print(f"Error fetching article content from {url}: {e}")
        return ""

    async def fetch_feed(self, url: str) -> list[dict]:
        await self._ensure_session()
        entries = []

        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    feed_content = await response.text()
                    feed = feedparser.parse(feed_content)

                    for entry in feed.entries[:20]:
                        published = None
                        if hasattr(entry, "published_parsed") and entry.published_parsed:
                            try:
                                published = datetime(*entry.published_parsed[:6])
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
        except Exception as e:
            print(f"Error fetching feed {url}: {e}")

        return entries

    async def fetch_all_feeds(self) -> list[dict]:
        await self._ensure_session()
        all_entries = []

        tasks = [self.fetch_feed(url) for url in self.sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                all_entries.extend(result)

        return all_entries

    def is_technology_related(self, text: str) -> tuple[bool, list[str]]:
        text_lower = text.lower()
        matched_keywords = []

        for keyword in self.keywords:
            if keyword.lower() in text_lower:
                matched_keywords.append(keyword)

        return len(matched_keywords) > 0, matched_keywords

    def calculate_relevance(self, text: str, matched_keywords: list[str]) -> float:
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
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)

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

        entries = await self.fetch_all_feeds()

        technology_mentions = []
        stored_article_ids = []
        
        for entry in entries:
            if entry["published"] and entry["published"] < cutoff_date:
                continue

            is_tech, matched_keywords = self.is_technology_related(
                f"{entry['title']} {entry['summary']}"
            )

            if not is_tech:
                continue

            relevance = self.calculate_relevance(
                f"{entry['title']} {entry['summary']}", matched_keywords
            )

            if relevance < 0.1:
                continue

            sentiment = await self.analyze_sentiment(f"{entry['title']} {entry['summary']}")

            # Fetch full article content
            article_content = await self.fetch_article_content(entry["link"])
            
            # Use full content for summary if available, otherwise fall back to RSS summary
            full_text = article_content if article_content else entry["summary"]
            summary_for_mention = full_text[:500] if full_text else ""

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
                "summary": entry["summary"][:1000] if entry["summary"] else "",
                "content": article_content,  # Store full article content
                "sentiment_score": sentiment,
                "relevance_score": relevance,
                "keywords": matched_keywords,
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

        technology_mentions.sort(key=lambda x: (x.relevance_score, x.published_date), reverse=True)

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
