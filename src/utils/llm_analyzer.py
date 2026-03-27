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
        model_name: str = "qwen/qwen3.5-27b",
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        """Initialize the LLM analyzer.

        Args:
            model_name: The model to use (for backward compatibility).
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var).
            temperature: Temperature for LLM responses.
            base_url: Base URL for API (for OpenRouter or custom endpoints).
            model: Alternative parameter for model name (takes precedence over model_name).
        """
        # Use model parameter if provided, otherwise fall back to model_name
        effective_model = model or model_name

        # Build ChatOpenAI kwargs
        llm_kwargs = {
            "model": effective_model,
            "api_key": api_key or os.getenv("OPENAI_API_KEY"),
            "temperature": temperature
        }

        # Add base_url if provided
        if base_url:
            llm_kwargs["base_url"] = base_url

        self.llm = ChatOpenAI(**llm_kwargs)
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
            - companies: list of objects with {{name, context, sentiment (positive/negative/neutral)}}
            - countries: list of objects with {{name, context}}"""),
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

    async def extract_all_entities(
        self,
        title: str,
        content: str = "",
        summary: str = ""
    ) -> dict:
        """Extract all entities (technologies, companies, countries) from article in a single LLM call.

        This unified method extracts technologies, companies, and countries in one call
        for efficiency and consistency.

        Args:
            title: The article title.
            content: The article content (optional).
            summary: The article summary (optional).

        Returns:
            Dictionary with:
            - is_technology_related (bool): whether the article is tech-related
            - technologies (list): list of technology topics with category and relevance
            - companies (list): list of companies with country and context
            - countries (list): list of countries with context
            - confidence (float): confidence level of the extraction
        """
        # Combine available text, prioritizing content over summary
        full_text = f"{title}\n\n"
        if content:
            full_text += content[:2000]
        elif summary:
            full_text += summary[:1000]

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a technology news analyzer. Extract ALL entities from the given article 
            in a single comprehensive analysis.

            Extract the following:
            1. TECHNOLOGIES: Technology topics, products, frameworks, or concepts mentioned
               - Include AI/ML, programming languages, frameworks, hardware, cloud services, etc.
               - For each technology, provide:
                 * name: the technology name
                 * category: one of [AI/ML, Quantum Computing, Blockchain/Web3, Robotics, 
                   Cloud/Infrastructure, Cybersecurity, Telecommunications, IoT, AR/VR/MR, 
                   Biotech, Energy/Cleantech, Semiconductors, Hardware/Interfaces, Space Tech, 
                   Manufacturing, Materials, General Technology]
                 * relevance: relevance score 0-1
                 * context: brief context of how it's mentioned

            2. COMPANIES: Companies and organizations mentioned
               - Include tech companies, startups, research labs, etc.
               - For each company, provide:
                 * name: company name
                 * country: country of origin if known (or null)
                 * industry: industry sector if known (or null)
                 * context: brief context of how it's mentioned
                 * sentiment: positive, negative, or neutral

            3. COUNTRIES: Countries and regions mentioned in relation to technology
               - For each country, provide:
                 * name: country name
                 * context: brief context of how it's mentioned

            4. CLASSIFICATION:
               - is_technology_related: true if the article is primarily about technology
               - confidence: confidence level 0-1 for the classification

            Return a JSON object with these exact keys:
            {{
                "is_technology_related": boolean,
                "confidence": float,
                "technologies": [
                    {{"name": string, "category": string, "relevance": float, "context": string}}
                ],
                "companies": [
                    {{"name": string, "country": string or null, "industry": string or null,
                     "context": string, "sentiment": string}}
                ],
                "countries": [
                    {{"name": string, "context": string}}
                ]
            }}"""),
            ("user", """Article Title: {title}

Article Content:
{content}

Extract all entities and return JSON:""")
        ])

        chain = prompt | self.llm | self.output_parser
        response = await chain.ainvoke({
            "title": title,
            "content": full_text[:2500]  # Limit total text length
        })

        result = self._parse_json_response(response)

        # Normalize and validate results
        is_tech = result.get("is_technology_related", False)
        if isinstance(is_tech, str):
            is_tech = is_tech.lower() in ("true", "yes", "1")

        confidence = result.get("confidence", 0.5)
        if isinstance(confidence, str):
            try:
                confidence = float(confidence)
            except ValueError:
                confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))

        # Ensure all lists exist
        technologies = result.get("technologies", [])
        companies = result.get("companies", [])
        countries = result.get("countries", [])

        # Validate and normalize technology entries
        validated_technologies = []
        for tech in technologies:
            if isinstance(tech, dict) and tech.get("name"):
                validated_technologies.append({
                    "name": tech["name"],
                    "category": tech.get("category", "General Technology"),
                    "relevance": max(0.0, min(1.0, float(tech.get("relevance", 0.5)))),
                    "context": tech.get("context", "")
                })

        # Validate and normalize company entries
        validated_companies = []
        for company in companies:
            if isinstance(company, dict) and company.get("name"):
                validated_companies.append({
                    "name": company["name"],
                    "country": company.get("country"),
                    "industry": company.get("industry"),
                    "context": company.get("context", ""),
                    "sentiment": company.get("sentiment", "neutral")
                })

        # Validate and normalize country entries
        validated_countries = []
        for country in countries:
            if isinstance(country, dict) and country.get("name"):
                validated_countries.append({
                    "name": country["name"],
                    "context": country.get("context", "")
                })

        return {
            "is_technology_related": bool(is_tech),
            "confidence": confidence,
            "technologies": validated_technologies,
            "companies": validated_companies,
            "countries": validated_countries
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

    async def analyze_article_relevance(
        self,
        title: str,
        summary: str = ""
    ) -> tuple[bool, list[str], float]:
        """Analyze if an article is technology-related and calculate relevance in a single LLM call.

        This combined method is more efficient than calling is_technology_related and
        calculate_relevance separately, as it makes only one LLM request.

        Args:
            title: The article title to analyze.
            summary: Optional article summary for additional context.

        Returns:
            Tuple of (is_tech_related: bool, tech_topics: list[str], relevance_score: float)
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a technology news classifier and relevance assessor. Analyze the given
            article title and summary to:
            1. Determine if it is related to technology topics
            2. Identify the technology topics mentioned
            3. Assess the relevance score for technology readers
            
            Technology topics include but are not limited to:
            - Artificial Intelligence, Machine Learning, Deep Learning, LLMs
            - Software development, programming languages, frameworks
            - Hardware, semiconductors, chips, processors
            - Cloud computing, infrastructure, DevOps
            - Cybersecurity, privacy, encryption
            - Mobile devices, smartphones, tablets
            - Internet, web technologies, APIs
            - Data science, analytics, big data
            - Blockchain, cryptocurrency, Web3
            - Robotics, automation, autonomous systems
            - Biotechnology, medical technology
            - Energy technology, clean tech
            - Space technology, satellites
            - Telecommunications, 5G/6G
            - AR/VR, metaverse
            - IoT, smart devices
            - Electric vehicles, autonomous vehicles
            
            Relevance scoring guidelines:
            - 0.0-0.2: Technology mentioned only in passing, not the main focus
            - 0.3-0.5: Technology is discussed but not deeply, or is peripheral to main topic
            - 0.6-0.8: Technology is a significant focus, good depth of coverage
            - 0.9-1.0: Deep technology analysis, breaking news, or highly significant development
            
            Return a JSON object with these keys:
            - is_technology_related (boolean): true if the article is about technology
            - tech_topics (list of strings): technology topics mentioned in the article
            - relevance_score (float 0-1): overall relevance to technology
            - confidence (float 0-1): confidence level of the classification"""),
            ("user", """Article Title: {title}
Article Summary: {summary}

Analyze and return JSON:""")
        ])

        chain = prompt | self.llm | self.output_parser
        response = await chain.ainvoke({
            "title": title,
            "summary": summary[:500] if summary else "N/A"
        })

        result = self._parse_json_response(response)
        is_tech = result.get("is_technology_related", False)
        topics = result.get("tech_topics", [])
        relevance = result.get("relevance_score", 0.5)

        # Ensure is_tech is a boolean
        if isinstance(is_tech, str):
            is_tech = is_tech.lower() in ("true", "yes", "1")

        # Ensure relevance is a float in valid range
        if isinstance(relevance, str):
            try:
                relevance = float(relevance)
            except ValueError:
                relevance = 0.5
        relevance = max(0.0, min(1.0, float(relevance)))

        return bool(is_tech), topics, relevance

