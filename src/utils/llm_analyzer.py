"""LLM-powered analysis utilities using LangChain."""

import json
import os
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


class LLMAnalyzer:
    """LLM-powered analyzer for news content and reports."""
    
    def __init__(
        self, 
        model_name: str = "gpt-4o-mini", 
        api_key: Optional[str] = None,
        temperature: float = 0.7
    ):
        """Initialize the LLM analyzer.
        
        Args:
            model_name: The OpenAI model to use.
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var).
            temperature: Temperature for LLM responses.
        """
        self.llm = ChatOpenAI(
            model=model_name,
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            temperature=temperature
        )
        self.output_parser = StrOutputParser()
    
    def _format_articles_for_prompt(self, articles: list[dict]) -> str:
        """Format articles for inclusion in prompts.
        
        Args:
            articles: List of article dictionaries.
            
        Returns:
            Formatted string for prompts.
        """
        formatted = []
        for i, article in enumerate(articles[:20], 1):
            # Use full content if available, otherwise fall back to summary
            content = article.get('content', '') or article.get('summary', '')
            # Truncate to reasonable length for prompts (500 chars for better context)
            content_preview = content[:500] if content else 'N/A'
            
            formatted.append(
                f"{i}. {article.get('title', 'N/A')}\n"
                f"   Source: {article.get('source', 'N/A')}\n"
                f"   Content: {content_preview}{'...' if len(content) > 500 else ''}"
            )
        return "\n".join(formatted)
    
    def _format_technologies_for_prompt(self, technologies: list[dict]) -> str:
        """Format technologies for inclusion in prompts.
        
        Args:
            technologies: List of technology dictionaries.
            
        Returns:
            Formatted string for prompts.
        """
        formatted = []
        for i, tech in enumerate(technologies[:20], 1):
            formatted.append(
                f"{i}. {tech.get('name', 'N/A')} "
                f"({tech.get('category', 'N/A')}) - "
                f"Status: {tech.get('status', 'N/A')}, "
                f"Trend: {tech.get('trend_direction', 'N/A')}"
            )
        return "\n".join(formatted)
    
    def _parse_json_response(self, response: str) -> dict:
        """Parse JSON from LLM response.
        
        Args:
            response: Raw LLM response string.
            
        Returns:
            Parsed dictionary or empty dict on failure.
        """
        try:
            # Try to extract JSON from the response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        return {}
    
    async def generate_executive_summary(
        self, 
        articles: list[dict], 
        technologies: list[dict]
    ) -> str:
        """Generate an intelligent executive summary using LLM.
        
        Args:
            articles: List of article dictionaries.
            technologies: List of technology dictionaries.
            
        Returns:
            Generated executive summary string.
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a technology news analyst. Generate a concise executive summary 
            of the technology news landscape based on the provided articles and technologies.
            Focus on:
            1. Key trends and patterns
            2. Significant developments
            3. Market implications
            Keep the summary to 2-3 paragraphs."""),
            ("user", """Articles:
{articles}

Technologies:
{technologies}

Generate an executive summary:""")
        ])
        
        chain = prompt | self.llm | self.output_parser
        response = await chain.ainvoke({
            "articles": self._format_articles_for_prompt(articles),
            "technologies": self._format_technologies_for_prompt(technologies)
        })
        
        return response
    
    async def analyze_significance(
        self, 
        article: dict, 
        related_technologies: list[dict]
    ) -> dict:
        """Analyze the significance of a news article using LLM.
        
        Args:
            article: Article dictionary.
            related_technologies: List of related technology dictionaries.
            
        Returns:
            Dictionary with significance analysis.
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a technology news analyst. Analyze the significance 
            of the given news article. Consider:
            1. Market impact potential (score 0-1)
            2. Technology advancement implications
            3. Competitive landscape effects
            4. Geographic relevance
            
            Return a JSON object with these keys:
            - significance_score (float 0-1)
            - market_impact (string description)
            - technology_implications (string description)
            - competitive_effects (string description)
            - geographic_relevance (string description)"""),
            ("user", """Article Title: {title}
Article Content: {content}
Related Technologies: {technologies}

Analyze the significance and return JSON:""")
        ])
        
        chain = prompt | self.llm | self.output_parser
        # Use full content if available, otherwise fall back to summary
        content = article.get("content", "") or article.get("summary", "")
        response = await chain.ainvoke({
            "title": article.get("title", ""),
            "content": content[:2000],  # Use more content for better analysis
            "technologies": ", ".join([t.get("name", "") for t in related_technologies])
        })
        
        result = self._parse_json_response(response)
        result["article_title"] = article.get("title", "")
        return result
    
    async def extract_entities_with_context(self, text: str) -> dict:
        """Extract companies and countries with context using LLM.
        
        Args:
            text: Text to extract entities from.
            
        Returns:
            Dictionary with companies and countries lists.
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Extract companies and countries mentioned in the text.
            For each entity, provide the context in which it was mentioned.
            
            Return a JSON object with these keys:
            - companies: list of objects with {name, context, sentiment (positive/negative/neutral)}
            - countries: list of objects with {name, context}"""),
            ("user", """Text: {text}

Extract entities and return JSON:""")
        ])
        
        chain = prompt | self.llm | self.output_parser
        response = await chain.ainvoke({"text": text[:2000]})
        
        result = self._parse_json_response(response)
        return {
            "companies": result.get("companies", []),
            "countries": result.get("countries", [])
        }
    
    async def generate_trend_analysis(
        self, 
        technologies: list[dict],
        articles: list[dict]
    ) -> str:
        """Generate trend analysis using LLM.
        
        Args:
            technologies: List of technology dictionaries.
            articles: List of article dictionaries.
            
        Returns:
            Generated trend analysis string.
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a technology trend analyst. Analyze the provided 
            technologies and news articles to identify:
            1. Emerging trends (what's gaining momentum)
            2. Declining technologies (what's losing attention)
            3. Cross-technology synergies (how technologies connect)
            4. Market opportunities (potential growth areas)
            
            Provide a structured analysis with clear sections."""),
            ("user", """Technologies:
{technologies}

Recent Articles:
{articles}

Generate a comprehensive trend analysis:""")
        ])
        
        chain = prompt | self.llm | self.output_parser
        response = await chain.ainvoke({
            "technologies": self._format_technologies_for_prompt(technologies),
            "articles": self._format_articles_for_prompt(articles[:15])
        })
        
        return response
    
    async def generate_company_analysis(
        self, 
        company_name: str,
        articles: list[dict]
    ) -> dict:
        """Generate detailed company analysis using LLM.
        
        Args:
            company_name: Name of the company.
            articles: List of related article dictionaries.
            
        Returns:
            Dictionary with company analysis.
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a business intelligence analyst. Analyze the news 
            coverage of a company and provide insights on:
            1. Recent activities and announcements
            2. Strategic direction
            3. Market position
            4. Technology focus areas
            
            Provide a concise analysis in 2-3 paragraphs."""),
            ("user", """Company: {company}

Related Articles:
{articles}

Generate a company analysis:""")
        ])
        
        chain = prompt | self.llm | self.output_parser
        response = await chain.ainvoke({
            "company": company_name,
            "articles": self._format_articles_for_prompt(articles)
        })
        
        return {
            "company": company_name,
            "analysis": response,
            "article_count": len(articles)
        }
    
    async def generate_market_impact_summary(
        self, 
        significance_analyses: list[dict]
    ) -> str:
        """Generate a summary of market impact from significance analyses.
        
        Args:
            significance_analyses: List of significance analysis dictionaries.
            
        Returns:
            Generated market impact summary string.
        """
        if not significance_analyses:
            return "No significant market impacts identified in this period."
        
        # Format analyses for prompt
        analyses_text = []
        for analysis in significance_analyses[:10]:
            analyses_text.append(
                f"- {analysis.get('article_title', 'Unknown')}: "
                f"{analysis.get('market_impact', 'N/A')}"
            )
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a market analyst. Synthesize the following market impact 
            analyses into a cohesive summary. Identify common themes, overall market direction, 
            and key takeaways. Keep it to 1-2 paragraphs."""),
            ("user", """Market Impact Analyses:
{analyses}

