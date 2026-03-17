import re
import uuid
from datetime import datetime
from typing import Optional, Any

from ..models.schemas import Technology, TechnologyStatus, TechnologyMention
from .base import BaseAgent


TECH_CATEGORIES = {
    "AI/ML": [
        "AI",
        "artificial intelligence",
        "machine learning",
        "deep learning",
        "neural network",
        "LLM",
        "large language model",
        "transformer",
        "diffusion model",
        "generative AI",
        "computer vision",
        "NLP",
        "RAG",
        "agent",
        "multi-agent",
    ],
    "Quantum Computing": [
        "quantum computing",
        "quantum",
        "qubit",
        "quantum supremacy",
    ],
    "Blockchain/Web3": [
        "blockchain",
        "cryptocurrency",
        "web3",
        "crypto",
        "NFT",
        "DeFi",
        "smart contract",
    ],
    "Robotics": [
        "robotics",
        "robot",
        "autonomous",
        "humanoid",
        "automation",
    ],
    "Cloud/Infrastructure": [
        "cloud computing",
        "edge computing",
        "serverless",
        "kubernetes",
        "microservices",
        "devops",
        "API",
    ],
    "Cybersecurity": [
        "cybersecurity",
        "zero trust",
        "encryption",
        "authentication",
        "security",
    ],
    "Telecommunications": [
        "5G",
        "6G",
        "telecommunications",
        "network",
    ],
    "IoT": [
        "IoT",
        "Internet of Things",
        "sensor",
        "connected",
    ],
    "AR/VR/MR": [
        "augmented reality",
        "virtual reality",
        "AR",
        "VR",
        "mixed reality",
        "metaverse",
    ],
    "Biotech": [
        "biotech",
        "gene editing",
        "CRISPR",
        "synthetic biology",
        "biomedical",
    ],
    "Energy/Cleantech": [
        "battery technology",
        "renewable energy",
        "solar",
        "fusion",
        "hydrogen fuel",
        "carbon capture",
        "climate tech",
        "electric vehicle",
        "EV",
    ],
    "Semiconductors": [
        "semiconductor",
        "chip",
        "processor",
        "GPU",
        "TPU",
        "neuromorphic",
    ],
    "Hardware/Interfaces": [
        "brain-computer interface",
        "wearable",
        "hardware",
    ],
    "Space Tech": [
        "space technology",
        "satellite",
        "rocket",
        "spaceX",
    ],
    "Manufacturing": [
        "3D printing",
        "additive manufacturing",
        "nanotechnology",
    ],
    "Materials": [
        "material science",
        "graphene",
        "superconductor",
    ],
}


