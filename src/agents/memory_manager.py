import uuid
from datetime import datetime
from typing import Any, Optional

from ..models.schemas import Technology, TechnologyStatus
from ..memory.vector_store import VectorMemory
from ..storage.sqlite_store import SQLiteStore
from .base import BaseAgent


class MemoryManagerAgent(BaseAgent):
    def __init__(self, **kwargs):
        super().__init__(name="MemoryManagerAgent", **kwargs)
        if not self.memory:
            self.memory = VectorMemory()
        self.db = SQLiteStore()

    def search_related_articles(self, query: str, limit: int = 20) -> list[dict]:
        """Search the database for articles related to a technology or topic.
        
        Args:
            query: Search query (technology name or topic)
            limit: Maximum number of articles to return
            
        Returns:
            List of matching articles with content
        """
        try:
            articles = self.db.search_articles(query, limit=limit)
            return articles
        except Exception as e:
            self.logger.error(f"Error searching articles for '{query}': {e}")
            return []

    def get_context_articles(self, tech_name: str, limit: int = 10) -> list[dict]:
        """Get context articles from the database for a technology.
        
        Args:
            tech_name: Name of the technology
            limit: Maximum number of articles to return
            
        Returns:
            List of articles with full content for context
        """
        try:
            articles = self.db.get_articles_with_content(limit=limit)
            # Filter to only include articles mentioning the technology
            relevant = [
                a for a in articles
                if tech_name.lower() in a.get("title", "").lower()
                or tech_name.lower() in a.get("content", "").lower()
            ]
            return relevant[:limit]
        except Exception as e:
            self.logger.error(f"Error getting context articles for '{tech_name}': {e}")
            return []

    def _technology_to_memory_entry(self, tech: Technology) -> dict:
        return {
            "id": tech.id,
            "name": tech.name,
            "description": tech.description,
            "category": tech.category,
            "status": tech.status.value if isinstance(tech.status, TechnologyStatus) else tech.status,
            "first_seen": tech.first_seen.isoformat() if tech.first_seen else datetime.now().isoformat(),
            "last_updated": tech.last_updated.isoformat() if tech.last_updated else datetime.now().isoformat(),
            "related_technologies": tech.related_technologies,
            "key_developments": tech.key_developments,
            "confidence_score": tech.confidence_score,
            "trend_direction": tech.trend_direction,
            "hype_level": tech.hype_level,
        }

    async def store_new_technologies(self, technologies: list[Technology]) -> list[str]:
        stored_ids = []
        for tech in technologies:
            try:
                tech_id = self.memory.store_technology(tech)
                stored_ids.append(tech_id)

                if tech.key_developments:
                    for dev in tech.key_developments:
                        self.memory.add_development(tech_id, dev, tech.last_updated)

                if tech.mentions:
                    for mention in tech.mentions[:5]:
                        mention_data = {
                            "source": mention.source,
                            "url": mention.url,
                            "title": mention.title,
                            "published_date": mention.published_date.isoformat(),
                            "summary": mention.summary,
                            "sentiment_score": mention.sentiment_score,
                            "relevance_score": mention.relevance_score,
                        }
                        self.memory.store_news_mention(tech_id, mention_data)

            except Exception as e:
                print(f"Error storing technology {tech.name}: {e}")
                continue

        return stored_ids

    async def update_existing_technologies(self, technologies: list[Technology]) -> list[str]:
        updated_ids = []
        for tech in technologies:
            try:
                existing = self.memory.search_technologies(tech.name, n_results=1)
                if existing and existing[0]["name"].lower() == tech.name.lower():
                    tech_id = existing[0]["id"]
                else:
                    tech_id = tech.id or str(uuid.uuid4())

                tech.id = tech_id
                self.memory.store_technology(tech)
                updated_ids.append(tech_id)

                if tech.key_developments:
                    for dev in tech.key_developments:
                        self.memory.add_development(tech_id, dev)

            except Exception as e:
                print(f"Error updating technology {tech.name}: {e}")
                continue

        return updated_ids

    async def retrieve_technology_history(self, tech_name: str) -> dict[str, Any]:
        results = self.memory.search_technologies(tech_name, n_results=1)
        if not results:
            return {"found": False, "error": "Technology not found"}

        tech_data = results[0]
        tech_id = tech_data["id"]

        developments = self.memory.get_technology_developments(tech_id)
        mentions = self.memory.get_technology_mentions(tech_id)
        similar = self.memory.find_similar_technologies(tech_name)

        return {
            "found": True,
            "technology": tech_data,
            "developments": developments,
            "mentions": mentions,
            "similar_technologies": similar,
        }

    async def get_all_tracked_technologies(self) -> list[dict]:
        return self.memory.get_all_technologies()

    async def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        new_techs_data = input_data.get("new_technologies", [])
        updated_techs_data = input_data.get("updated_technologies", [])

        new_technologies = []
        for tech_data in new_techs_data:
            if isinstance(tech_data, dict):
                tech = Technology(**tech_data)
                new_technologies.append(tech)
            elif isinstance(tech_data, Technology):
                new_technologies.append(tech_data)

        updated_technologies = []
        for tech_data in updated_techs_data:
            if isinstance(tech_data, dict):
                tech = Technology(**tech_data)
                updated_technologies.append(tech)
            elif isinstance(tech_data, Technology):
                updated_technologies.append(tech_data)

        new_stored_ids = await self.store_new_technologies(new_technologies)
        updated_stored_ids = await self.update_existing_technologies(updated_technologies)

        # Optionally search database for additional context
        search_db = input_data.get("search_database", False)
        db_context = {}
        if search_db:
            try:
                # Get context for new technologies
                for tech in new_technologies:
                    articles = self.get_context_articles(tech.name, limit=5)
                    if articles:
                        db_context[tech.name] = {
                            "article_count": len(articles),
                            "sources": list(set(a.get("source", "") for a in articles)),
                        }
                self.logger.info(f"Found database context for {len(db_context)} technologies")
            except Exception as e:
                self.logger.error(f"Error searching database for context: {e}")

        result = {
            "new_technologies_stored": len(new_stored_ids),
            "updated_technologies_stored": len(updated_stored_ids),
            "new_ids": new_stored_ids,
            "updated_ids": updated_stored_ids,
            "database_context": db_context if search_db else {},
            "timestamp": datetime.now().isoformat(),
        }

        self.send_message(
            recipient="DevelopmentTrackerAgent",
            message_type="memory_update",
            content=result,
        )

        return result

    async def search_technologies(self, query: str, limit: int = 10) -> list[dict]:
        return self.memory.search_technologies(query, n_results=limit)

    async def find_similar(self, tech_name: str, threshold: float = 0.7) -> list[dict]:
        return self.memory.find_similar_technologies(tech_name, threshold=threshold)

    async def get_developments(self, tech_id: str) -> list[dict]:
        return self.memory.get_technology_developments(tech_id)

    async def get_mentions(self, tech_id: str, limit: int = 50) -> list[dict]:
        return self.memory.get_technology_mentions(tech_id, limit=limit)