Generate a market impact summary:""")
        ])
        
        chain = prompt | self.llm | self.output_parser
        response = await chain.ainvoke({
            "analyses": "\n".join(analyses_text)
        })
        
        return response
    
    async def generate_geographic_insights(
        self, 
        countries: list[dict],
        articles: list[dict]
    ) -> str:
        """Generate geographic insights using LLM.
        
        Args:
            countries: List of country dictionaries with mention counts.
            articles: List of article dictionaries.
            
        Returns:
            Generated geographic insights string.
        """
        if not countries:
            return "No significant geographic patterns identified in this period."
        
        countries_text = [
            f"- {c.get('name', 'Unknown')}: {c.get('mention_count', 0)} mentions"
            for c in countries[:10]
        ]
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a geopolitical analyst. Analyze the geographic distribution 
            of technology news coverage. Consider:
            1. Regional technology hubs and their focus areas
            2. Emerging markets
            3. Geographic shifts in technology development
            Keep the analysis to 1-2 paragraphs."""),
            ("user", """Countries Mentioned:
{countries}

Generate geographic insights:""")
        ])
        
        chain = prompt | self.llm | self.output_parser
        response = await chain.ainvoke({
            "countries": "\n".join(countries_text)
        })
        
        return response
    
    async def generate_technology_outlook(
        self, 
        technologies: list[dict],
        trend_analysis: str
    ) -> str:
        """Generate technology outlook using LLM.
        
        Args:
            technologies: List of technology dictionaries.
            trend_analysis: Previously generated trend analysis.
            
        Returns:
            Generated technology outlook string.
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a technology futurist. Based on the current trends and 
            technologies, provide an outlook for the next 6-12 months. Consider:
            1. Technologies likely to gain momentum
            2. Potential breakthroughs
            3. Investment opportunities
            4. Risk areas
            Keep the outlook to 2-3 paragraphs."""),
            ("user", """Current Technologies:
{technologies}

Trend Analysis:
{trend_analysis}

Generate a technology outlook:""")
        ])
        
        chain = prompt | self.llm | self.output_parser
        response = await chain.ainvoke({
            "technologies": self._format_technologies_for_prompt(technologies[:15]),
            "trend_analysis": trend_analysis[:1000]
        })
        
        return response
    
    async def categorize_article(self, article: dict) -> str:
        """Categorize an article using LLM.
        
        Args:
            article: Article dictionary.
            
        Returns:
            Category string.
        """
        categories = [
            "AI/ML", "Quantum Computing", "Blockchain/Web3", "Robotics",
            "Cloud/Infrastructure", "Cybersecurity", "Telecommunications",
            "IoT", "AR/VR/MR", "Biotech", "Energy/Cleantech", "Semiconductors",
            "Hardware/Interfaces", "Space Tech", "Manufacturing", "Materials",
            "General Technology"
        ]
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", f"""You are a technology news categorizer. Categorize the given 
            article into exactly one of these categories:
            {', '.join(categories)}
            
            Return only the category name, nothing else."""),
            ("user", """Article Title: {title}
Article Content: {content}

Category:""")
        ])
        
        chain = prompt | self.llm | self.output_parser
        # Use full content if available, otherwise fall back to summary
        content = article.get("content", "") or article.get("summary", "")
        response = await chain.ainvoke({
            "title": article.get("title", ""),
            "content": content[:1000]  # Use more content for better categorization
        })
        
        category = response.strip()
        return category if category in categories else "General Technology"
