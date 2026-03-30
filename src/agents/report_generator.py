"""Report Generator Agent for generating markdown analysis reports."""

import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from ..models.schemas import GeneratedReport, ReportSection
from ..storage.sqlite_store import SQLiteStore
from ..utils.llm_analyzer import LLMAnalyzer
from ..utils.entity_extractor import EntityExtractor
from ..config.llm_config import LLMConfig
from .base import BaseAgent


class ReportGeneratorAgent(BaseAgent):
    """Agent for generating comprehensive markdown reports."""
    
    def __init__(
        self,
        sqlite_store: SQLiteStore = None,
        llm_analyzer: LLMAnalyzer = None,
        report_dir: str = "./reports",
        use_llm: bool = True,
        **kwargs
    ):
        """Initialize the report generator agent.
        
        Args:
            sqlite_store: SQLite store for data retrieval.
            llm_analyzer: LLM analyzer for intelligent analysis.
            report_dir: Directory to save reports.
            use_llm: Whether to use LLM for enhanced analysis.
            **kwargs: Additional arguments for BaseAgent.
        """
        super().__init__(name="ReportGeneratorAgent", **kwargs)
        self.sqlite_store = sqlite_store or SQLiteStore()
        self.llm_analyzer = llm_analyzer
        self.use_llm = use_llm
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        
        if use_llm and not llm_analyzer:
            try:
                # Initialize LLM with configuration from LLMConfig
                llm_kwargs = LLMConfig.create_llm_kwargs("report_generator")
                self.llm_analyzer = LLMAnalyzer(**llm_kwargs)
            except Exception as e:
                print(f"Warning: Could not initialize LLM analyzer: {e}")
                self.use_llm = False
    
    async def process(self, input_data: dict) -> GeneratedReport:
        """Generate a comprehensive report.
        
        Args:
            input_data: Dictionary containing:
                - period_start: Start date for the report period.
                - period_end: End date for the report period.
                - technologies: List of technology data.
                - developments: Development tracking data.
                
        Returns:
            GeneratedReport object.
        """
        period_start = input_data.get("period_start")
        period_end = input_data.get("period_end")
        
        # Parse dates if strings
        if isinstance(period_start, str):
            period_start = datetime.fromisoformat(period_start)
        if isinstance(period_end, str):
            period_end = datetime.fromisoformat(period_end)
        
        # Default to last 7 days if not specified
        if not period_end:
            period_end = datetime.now()
        if not period_start:
            period_start = period_end - timedelta(days=7)
        
        # Gather data
        articles = self.sqlite_store.get_articles_by_date_range(
            period_start, period_end, limit=100
        )
        technologies = input_data.get("technologies", [])
        developments = input_data.get("developments", {})
        
        # Get entity data
        top_companies = self.sqlite_store.get_top_companies(limit=10)
        top_countries = self.sqlite_store.get_top_countries(limit=10)
        
        # Generate report components
        title = self._generate_title(articles, technologies, period_start, period_end)
        
        # Single LLM call to generate all report content (if LLM is enabled)
        llm_report_data = await self._generate_report_with_single_llm_call(
            articles, technologies, top_companies, top_countries
        )
        
        executive_summary = llm_report_data.get("executive_summary") or self._generate_template_summary(articles, technologies)
        sections = self._build_sections_from_llm_data(
            llm_report_data, articles, technologies, developments, top_companies, top_countries
        )
        notable_technologies = self._get_notable_technologies(technologies)
        key_companies = self._format_companies(top_companies, articles)
        key_countries = self._format_countries(top_countries)
        significance_analysis = self._build_significance_from_llm_data(
            llm_report_data, articles, technologies
        )
        
        # Create report object
        report = GeneratedReport(
            id=str(uuid.uuid4()),
            generated_date=datetime.now(),
            period_start=period_start,
            period_end=period_end,
            title=title,
            executive_summary=executive_summary,
            sections=sections,
            notable_technologies=notable_technologies,
            key_companies=key_companies,
            key_countries=key_countries,
            significance_analysis=significance_analysis,
        )
        
        # Save report to file
        file_path = self._save_report(report)
        report.file_path = str(file_path)
        
        # Store report metadata
        self.sqlite_store.store_report_metadata({
            "id": report.id,
            "generated_date": report.generated_date.isoformat(),
            "period_start": report.period_start.isoformat(),
            "period_end": report.period_end.isoformat(),
            "file_path": report.file_path,
            "summary": report.executive_summary[:500],
        })
        
        # Send message about report generation
        self.send_message(
            recipient="MemoryManagerAgent",
            message_type="report_generated",
            content={
                "report_id": report.id,
                "file_path": report.file_path,
                "articles_analyzed": len(articles),
                "technologies_covered": len(technologies),
            }
        )
        
        return report
    
    async def _generate_report_with_single_llm_call(
        self,
        articles: list[dict],
        technologies: list,
        top_companies: list[dict],
        top_countries: list[dict]
    ) -> dict:
        """Generate all report content with a single LLM call.
        
        This is the optimized approach that reduces LLM calls from ~9 to 1.
        
        Args:
            articles: List of article dictionaries.
            technologies: List of technology data.
            top_companies: List of top companies.
            top_countries: List of top countries.
            
        Returns:
            Dictionary with all LLM-generated report sections.
        """
        if not self.use_llm or not self.llm_analyzer or not articles:
            return {}
        
        try:
            tech_dicts = [t if isinstance(t, dict) else t.model_dump() for t in technologies]
            return await self.llm_analyzer.generate_complete_report(
                articles, tech_dicts, top_companies, top_countries
            )
        except Exception as e:
            print(f"LLM report generation failed: {e}")
            return {}
    
    def _build_sections_from_llm_data(
        self,
        llm_data: dict,
        articles: list[dict],
        technologies: list,
        developments: dict,
        top_companies: list[dict],
        top_countries: list[dict]
    ) -> list[ReportSection]:
        """Build report sections from LLM-generated data with fallbacks.
        
        Args:
            llm_data: Dictionary from single LLM call.
            articles: List of articles.
            technologies: List of technologies.
            developments: Development tracking data.
            top_companies: Top companies data.
            top_countries: Top countries data.
            
        Returns:
            List of ReportSection objects.
        """
        sections = []
        
        # Technology Trends Section - use LLM data or fallback
        trends_content = llm_data.get("trend_analysis")
        if not trends_content:
            trends_content = self._generate_fallback_trends(technologies)
        sections.append(ReportSection(
            title="Technology Trends",
            content=trends_content,
            priority=1
        ))
        
        # Key Developments Section - template-based (no LLM needed)
        developments_content = self._generate_developments_section(technologies, developments)
        sections.append(ReportSection(
            title="Key Developments",
            content=developments_content,
            priority=2
        ))
        
        # Companies Section - template-based (no LLM needed)
        companies_content = self._generate_companies_section(top_companies)
        sections.append(ReportSection(
            title="Companies in Focus",
            content=companies_content,
            priority=3
        ))
        
        # Geographic Insights Section - use LLM data or fallback
        geo_content = llm_data.get("geographic_insights")
        if not geo_content:
            geo_content = self._generate_geographic_section(top_countries)
        sections.append(ReportSection(
            title="Geographic Insights",
            content=geo_content,
            priority=4
        ))
        
        # Significance Analysis Section - use LLM data or fallback
        significance_content = self._build_significance_section_from_llm_data(
            llm_data, articles, technologies
        )
        sections.append(ReportSection(
            title="Significance Analysis",
            content=significance_content,
            priority=5
        ))
        
        # Sort by priority
        sections.sort(key=lambda x: x.priority)
        return sections
    
    def _generate_fallback_trends(self, technologies: list) -> str:
        """Generate fallback trends section when LLM data is not available."""
        if not technologies:
            return "No significant technology trends identified in this period."
        
        content = "### Identified Technologies\n\n"
        for tech in technologies[:10]:
            if isinstance(tech, dict):
                name = tech.get("name", "Unknown")
                category = tech.get("category", "General")
                status = tech.get("status", "emerging")
                trend = tech.get("trend_direction", "stable")
            else:
                name = tech.name
                category = tech.category
                status = tech.status.value if hasattr(tech.status, "value") else tech.status
                trend = tech.trend_direction
            
            content += f"- **{name}** ({category}) - Status: {status}, Trend: {trend}\n"
        
        return content
    
    def _build_significance_section_from_llm_data(
        self,
        llm_data: dict,
        articles: list[dict],
        technologies: list
    ) -> str:
        """Build significance section from LLM data with fallback."""
        if not articles:
            return "No articles to analyze for significance."
        
        content = "### Market Impact Analysis\n\n"
        
        # Get high-relevance articles
        high_relevance = sorted(
            articles,
            key=lambda x: x.get("relevance_score", 0),
            reverse=True
        )[:5]
        
        # Try to use LLM-generated significance data
        sig_data = llm_data.get("significance_analysis", {})
        top_articles_analysis = sig_data.get("top_articles", [])
        
        if top_articles_analysis:
            for analysis in top_articles_analysis:
                content += f"**{analysis.get('title', 'Unknown')}**\n"
                content += f"- Significance Score: {analysis.get('significance_score', 0):.2f}\n"
                content += f"- Market Impact: {analysis.get('market_impact', 'N/A')}\n"
                content += f"- Technology Implications: {analysis.get('technology_implications', 'N/A')}\n\n"
            
            market_summary = sig_data.get("market_impact_summary", "")
            if market_summary:
                content += f"**Summary:** {market_summary}\n"
        else:
            # Fallback to template-based analysis
            content += self._generate_template_significance(high_relevance)
        
        return content
    
    def _build_significance_from_llm_data(
        self,
        llm_data: dict,
        articles: list[dict],
        technologies: list
    ) -> dict:
        """Build significance analysis dict from LLM data with fallback."""
        if not articles:
            return {}
        
        # Get top articles by relevance
        top_articles = sorted(
            articles,
            key=lambda x: x.get("relevance_score", 0),
            reverse=True
        )[:10]
        
        result = {
            "total_articles": len(articles),
            "high_relevance_count": len([a for a in articles if a.get("relevance_score", 0) > 0.5]),
            "average_sentiment": sum(a.get("sentiment_score", 0) for a in articles) / len(articles) if articles else 0,
            "top_articles": [
                {
                    "title": a.get("title", ""),
                    "relevance_score": a.get("relevance_score", 0),
                    "sentiment_score": a.get("sentiment_score", 0),
                }
                for a in top_articles
            ],
        }
        
        # Add LLM-generated market impact summary if available
        sig_data = llm_data.get("significance_analysis", {})
        if sig_data.get("market_impact_summary"):
            result["market_impact_summary"] = sig_data["market_impact_summary"]
        
        return result
    
    def _generate_title(
        self, 
        articles: list[dict], 
        technologies: list, 
        period_start: datetime,
        period_end: datetime
    ) -> str:
        """Generate report title."""
        date_range = f"{period_start.strftime('%Y-%m-%d')} to {period_end.strftime('%Y-%m-%d')}"
        return f"Technology News Analysis Report\n**Period:** {date_range}"
    
    def _generate_template_summary(
        self,
        articles: list[dict],
        technologies: list
    ) -> str:
        """Generate a template-based executive summary using article content."""
        total_articles = len(articles)
        total_technologies = len(technologies)
        
        if total_articles == 0:
            return "No articles were collected during this reporting period."
        
        # Get top sources
        sources = {}
        for article in articles:
            source = article.get("source", "Unknown")
            sources[source] = sources.get(source, 0) + 1
        top_sources = sorted(sources.items(), key=lambda x: x[1], reverse=True)[:3]
        
        # Get average sentiment
        sentiments = [a.get("sentiment_score", 0) for a in articles]
        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0
        sentiment_desc = "positive" if avg_sentiment > 0.1 else "negative" if avg_sentiment < -0.1 else "neutral"
        
        # Extract key themes from article content
        key_themes = self._extract_key_themes(articles)
        
        summary = f"""During this reporting period, {total_articles} technology-related articles were analyzed from {len(sources)} sources. """
        
        if top_sources:
            summary += f"The primary sources were {', '.join([s[0] for s in top_sources])}. "
        
        summary += f"\n\n{total_technologies} technologies were identified and tracked. "
        summary += f"The overall market sentiment was {sentiment_desc} (score: {avg_sentiment:.2f})."
        
        if key_themes:
            summary += f"\n\n**Key Themes Identified:**\n{key_themes}"
        
        return summary
    
    def _extract_key_themes(self, articles: list[dict]) -> str:
        """Extract key themes from article content."""
        if not articles:
            return ""
        
        # Collect content from articles
        all_content = []
        for article in articles[:20]:
            content = article.get("content", "") or article.get("summary", "")
            if content:
                all_content.append(content[:500])
        
        if not all_content:
            return ""
        
        # Simple keyword-based theme extraction
        theme_keywords = {
            "Artificial Intelligence": ["AI", "artificial intelligence", "machine learning", "deep learning", "neural network", "LLM", "GPT"],
            "Cloud Computing": ["cloud", "AWS", "Azure", "Google Cloud", "kubernetes", "serverless"],
            "Cybersecurity": ["security", "cyber", "hack", "breach", "encryption", "zero trust"],
            "Semiconductors": ["chip", "semiconductor", "processor", "GPU", "NVIDIA", "Intel", "AMD"],
            "Blockchain/Web3": ["blockchain", "crypto", "bitcoin", "ethereum", "web3", "NFT"],
            "Quantum Computing": ["quantum", "qubit", "quantum computing"],
            "Robotics": ["robot", "robotics", "autonomous", "drone"],
            "Biotechnology": ["biotech", "gene", "CRISPR", "genomic", "pharmaceutical"],
        }
        
        theme_counts = {}
        combined_text = " ".join(all_content).lower()
        
        for theme, keywords in theme_keywords.items():
            count = sum(combined_text.count(kw.lower()) for kw in keywords)
            if count > 0:
                theme_counts[theme] = count
        
        if not theme_counts:
            return ""
        
        # Sort by count and return top themes
        sorted_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        return "\n".join([f"- {theme}" for theme, _ in sorted_themes])
    
    def _generate_developments_section(
        self, 
        technologies: list, 
        developments: dict
    ) -> str:
        """Generate key developments section."""
        content = ""
        
        # From technologies
        tech_developments = []
        for tech in technologies[:5]:
            if isinstance(tech, dict):
                name = tech.get("name", "Unknown")
                key_devs = tech.get("key_developments", [])
            else:
                name = tech.name
                key_devs = tech.key_developments
            
            if key_devs:
                tech_developments.append((name, key_devs[:3]))
        
        if tech_developments:
            content += "### Technology Developments\n\n"
            for name, devs in tech_developments:
                content += f"**{name}:**\n"
                for dev in devs:
                    content += f"  - {dev}\n"
                content += "\n"
        
        # From development tracker
        promising = developments.get("promising_technologies", [])
        if promising:
            content += "### Promising Technologies\n\n"
            for p in promising[:5]:
                content += f"- **{p.get('tech_name', 'Unknown')}**: {p.get('reason', 'N/A')}\n"
        
        status_changes = developments.get("status_changes_recommended", [])
        if status_changes:
            content += "\n### Recommended Status Changes\n\n"
            for sc in status_changes[:5]:
                content += f"- **{sc.get('tech_name', 'Unknown')}**: {sc.get('current_status', 'N/A')} → {sc.get('recommended_status', 'N/A')}\n"
        
        if not content:
            content = "No significant developments identified in this period."
        
        return content
    
    def _generate_companies_section(self, companies: list[dict]) -> str:
        """Generate companies section."""
        if not companies:
            return "No companies were prominently mentioned in this period."
        
        content = "### Most Mentioned Companies\n\n"
        content += "| Company | Country | Mentions |\n"
        content += "|---------|---------|----------|\n"
        
        for company in companies[:10]:
            name = company.get("name", "Unknown")
            country = company.get("country", "N/A")
            mentions = company.get("mention_count", 0)
            content += f"| {name} | {country} | {mentions} |\n"
        
        return content
    
    def _generate_geographic_section(self, countries: list[dict]) -> str:
        """Generate geographic insights section."""
        if not countries:
            return "No significant geographic patterns identified in this period."
        
        content = "### Countries in Focus\n\n"
        content += "| Country | Mentions |\n"
        content += "|---------|----------|\n"
        
        for country in countries[:10]:
            name = country.get("name", "Unknown")
            mentions = country.get("mention_count", 0)
            content += f"| {name} | {mentions} |\n"
        
        return content
    
    def _generate_template_significance(self, articles: list[dict]) -> str:
        """Generate template-based significance analysis using article content."""
        content = ""
        for article in articles:
            title = article.get("title", "Unknown")
            relevance = article.get("relevance_score", 0)
            sentiment = article.get("sentiment_score", 0)
            # Use full content if available, otherwise fall back to summary
            article_content = article.get("content", "") or article.get("summary", "")
            content_preview = article_content[:300] if article_content else "No content available"
            
            content += f"**{title}**\n"
            content += f"- Relevance Score: {relevance:.2f}\n"
            content += f"- Sentiment: {sentiment:.2f}\n"
            content += f"- Key Content: {content_preview}{'...' if len(article_content) > 300 else ''}\n\n"
        
        return content
    
    def _get_notable_technologies(self, technologies: list) -> list[dict]:
        """Get notable technologies for the report."""
        notable = []
        for tech in technologies[:10]:
            if isinstance(tech, dict):
                notable.append(tech)
            else:
                notable.append(tech.model_dump())
        return notable
    
    def _format_companies(self, companies: list[dict], articles: list[dict]) -> list[dict]:
        """Format companies for the report."""
        return [
            {
                "name": c.get("name", "Unknown"),
                "country": c.get("country", "N/A"),
                "mention_count": c.get("mention_count", 0),
            }
            for c in companies[:10]
        ]
    
    def _format_countries(self, countries: list[dict]) -> list[dict]:
        """Format countries for the report."""
        return [
            {
                "name": c.get("name", "Unknown"),
                "code": c.get("code", "N/A"),
                "mention_count": c.get("mention_count", 0),
            }
            for c in countries[:10]
        ]
    
    def _save_report(self, report: GeneratedReport) -> Path:
        """Save report as markdown file.
        
        Args:
            report: GeneratedReport object.
            
        Returns:
            Path to the saved file.
        """
        timestamp = report.generated_date.strftime("%Y%m%d_%H%M%S")
        filename = f"report_{timestamp}.md"
        file_path = self.report_dir / filename
        
        content = self._format_markdown(report)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        return file_path
    
    def _format_markdown(self, report: GeneratedReport) -> str:
        """Format report as markdown.
        
        Args:
            report: GeneratedReport object.
            
        Returns:
            Markdown string.
        """
        lines = []
        
        # Title
        lines.append(f"# {report.title}")
        lines.append("")
        lines.append(f"**Generated:** {report.generated_date.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        # Executive Summary
        lines.append("## Executive Summary")
        lines.append("")
        lines.append(report.executive_summary)
        lines.append("")
        
        # Sections
        for section in report.sections:
            lines.append(f"## {section.title}")
            lines.append("")
            lines.append(section.content)
            lines.append("")
        
        # Notable Technologies Table
        if report.notable_technologies:
            lines.append("## Notable Technologies")
            lines.append("")
            lines.append("| Technology | Category | Status | Trend | Confidence |")
            lines.append("|------------|----------|--------|-------|------------|")
            for tech in report.notable_technologies:
                lines.append(
                    f"| {tech.get('name', 'N/A')} | {tech.get('category', 'N/A')} | "
                    f"{tech.get('status', 'N/A')} | {tech.get('trend_direction', 'N/A')} | "
                    f"{tech.get('confidence_score', 0):.2f} |"
                )
            lines.append("")
        
        # Key Companies Table
        if report.key_companies:
            lines.append("## Key Companies")
            lines.append("")
            lines.append("| Company | Country | Mentions |")
            lines.append("|---------|---------|----------|")
            for company in report.key_companies:
                lines.append(
                    f"| {company.get('name', 'N/A')} | {company.get('country', 'N/A')} | "
                    f"{company.get('mention_count', 0)} |"
                )
            lines.append("")
        
        # Key Countries Table
        if report.key_countries:
            lines.append("## Countries in Focus")
            lines.append("")
            lines.append("| Country | Code | Mentions |")
            lines.append("|---------|------|----------|")
            for country in report.key_countries:
                lines.append(
                    f"| {country.get('name', 'N/A')} | {country.get('code', 'N/A')} | "
                    f"{country.get('mention_count', 0)} |"
                )
            lines.append("")
        
        # Significance Analysis Summary
        if report.significance_analysis:
            lines.append("## Analysis Summary")
            lines.append("")
            sa = report.significance_analysis
            lines.append(f"- **Total Articles Analyzed:** {sa.get('total_articles', 0)}")
            lines.append(f"- **High Relevance Articles:** {sa.get('high_relevance_count', 0)}")
            lines.append(f"- **Average Sentiment:** {sa.get('average_sentiment', 0):.2f}")
            lines.append("")
        
        # Footer
        lines.append("---")
        lines.append("")
        lines.append("*This report was generated by the Tech News Multi-Agent System.*")
        
        return "\n".join(lines)
