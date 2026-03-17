"""Tests for new SQLite storage, entity extraction, and report generation functionality."""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from pathlib import Path

from src.models.schemas import (
    Technology, TechnologyStatus, TechnologyMention,
    NewsArticle, Company, CountryMention, GeneratedReport, ReportSection
)
from src.storage.sqlite_store import SQLiteStore
from src.utils.entity_extractor import EntityExtractor


class TestSQLiteStore:
    """Tests for SQLite storage functionality."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_news.db")
            store = SQLiteStore(db_path=db_path)
            yield store
    
    def test_init_database(self, temp_db):
        """Test database initialization."""
        assert temp_db.db_path.exists()
    
    def test_store_article(self, temp_db):
        """Test storing an article."""
        article_data = {
            "id": "test-article-1",
            "title": "Test Article",
            "url": "https://example.com/test",
            "source": "Test Source",
            "published_date": datetime.now().isoformat(),
            "summary": "Test summary",
            "sentiment_score": 0.5,
            "relevance_score": 0.8,
            "keywords": ["AI", "machine learning"],
        }
        
        article_id = temp_db.store_article(article_data)
        assert article_id == "test-article-1"
        
        # Verify article was stored
        article = temp_db.get_article_by_id(article_id)
        assert article is not None
        assert article["title"] == "Test Article"
        assert article["sentiment_score"] == 0.5
    
    def test_store_duplicate_article(self, temp_db):
        """Test storing duplicate article (same URL) updates existing."""
        article_data = {
            "id": "test-article-2",
            "title": "Original Title",
            "url": "https://example.com/duplicate",
            "source": "Test Source",
            "summary": "Original summary",
        }
        temp_db.store_article(article_data)
        
        # Store with same URL but different title
        article_data["title"] = "Updated Title"
        article_data["id"] = "different-id"
        temp_db.store_article(article_data)
        
        # Should have only one article
        assert temp_db.get_article_count() == 1
    
    def test_store_company(self, temp_db):
        """Test storing a company."""
        company_data = {
            "name": "OpenAI",
            "country": "USA",
            "industry": "AI",
        }
        
        company_id = temp_db.store_company(company_data)
        assert company_id is not None
        
        # Verify company was stored
        company = temp_db.get_company_by_name("OpenAI")
        assert company is not None
        assert company["country"] == "USA"
    
    def test_store_country(self, temp_db):
        """Test storing a country."""
        country_data = {
            "name": "United States",
            "code": "US",
        }
        
        country_id = temp_db.store_country(country_data)
        assert country_id is not None
    
    def test_get_articles_by_date_range(self, temp_db):
        """Test retrieving articles by date range."""
        # Store articles with different dates
        now = datetime.now()
        
        for i in range(3):
            article_data = {
                "id": f"date-test-{i}",
                "title": f"Article {i}",
                "url": f"https://example.com/date-test-{i}",
                "source": "Test",
                "published_date": (now - timedelta(days=i)).isoformat(),
            }
            temp_db.store_article(article_data)
        
        # Query for last 2 days
        start = now - timedelta(days=2)
        end = now
        
        articles = temp_db.get_articles_by_date_range(start, end)
        assert len(articles) >= 2
    
    def test_get_top_companies(self, temp_db):
        """Test getting top companies by mention count."""
        # Store companies
        for name in ["OpenAI", "Google", "Microsoft"]:
            temp_db.store_company({"name": name})
        
        # Update mention counts
        temp_db.store_company({"name": "OpenAI"})  # 2 mentions
        temp_db.store_company({"name": "OpenAI"})  # 3 mentions
        
        top_companies = temp_db.get_top_companies(limit=10)
        assert len(top_companies) >= 1
        # OpenAI should be first due to more mentions
        assert top_companies[0]["name"] == "OpenAI"
    
    def test_link_article_entities(self, temp_db):
        """Test linking articles with entities."""
        # Store article, company, and country
        article_id = temp_db.store_article({
            "title": "Test",
            "url": "https://example.com/entity-test",
            "source": "Test",
        })
        company_id = temp_db.store_company({"name": "TestCompany"})
        country_id = temp_db.store_country({"name": "TestCountry"})
        
        # Link them
        temp_db.link_article_entities(article_id, [company_id], [country_id])
        
        # Verify links
        companies = temp_db.get_companies_by_article(article_id)
        assert len(companies) == 1
        assert companies[0]["name"] == "TestCompany"
    
    def test_search_articles(self, temp_db):
        """Test searching articles."""
        temp_db.store_article({
            "title": "Machine Learning Breakthrough",
            "url": "https://example.com/ml-article",
            "source": "Test",
            "summary": "New advances in AI and machine learning",
        })
        
        results = temp_db.search_articles("machine learning")
        assert len(results) >= 1
        assert "Machine Learning" in results[0]["title"]


class TestEntityExtractor:
    """Tests for entity extraction functionality."""
    
    @pytest.fixture
    def extractor(self):
        return EntityExtractor()
    
    def test_extract_known_companies(self, extractor):
        """Test extracting known tech companies."""
        text = "OpenAI and Google announced new AI partnerships with Microsoft."
        
        companies = extractor.extract_companies(text)
        
        assert len(companies) >= 2
        company_names = [c["name"] for c in companies]
        assert "OpenAI" in company_names
        assert "Google" in company_names
        assert "Microsoft" in company_names
    
    def test_extract_countries(self, extractor):
        """Test extracting country mentions."""
        text = "The technology is being developed in the USA, China, and Japan."
        
        countries = extractor.extract_countries(text)
        
        assert len(countries) >= 2
        country_names = [c["name"] for c in countries]
        # At least some countries should be found
        assert len(country_names) > 0
    
    def test_extract_all(self, extractor):
        """Test extracting all entities."""
        text = "OpenAI, based in the USA, is partnering with Samsung from South Korea."
        
        entities = extractor.extract_all(text)
        
        assert "companies" in entities
        assert "countries" in entities
        assert len(entities["companies"]) >= 1
        assert len(entities["countries"]) >= 1
    
    def test_get_company_country(self, extractor):
        """Test getting country for a known company."""
        country = extractor.get_company_country("OpenAI")
        assert country == "USA"
        
        country = extractor.get_company_country("Samsung")
        assert country == "South Korea"
    
    def test_is_known_company(self, extractor):
        """Test checking if a company is known."""
        assert extractor.is_known_company("OpenAI") is True
        assert extractor.is_known_company("UnknownStartup") is False
    
    def test_get_companies_by_country(self, extractor):
        """Test getting companies by country."""
        us_companies = extractor.get_companies_by_country("USA")
        assert "OpenAI" in us_companies
        assert "Google" in us_companies
        
        korean_companies = extractor.get_companies_by_country("South Korea")
        assert "Samsung" in korean_companies


class TestNewSchemas:
    """Tests for new data models."""
    
    def test_news_article_model(self):
        """Test NewsArticle model."""
        article = NewsArticle(
            id="test-1",
            title="Test Article",
            url="https://example.com",
            source="Test Source",
            summary="Test summary",
            sentiment_score=0.5,
            relevance_score=0.8,
            keywords=["AI", "ML"],
        )
        
        assert article.id == "test-1"
        assert article.title == "Test Article"
        assert len(article.keywords) == 2
        assert article.category == "General"
    
    def test_company_model(self):
        """Test Company model."""
        company = Company(
            id="company-1",
            name="Test Company",
            country="USA",
            industry="Technology",
        )
        
        assert company.name == "Test Company"
        assert company.mention_count == 1
    
    def test_country_mention_model(self):
        """Test CountryMention model."""
        country = CountryMention(
            id="country-1",
            name="United States",
            code="US",
        )
        
        assert country.name == "United States"
        assert country.code == "US"
    
    def test_report_section_model(self):
        """Test ReportSection model."""
        section = ReportSection(
            title="Test Section",
            content="Test content",
            priority=1,
        )
        
        assert section.title == "Test Section"
        assert section.priority == 1
    
    def test_generated_report_model(self):
        """Test GeneratedReport model."""
        report = GeneratedReport(
            id="report-1",
            period_start=datetime.now() - timedelta(days=7),
            period_end=datetime.now(),
            title="Test Report",
            executive_summary="Test summary",
            sections=[
                ReportSection(title="Section 1", content="Content 1", priority=1)
            ],
        )
        
        assert report.id == "report-1"
        assert len(report.sections) == 1
        assert report.file_path is None


class TestReportGeneratorAgent:
    """Tests for ReportGeneratorAgent functionality."""
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            report_dir = os.path.join(tmpdir, "reports")
            os.makedirs(report_dir)
            yield {
                "db_path": db_path,
                "report_dir": report_dir,
            }
    
    @pytest.fixture
    def store(self, temp_dirs):
        """Create SQLite store for testing."""
        return SQLiteStore(db_path=temp_dirs["db_path"])
    
    def test_report_generator_init(self, temp_dirs):
        """Test ReportGeneratorAgent initialization."""
        from src.agents.report_generator import ReportGeneratorAgent
        
        agent = ReportGeneratorAgent(
            sqlite_store=SQLiteStore(db_path=temp_dirs["db_path"]),
            report_dir=temp_dirs["report_dir"],
            use_llm=False,  # Disable LLM for testing
        )
        
        assert agent.name == "ReportGeneratorAgent"
        assert agent.use_llm is False
    
    @pytest.mark.asyncio
    async def test_generate_report_without_llm(self, temp_dirs, store):
        """Test report generation without LLM."""
        from src.agents.report_generator import ReportGeneratorAgent
        
        # Store some test data
        store.store_article({
            "title": "AI Breakthrough",
            "url": "https://example.com/ai",
            "source": "Test",
            "summary": "New AI technology",
            "relevance_score": 0.8,
            "sentiment_score": 0.5,
        })
        
        agent = ReportGeneratorAgent(
            sqlite_store=store,
            report_dir=temp_dirs["report_dir"],
            use_llm=False,
        )
        
        report = await agent.process({
            "period_start": datetime.now() - timedelta(days=7),
            "period_end": datetime.now(),
            "technologies": [],
            "developments": {},
        })
        
        assert report is not None
        assert report.title is not None
        assert report.executive_summary is not None
        assert report.file_path is not None
        assert Path(report.file_path).exists()


class TestNewsCollectorWithSQLite:
    """Tests for NewsCollectorAgent with SQLite storage."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            store = SQLiteStore(db_path=db_path)
            yield store
    
    def test_news_collector_with_sqlite(self, temp_db):
        """Test NewsCollectorAgent initialization with SQLite."""
        agent = NewsCollectorAgent(sqlite_store=temp_db)
        
        assert agent.sqlite_store is not None
        assert agent.extract_entities is True
        assert agent.entity_extractor is not None
    
    def test_news_collector_entity_extraction_disabled(self, temp_db):
        """Test NewsCollectorAgent with entity extraction disabled."""
        agent = NewsCollectorAgent(
            sqlite_store=temp_db,
            extract_entities=False,
        )
        
        assert agent.extract_entities is False
        assert agent.entity_extractor is None


class TestTechNewsMultiAgentSystemWithNewFeatures:
    """Tests for the updated multi-agent system."""
    
    @pytest.fixture
    def temp_system(self):
        """Create a temporary system for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            memory_dir = os.path.join(tmpdir, "memory")
            sqlite_path = os.path.join(tmpdir, "news.db")
            report_dir = os.path.join(tmpdir, "reports")
            
            system = TechNewsMultiAgentSystem(
                memory_dir=memory_dir,
                sqlite_path=sqlite_path,
                report_dir=report_dir,
                use_llm=False,
            )
            yield system
    
    def test_system_has_sqlite_store(self, temp_system):
        """Test that system has SQLite store initialized."""
        assert temp_system.sqlite_store is not None
        assert temp_system.report_generator is not None
    
    def test_system_has_report_generator(self, temp_system):
        """Test that system has report generator initialized."""
        assert temp_system.report_generator is not None
        assert temp_system.report_generator.use_llm is False
    
    @pytest.mark.asyncio
    async def test_system_initialization(self, temp_system):
        """Test system initialization with new components."""
        assert temp_system.news_collector.sqlite_store is not None
        assert temp_system.report_generator.sqlite_store is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
