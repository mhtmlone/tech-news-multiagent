import chromadb
from chromadb.config import Settings
from typing import Optional
import uuid
from datetime import datetime
import json
from pathlib import Path

from ..models.schemas import Technology, MemoryEntry


class VectorMemory:
    def __init__(self, persist_directory: str = "./memory_db"):
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(anonymized_telemetry=False)
        )
        
        self.tech_collection = self.client.get_or_create_collection(
            name="technologies",
            metadata={"description": "Technology information and developments"}
        )
        
        self.development_collection = self.client.get_or_create_collection(
            name="developments",
            metadata={"description": "Technology developments and updates"}
        )
        
        self.news_collection = self.client.get_or_create_collection(
            name="news_mentions",
            metadata={"description": "News mentions and articles"}
        )

    def store_technology(self, technology: Technology) -> str:
        tech_id = technology.id or str(uuid.uuid4())
        
        tech_data = {
            "id": tech_id,
            "name": technology.name,
            "description": technology.description,
            "category": technology.category,
            "status": technology.status.value,
            "first_seen": technology.first_seen.isoformat(),
            "last_updated": technology.last_updated.isoformat(),
            "related_technologies": json.dumps(technology.related_technologies),
            "key_developments": json.dumps(technology.key_developments),
            "confidence_score": technology.confidence_score,
            "trend_direction": technology.trend_direction,
            "hype_level": technology.hype_level,
        }
        
        content = f"{technology.name}: {technology.description}. " \
                  f"Category: {technology.category}. " \
                  f"Status: {technology.status.value}. " \
                  f"Developments: {', '.join(technology.key_developments)}"
        
        self.tech_collection.upsert(
            ids=[tech_id],
            documents=[content],
            metadatas=[tech_data]
        )
        
        return tech_id

    def search_technologies(self, query: str, n_results: int = 10) -> list[dict]:
        results = self.tech_collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        technologies = []
        if results["ids"] and results["ids"][0]:
            for i, tech_id in enumerate(results["ids"][0]):
                tech_data = {
                    "id": tech_id,
                    "name": results["metadatas"][0][i].get("name", ""),
                    "description": results["metadatas"][0][i].get("description", ""),
                    "category": results["metadatas"][0][i].get("category", ""),
                    "status": results["metadatas"][0][i].get("status", "emerging"),
                    "confidence_score": results["metadatas"][0][i].get("confidence_score", 0.5),
                    "trend_direction": results["metadatas"][0][i].get("trend_direction", "stable"),
                }
                technologies.append(tech_data)
        
        return technologies

    def add_development(self, tech_id: str, development: str, timestamp: datetime = None) -> str:
        dev_id = str(uuid.uuid4())
        
        dev_data = {
            "id": dev_id,
            "tech_id": tech_id,
            "development": development,
            "timestamp": (timestamp or datetime.now()).isoformat(),
        }
        
        self.development_collection.add(
            ids=[dev_id],
            documents=[development],
            metadatas=[dev_data]
        )
        
        return dev_id

    def get_technology_developments(self, tech_id: str) -> list[dict]:
        results = self.development_collection.get(
            where={"tech_id": tech_id}
        )
        
        developments = []
        if results["ids"]:
            for i, dev_id in enumerate(results["ids"]):
                dev_data = {
                    "id": dev_id,
                    "development": results["documents"][i],
                    "timestamp": results["metadatas"][i].get("timestamp", ""),
                }
                developments.append(dev_data)
        
        # Sort by timestamp
        developments.sort(key=lambda x: x["timestamp"])
        
        return developments

    def store_news_mention(self, tech_id: str, mention_data: dict) -> str:
        mention_id = str(uuid.uuid4())
        
        content = f"{mention_data.get('title', '')}: {mention_data.get('summary', '')}"
        
        metadata = {
            "id": mention_id,
            "tech_id": tech_id,
            "source": mention_data.get("source", ""),
            "url": mention_data.get("url", ""),
            "title": mention_data.get("title", ""),
            "published_date": mention_data.get("published_date", ""),
            "sentiment_score": mention_data.get("sentiment_score", 0.0),
            "relevance_score": mention_data.get("relevance_score", 0.0),
        }
        
        self.news_collection.add(
            ids=[mention_id],
            documents=[content],
            metadatas=[metadata]
        )
        
        return mention_id

    def get_technology_mentions(self, tech_id: str, limit: int = 50) -> list[dict]:
        all_results = self.news_collection.get(
            where={"tech_id": tech_id},
            limit=limit
        )
        
        mentions = []
        if all_results["ids"]:
            for i, mention_id in enumerate(all_results["ids"]):
                mention_data = {
                    "id": mention_id,
                    "source": all_results["metadatas"][i].get("source", ""),
                    "url": all_results["metadatas"][i].get("url", ""),
                    "title": all_results["metadatas"][i].get("title", ""),
                    "published_date": all_results["metadatas"][i].get("published_date", ""),
                    "summary": all_results["documents"][i] if all_results["documents"] else "",
                    "sentiment_score": all_results["metadatas"][i].get("sentiment_score", 0.0),
                    "relevance_score": all_results["metadatas"][i].get("relevance_score", 0.0),
                }
                mentions.append(mention_data)
        
        # Sort by published_date and apply limit
        mentions.sort(key=lambda x: x["published_date"])
        return mentions[:limit]

    def get_all_technologies(self) -> list[dict]:
        results = self.tech_collection.get()
        
        technologies = []
        if results["ids"]:
            for i, tech_id in enumerate(results["ids"]):
                tech_data = {
                    "id": tech_id,
                    "name": results["metadatas"][i].get("name", ""),
                    "description": results["metadatas"][i].get("description", ""),
                    "category": results["metadatas"][i].get("category", ""),
                    "status": results["metadatas"][i].get("status", "emerging"),
                    "first_seen": results["metadatas"][i].get("first_seen", ""),
                    "last_updated": results["metadatas"][i].get("last_updated", ""),
                    "confidence_score": results["metadatas"][i].get("confidence_score", 0.5),
                    "trend_direction": results["metadatas"][i].get("trend_direction", "stable"),
                }
                technologies.append(tech_data)
        
        return technologies

    def delete_technology(self, tech_id: str):
        self.tech_collection.delete(ids=[tech_id])
        
        dev_results = self.development_collection.get(
            where={"tech_id": tech_id}
        )
        if dev_results["ids"]:
            self.development_collection.delete(ids=dev_results["ids"])
        
        mention_results = self.news_collection.get(
            where={"tech_id": tech_id}
        )
        if mention_results["ids"]:
            self.news_collection.delete(ids=mention_results["ids"])

    def find_similar_technologies(self, tech_name: str, threshold: float = 0.7) -> list[dict]:
        results = self.tech_collection.query(
            query_texts=[tech_name],
            n_results=10
        )
        
        similar = []
        if results["ids"] and results["distances"]:
            for i, tech_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i]
                similarity = 1 - distance
                
                if similarity >= threshold:
                    tech_data = {
                        "id": tech_id,
                        "name": results["metadatas"][0][i].get("name", ""),
                        "similarity": similarity,
                    }
                    similar.append(tech_data)
        
        return similar