class TechnologyAnalyzerAgent(BaseAgent):
    def __init__(self, **kwargs):
        super().__init__(name="TechnologyAnalyzerAgent", **kwargs)
        self.categories = TECH_CATEGORIES
        self.patterns = self._build_patterns()

    def _build_patterns(self) -> dict[str, re.Pattern]:
        patterns = {}
        for category, keywords in self.categories.items():
            pattern_str = r"\b(" + "|".join(re.escape(kw) for kw in keywords) + r")\b"
            patterns[category] = re.compile(pattern_str, re.IGNORECASE)
        return patterns

    def categorize_technology(self, text: str) -> str:
        for category, pattern in self.patterns.items():
            if pattern.search(text):
                return category
        return "General Technology"

    def extract_technology_names(self, text: str) -> list[str]:
        tech_names = []

        patterns = [
            r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:AI|ML|OS|API|SDK|GPU|TPU|CPU|NLP|LLM|VR|AR|MR|XR|IoT|DeFi|NFT|Web3))\b",
            r"\b((?:[A-Z][a-z]+)+Tech)\b",
            r"\b((?:[A-Z][a-z]+)+OS)\b",
            r"\b((?:[A-Z][a-z]+)+AI)\b",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            tech_names.extend(matches)

        return list(set(tech_names))

    def identify_new_technologies(
        self, mentions: list[TechnologyMention], existing_techs: list[dict]
    ) -> list[Technology]:
        existing_names = {tech["name"].lower() for tech in existing_techs}

        tech_mentions: dict[str, list[TechnologyMention]] = {}

        for mention in mentions:
            text = f"{mention.title} {mention.summary}"

            for category, pattern in self.patterns.items():
                matches = pattern.findall(text)
                if matches:
                    for match in matches:
                        tech_key = match.lower()
                        if tech_key not in existing_names:
                            if tech_key not in tech_mentions:
                                tech_mentions[tech_key] = []
                            tech_mentions[tech_key].append(mention)

        new_technologies = []
        for tech_key, mentions_list in tech_mentions.items():
            if len(mentions_list) < 2:
                continue

            mentions_list.sort(key=lambda x: x.relevance_score, reverse=True)
            top_mention = mentions_list[0]

            avg_sentiment = sum(m.sentiment_score for m in mentions_list) / len(mentions_list)
            avg_relevance = sum(m.relevance_score for m in mentions_list) / len(mentions_list)

            category = self.categorize_technology(f"{top_mention.title} {top_mention.summary}")

            tech = Technology(
                id=str(uuid.uuid4()),
                name=tech_key.title(),
                description=self._generate_description(mentions_list),
                category=category,
                status=TechnologyStatus.EMERGING,
                first_seen=min(m.published_date for m in mentions_list),
                last_updated=datetime.now(),
                mentions=mentions_list[:10],
                related_technologies=[],
                key_developments=[top_mention.title],
                confidence_score=avg_relevance,
                trend_direction="emerging",
                hype_level=min(1.0, len(mentions_list) / 10.0),
            )

            new_technologies.append(tech)

        return new_technologies

    def _generate_description(self, mentions: list[TechnologyMention]) -> str:
        if not mentions:
            return "No description available"

        summary = mentions[0].summary
        if len(summary) > 300:
            summary = summary[:300] + "..."

        return summary

    def analyze_existing_technologies(
        self,
        mentions: list[TechnologyMention],
        existing_techs: list[dict],
    ) -> list[Technology]:
        updated_technologies = []

        for tech_data in existing_techs:
            tech_mentions = []
            for mention in mentions:
                text = f"{mention.title} {mention.summary}".lower()
                if tech_data["name"].lower() in text:
                    tech_mentions.append(mention)

            if not tech_mentions:
                continue

            tech_data["last_updated"] = datetime.now().isoformat()

            if "key_developments" not in tech_data:
                tech_data["key_developments"] = []

            new_developments = [
                m.title for m in tech_mentions if m.title not in tech_data.get("key_developments", [])
            ]
            tech_data["key_developments"].extend(new_developments[:5])

            if tech_mentions:
                avg_sentiment = sum(m.sentiment_score for m in tech_mentions) / len(tech_mentions)
                tech_data["recent_sentiment"] = avg_sentiment

                mention_count = len(tech_mentions)
                if mention_count > 10:
                    tech_data["trend_direction"] = "rising"
                    if tech_data.get("status") == "emerging":
                        tech_data["status"] = "growing"
                elif mention_count > 5:
                    tech_data["trend_direction"] = "stable"
                else:
                    tech_data["trend_direction"] = "declining"

                tech_data["hype_level"] = min(1.0, mention_count / 20.0)

            updated_tech = Technology(**tech_data)
            updated_technologies.append(updated_tech)

        return updated_technologies

    def identify_promising_technologies(
        self, technologies: list[Technology], threshold: float = 0.7
    ) -> list[Technology]:
        promising = []

        for tech in technologies:
            score = self._calculate_promising_score(tech)
            if score >= threshold:
                promising.append(tech)

        promising.sort(key=lambda x: self._calculate_promising_score(x), reverse=True)
        return promising

    def _calculate_promising_score(self, tech: Technology) -> float:
        score = 0.0

        score += tech.confidence_score * 0.2

        score += tech.hype_level * 0.15

        if tech.status == TechnologyStatus.EMERGING:
            score += 0.2
        elif tech.status == TechnologyStatus.GROWING:
            score += 0.15

        if tech.trend_direction == "rising":
            score += 0.15
        elif tech.trend_direction == "stable":
            score += 0.05

        if tech.mentions:
            recent_mentions = [
                m for m in tech.mentions if (datetime.now() - m.published_date).days <= 7
            ]
            mention_ratio = len(recent_mentions) / max(len(tech.mentions), 1)
            score += mention_ratio * 0.15

        if tech.mentions:
            avg_sentiment = sum(m.sentiment_score for m in tech.mentions) / len(tech.mentions)
            if avg_sentiment > 0:
                score += avg_sentiment * 0.15

        return min(1.0, score)

    async def process(
        self, input_data: dict[str, Any]
    ) -> dict[str, list[Technology] | dict]:
        mentions_data = input_data.get("mentions", [])
        existing_techs = input_data.get("existing_technologies", [])

        mentions = []
        for m in mentions_data:
            if isinstance(m, dict):
                mentions.append(TechnologyMention(**m))
            elif isinstance(m, TechnologyMention):
                mentions.append(m)

        new_technologies = self.identify_new_technologies(mentions, existing_techs)

        updated_technologies = self.analyze_existing_technologies(mentions, existing_techs)

        all_technologies = new_technologies + updated_technologies
        promising_technologies = self.identify_promising_technologies(all_technologies)

        self.send_message(
            recipient="MemoryManagerAgent",
            message_type="technology_analysis",
            content={
                "new_technologies": [t.model_dump(mode="json") for t in new_technologies],
                "updated_technologies": [t.model_dump(mode="json") for t in updated_technologies],
                "promising_technologies": [t.model_dump(mode="json") for t in promising_technologies],
                "analysis_timestamp": datetime.now().isoformat(),
            },
        )

        return {
            "new_technologies": new_technologies,
            "updated_technologies": updated_technologies,
            "promising_technologies": promising_technologies,
            "total_mentions_analyzed": len(mentions),
            "analysis_timestamp": datetime.now(),
        }
