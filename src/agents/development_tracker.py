from datetime import datetime, timedelta
from typing import Any

from ..models.schemas import Technology, TechnologyStatus
from ..memory.vector_store import VectorMemory
from .base import BaseAgent


class DevelopmentTrackerAgent(BaseAgent):
    def __init__(self, **kwargs):
        super().__init__(name="DevelopmentTrackerAgent", **kwargs)
        if not self.memory:
            self.memory = VectorMemory()
        self.tracking_window_days = 30
        self.significant_mention_threshold = 5
        self.status_change_thresholds = {
            "emerging_to_growing": {"mentions": 10, "days": 7},
            "growing_to_mature": {"mentions": 50, "days": 30},
            "mature_to_declining": {"mentions": 5, "days": 30},
        }

    async def analyze_technology_trajectory(
        self, tech_id: str, tech_data: dict
    ) -> dict[str, Any]:
        developments = self.memory.get_technology_developments(tech_id)
        mentions = self.memory.get_technology_mentions(tech_id, limit=100)

        now = datetime.now()
        recent_developments = []
        development_timeline: dict[str, int] = {}

        for dev in developments:
            dev_date = dev.get("timestamp", "")
            if dev_date:
                try:
                    dev_datetime = datetime.fromisoformat(dev_date)
                    days_ago = (now - dev_datetime).days
                    week_key = f"week_{days_ago // 7}"
                    development_timeline[week_key] = (
                        development_timeline.get(week_key, 0) + 1
                    )

                    if days_ago <= self.tracking_window_days:
                        recent_developments.append(dev)
                except (ValueError, TypeError):
                    continue

        mention_counts: dict[str, int] = {}
        for mention in mentions:
            pub_date = mention.get("published_date", "")
            if pub_date:
                try:
                    pub_datetime = datetime.fromisoformat(pub_date)
                    days_ago = (now - pub_datetime).days
                    week_key = f"week_{days_ago // 7}"
                    mention_counts[week_key] = mention_counts.get(week_key, 0) + 1
                except (ValueError, TypeError):
                    continue

        trajectory = "stable"
        if mention_counts:
            weeks = sorted(mention_counts.keys())
            if len(weeks) >= 2:
                recent_week = weeks[-1]
                previous_week = weeks[-2]

                if mention_counts[recent_week] > mention_counts[previous_week] * 1.5:
                    trajectory = "accelerating"
                elif mention_counts[recent_week] < mention_counts[previous_week] * 0.5:
                    trajectory = "decelerating"

        sentiment_trend = "neutral"
        if mentions:
            recent_mentions = []
            for m in mentions:
                pub_date = m.get("published_date", "")
                if pub_date:
                    try:
                        pub_datetime = datetime.fromisoformat(pub_date)
                        if (now - pub_datetime).days <= 14:
                            recent_mentions.append(m)
                    except (ValueError, TypeError):
                        continue

            if recent_mentions:
                avg_sentiment = sum(
                    m.get("sentiment_score", 0) for m in recent_mentions
                ) / len(recent_mentions)

                if avg_sentiment > 0.2:
                    sentiment_trend = "positive"
                elif avg_sentiment < -0.2:
                    sentiment_trend = "negative"

        return {
            "tech_id": tech_id,
            "trajectory": trajectory,
            "sentiment_trend": sentiment_trend,
            "total_developments": len(developments),
            "recent_developments": len(recent_developments),
            "total_mentions": len(mentions),
            "development_timeline": development_timeline,
            "mention_timeline": mention_counts,
        }

    async def detect_significant_developments(
        self, tech_id: str, tech_data: dict
    ) -> list[dict]:
        developments = self.memory.get_technology_developments(tech_id)
        mentions = self.memory.get_technology_mentions(tech_id, limit=50)

        significant = []

        now = datetime.now()
        week_ago = now - timedelta(days=7)

        recent_high_relevance = [
            m
            for m in mentions
            if m.get("relevance_score", 0) > 0.7
            and m.get("published_date", "")
            and datetime.fromisoformat(m["published_date"]) > week_ago
        ]

        if len(recent_high_relevance) >= self.significant_mention_threshold:
            significant.append(
                {
                    "type": "surge_in_coverage",
                    "description": f"Significant increase in media coverage detected",
                    "count": len(recent_high_relevance),
                    "timestamp": now.isoformat(),
                }
            )

        positive_sentiment_surge = [
            m
            for m in mentions
            if m.get("sentiment_score", 0) > 0.5
            and m.get("published_date", "")
            and datetime.fromisoformat(m["published_date"]) > week_ago
        ]

        if len(positive_sentiment_surge) >= 3:
            significant.append(
                {
                    "type": "positive_sentiment_surge",
                    "description": "Strong positive sentiment detected in recent coverage",
                    "count": len(positive_sentiment_surge),
                    "timestamp": now.isoformat(),
                }
            )

        if developments:
            dev_dates: dict[str, list] = {}
            for dev in developments:
                dev_date = dev.get("timestamp", "")[:10]
                if dev_date:
                    if dev_date not in dev_dates:
                        dev_dates[dev_date] = []
                    dev_dates[dev_date].append(dev)

            for date, devs in dev_dates.items():
                if len(devs) >= 3:
                    significant.append(
                        {
                            "type": "development_cluster",
                            "description": f"Multiple developments ({len(devs)}) on {date}",
                            "count": len(devs),
                            "timestamp": date,
                        }
                    )

        return significant

    async def recommend_status_change(
        self, tech_id: str, tech_data: dict
    ) -> str | None:
        current_status = tech_data.get("status", "emerging")
        mentions = self.memory.get_technology_mentions(tech_id, limit=200)

        now = datetime.now()

        recent_mentions = []
        for m in mentions:
            pub_date = m.get("published_date", "")
            if pub_date:
                try:
                    pub_datetime = datetime.fromisoformat(pub_date)
                    if (now - pub_datetime).days <= 7:
                        recent_mentions.append(m)
                except (ValueError, TypeError):
                    continue

        all_time_mentions = len(mentions)
        recent_mention_count = len(recent_mentions)

        if current_status == "emerging":
            thresholds = self.status_change_thresholds["emerging_to_growing"]
            if (
                recent_mention_count >= thresholds["mentions"] // 2
                and all_time_mentions >= thresholds["mentions"]
            ):
                return "growing"

        elif current_status == "growing":
            thresholds = self.status_change_thresholds["growing_to_mature"]
            if (
                recent_mention_count >= thresholds["mentions"] // 3
                and all_time_mentions >= thresholds["mentions"]
            ):
                return "mature"

        elif current_status == "mature":
            thresholds = self.status_change_thresholds["mature_to_declining"]
            if recent_mention_count <= thresholds["mentions"]:
                return "declining"

        elif current_status == "declining":
            if recent_mention_count >= 10:
                return "mature"

        return None

    async def generate_development_report(
        self, tech_id: str, tech_data: dict
    ) -> dict[str, Any]:
        trajectory = await self.analyze_technology_trajectory(tech_id, tech_data)
        significant = await self.detect_significant_developments(tech_id, tech_data)
        recommended_status = await self.recommend_status_change(tech_id, tech_data)

        report = {
            "tech_id": tech_id,
            "tech_name": tech_data.get("name", "Unknown"),
            "current_status": tech_data.get("status", "emerging"),
            "recommended_status": recommended_status,
            "trajectory": trajectory,
            "significant_developments": significant,
            "generated_at": datetime.now().isoformat(),
        }

        return report

    async def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        memory_update = input_data.get("memory_update", {})
        new_ids = memory_update.get("new_ids", [])
        updated_ids = memory_update.get("updated_ids", [])

        all_tracked = self.memory.get_all_technologies()

        reports = []
        for tech_data in all_tracked:
            tech_id = tech_data["id"]
            report = await self.generate_development_report(tech_id, tech_data)
            reports.append(report)

        promising = []
        for report in reports:
            trajectory = report.get("trajectory", {})
            if trajectory.get("trajectory") == "accelerating":
                promising.append(
                    {
                        "tech_id": report["tech_id"],
                        "tech_name": report["tech_name"],
                        "reason": "Accelerating development trajectory",
                        "trajectory_score": 0.9,
                    }
                )
            elif trajectory.get("sentiment_trend") == "positive":
                promising.append(
                    {
                        "tech_id": report["tech_id"],
                        "tech_name": report["tech_name"],
                        "reason": "Positive sentiment trend",
                        "trajectory_score": 0.7,
                    }
                )

        promising.sort(key=lambda x: x.get("trajectory_score", 0), reverse=True)

        result = {
            "total_technologies_tracked": len(all_tracked),
            "reports_generated": len(reports),
            "promising_technologies": promising[:10],
            "significant_developments_count": sum(
                len(r.get("significant_developments", [])) for r in reports
            ),
            "status_changes_recommended": [
                r for r in reports if r.get("recommended_status")
            ],
            "timestamp": datetime.now().isoformat(),
        }

        self.send_message(
            recipient="TechnologyAnalyzerAgent",
            message_type="development_tracking",
            content=result,
        )

        return result

    async def get_technology_timeline(self, tech_id: str) -> dict[str, Any]:
        tech_results = self.memory.search_technologies("", n_results=100)
        tech_data = None
        for t in tech_results:
            if t["id"] == tech_id:
                tech_data = t
                break

        if not tech_data:
            return {"error": "Technology not found"}

        return await self.generate_development_report(tech_id, tech_data)
