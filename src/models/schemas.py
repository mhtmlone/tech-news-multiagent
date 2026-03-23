from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum


class TechnologyStatus(str, Enum):
    EMERGING = "emerging"
    GROWING = "growing"
    MATURE = "mature"
    DECLINING = "declining"


class TechnologyMention(BaseModel):
    source: str
    url: str
    title: str
    published_date: datetime
    summary: str
    sentiment_score: float = Field(ge=-1.0, le=1.0, default=0.0)
    relevance_score: float = Field(ge=0.0, le=1.0, default=0.0)


class Technology(BaseModel):
    id: str
    name: str
    description: str
    category: str
    status: TechnologyStatus = TechnologyStatus.EMERGING
    first_seen: datetime
    last_updated: datetime
    mentions: list[TechnologyMention] = Field(default_factory=list)
    related_technologies: list[str] = Field(default_factory=list)
    key_developments: list[str] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0, default=0.5)
    trend_direction: str = "stable"
    hype_level: float = Field(ge=0.0, le=1.0, default=0.0)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AnalysisReport(BaseModel):
    id: str
    timestamp: datetime
    new_technologies: list[Technology] = Field(default_factory=list)
    updated_technologies: list[Technology] = Field(default_factory=list)
    promising_technologies: list[Technology] = Field(default_factory=list)
    summary: str


class AgentMessage(BaseModel):
    sender: str
    recipient: str
    message_type: str
    content: dict
    timestamp: datetime = Field(default_factory=datetime.now)


class MemoryEntry(BaseModel):
    id: str
    technology_name: str
    content: str
    metadata: dict
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    embedding: Optional[list[float]] = None


# New models for news collection and report generation

class NewsArticle(BaseModel):
    """Model for storing news articles in SQLite."""
    id: str
    title: str
    url: str
    source: str
    author: Optional[str] = None
    published_date: Optional[datetime] = None
    collected_date: datetime = Field(default_factory=datetime.now)
    summary: str = ""
    content: Optional[str] = None
    sentiment_score: float = Field(ge=-1.0, le=1.0, default=0.0)
    relevance_score: float = Field(ge=0.0, le=1.0, default=0.0)
    category: str = "General"
    keywords: list[str] = Field(default_factory=list)
    processed: bool = False

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Company(BaseModel):
    """Model for company entities."""
    id: str
    name: str
    country: Optional[str] = None
    industry: Optional[str] = None
    first_mentioned: datetime = Field(default_factory=datetime.now)
    last_mentioned: datetime = Field(default_factory=datetime.now)
    mention_count: int = 1

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class CountryMention(BaseModel):
    """Model for country mentions."""
    id: str
    name: str
    code: Optional[str] = None
    mention_count: int = 1
    last_mentioned: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class EntityExtraction(BaseModel):
    """Model for extracted entities from text."""
    companies: list[Company] = Field(default_factory=list)
    countries: list[CountryMention] = Field(default_factory=list)
    context: dict[str, str] = Field(default_factory=dict)


class TechnologyMention(BaseModel):
    """Model for a technology mention in an article."""
    name: str
    category: str = "General Technology"
    relevance: float = Field(ge=0.0, le=1.0, default=0.5)
    context: str = ""


class UnifiedExtraction(BaseModel):
    """Model for unified extraction results from LLM."""
    is_technology_related: bool = True
    technologies: list[TechnologyMention] = Field(default_factory=list)
    companies: list[Company] = Field(default_factory=list)
    countries: list[CountryMention] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class ReportSection(BaseModel):
    """Model for a section in a report."""
    title: str
    content: str
    priority: int = 0


class SignificanceAnalysis(BaseModel):
    """Model for significance analysis of an article."""
    article_title: str
    significance_score: float = Field(ge=0.0, le=1.0, default=0.5)
    market_impact: str = ""
    technology_implications: str = ""
    competitive_effects: str = ""
    geographic_relevance: str = ""


class GeneratedReport(BaseModel):
    """Model for a generated report."""
    id: str
    generated_date: datetime = Field(default_factory=datetime.now)
    period_start: datetime
    period_end: datetime
    title: str
    executive_summary: str
    sections: list[ReportSection] = Field(default_factory=list)
    notable_technologies: list[dict] = Field(default_factory=list)
    key_companies: list[dict] = Field(default_factory=list)
    key_countries: list[dict] = Field(default_factory=list)
    significance_analysis: dict = Field(default_factory=dict)
    file_path: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
