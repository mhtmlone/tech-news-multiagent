import pytest
import asyncio
from datetime import datetime, timedelta

from src.models.schemas import Technology, TechnologyStatus, TechnologyMention
from src.memory.vector_store import VectorMemory
from src.agents.news_collector import NewsCollectorAgent
from src.agents.technology_analyzer import TechnologyAnalyzerAgent
from src.agents.memory_manager import MemoryManagerAgent
from src.agents.development_tracker import DevelopmentTrackerAgent
from src.main import TechNewsMultiAgentSystem


class TestTechnologyModel:
    def test_create_technology(self):
        tech = Technology(
            id="test-1",
            name="Test AI",
            description="A test technology",
            category="AI/ML",
            status=TechnologyStatus.EMERGING,
            first_seen=datetime.now(),
            last_updated=datetime.now(),
        )
        assert tech.name == "Test AI"
        assert tech.status == TechnologyStatus.EMERGING
        assert tech.confidence_score == 0.5

    def test_technology_with_mentions(self):
        mention = TechnologyMention(
            source="TechCrunch",
            url="https://example.com",
            title="Test Article",
            published_date=datetime.now(),
            summary="Test summary",
            sentiment_score=0.5,
            relevance_score=0.8,
        )

        tech = Technology(
            id="test-2",
            name="Test AI",
            description="A test technology",
            category="AI/ML",
            first_seen=datetime.now(),
            last_updated=datetime.now(),
            mentions=[mention],
        )

        assert len(tech.mentions) == 1
        assert tech.mentions[0].sentiment_score == 0.5


class TestVectorMemory:
    @pytest.fixture
    def memory(self):
        mem = VectorMemory(persist_directory="./test_memory_db")
        yield mem

    def test_store_technology(self, memory):
        tech = Technology(
            id="test-tech-1",
            name="Quantum Computing",
            description="Quantum computing technology",
            category="Quantum Computing",
            first_seen=datetime.now(),
            last_updated=datetime.now(),
        )

        tech_id = memory.store_technology(tech)
        assert tech_id == "test-tech-1"

    def test_search_technologies(self, memory):
        results = memory.search_technologies("quantum", n_results=5)
        assert isinstance(results, list)

    def test_add_development(self, memory):
        dev_id = memory.add_development(
            "test-tech-1", "New breakthrough in quantum computing"
        )
        assert dev_id is not None

    def test_get_developments(self, memory):
        developments = memory.get_technology_developments("test-tech-1")
        assert isinstance(developments, list)


class TestNewsCollectorAgent:
    @pytest.fixture
    def agent(self):
        return NewsCollectorAgent()

    @pytest.mark.asyncio
    async def test_is_technology_related(self, agent):
        is_tech, keywords = agent.is_technology_related(
            "New AI breakthrough in machine learning"
        )
        assert is_tech is True
        assert "AI" in keywords or "machine learning" in keywords

    @pytest.mark.asyncio
    async def test_is_not_technology_related(self, agent):
        is_tech, keywords = agent.is_technology_related(
            "The weather is nice today"
        )
        assert is_tech is False
        assert len(keywords) == 0

    @pytest.mark.asyncio
    async def test_calculate_relevance(self, agent):
        relevance = agent.calculate_relevance(
            "AI and machine learning are transforming technology",
            ["AI", "machine learning"]
        )
        assert 0.0 <= relevance <= 1.0

    @pytest.mark.asyncio
    async def test_analyze_sentiment_positive(self, agent):
        sentiment = await agent.analyze_sentiment(
            "Breakthrough: AI shows promising and impressive results"
        )
        assert sentiment > 0

    @pytest.mark.asyncio
    async def test_analyze_sentiment_negative(self, agent):
        sentiment = await agent.analyze_sentiment(
            "Failed: AI faces problems and criticism"
        )
        assert sentiment < 0


class TestTechnologyAnalyzerAgent:
    @pytest.fixture
    def agent(self):
        return TechnologyAnalyzerAgent()

    def test_categorize_technology(self, agent):
        category = agent.categorize_technology(
            "New machine learning model achieves breakthrough"
        )
        assert category == "AI/ML"

    def test_extract_technology_names(self, agent):
        text = "DeepMind's new AI system uses advanced neural networks"
        names = agent.extract_technology_names(text)
        assert isinstance(names, list)

    def test_calculate_promising_score(self, agent):
        tech = Technology(
            id="test-1",
            name="Test AI",
            description="Test",
            category="AI/ML",
            first_seen=datetime.now(),
            last_updated=datetime.now(),
            confidence_score=0.8,
            hype_level=0.6,
            status=TechnologyStatus.EMERGING,
            trend_direction="rising",
        )
        score = agent._calculate_promising_score(tech)
        assert 0.0 <= score <= 1.0


class TestMemoryManagerAgent:
    @pytest.fixture
    def agent(self):
        return MemoryManagerAgent()

    @pytest.mark.asyncio
    async def test_store_new_technologies(self, agent):
        tech = Technology(
            id="test-store-1",
            name="Test Technology",
            description="A test",
            category="AI/ML",
            first_seen=datetime.now(),
            last_updated=datetime.now(),
        )
        ids = await agent.store_new_technologies([tech])
        assert len(ids) == 1

    @pytest.mark.asyncio
    async def test_retrieve_technology_history(self, agent):
        result = await agent.retrieve_technology_history("NonExistent")
        assert result["found"] is False


class TestDevelopmentTrackerAgent:
    @pytest.fixture
    def agent(self):
        return DevelopmentTrackerAgent()

    @pytest.mark.asyncio
    async def test_analyze_trajectory(self, agent):
        result = await agent.analyze_technology_trajectory(
            "non-existent-id", {"name": "Test"}
        )
        assert "tech_id" in result
        assert "trajectory" in result

    @pytest.mark.asyncio
    async def test_detect_significant_developments(self, agent):
        developments = await agent.detect_significant_developments(
            "non-existent-id", {"name": "Test"}
        )
        assert isinstance(developments, list)


class TestTechNewsMultiAgentSystem:
    @pytest.fixture
    def system(self):
        return TechNewsMultiAgentSystem(memory_dir="./test_system_memory")

    @pytest.mark.asyncio
    async def test_initialization(self, system):
        assert system.news_collector is not None
        assert system.tech_analyzer is not None
        assert system.memory_manager is not None
        assert system.dev_tracker is not None

    @pytest.mark.asyncio
    async def test_search_technologies(self, system):
        results = await system.search_technologies("AI", limit=5)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_generate_summary_report(self, system):
        report = await system.generate_summary_report()
        assert isinstance(report, str)
        assert "TECHNOLOGY TRACKING SUMMARY" in report


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
