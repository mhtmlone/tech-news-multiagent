# Tech News Multi-Agent System - Software Flow Documentation

## System Overview

The Tech News Multi-Agent System is an AI-powered technology tracking and analysis platform that collects news from RSS feeds, identifies emerging technologies, and generates comprehensive analysis reports. The system uses a **multi-agent architecture** with specialized agents working in a 5-step pipeline.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Data Sources                                  │
│                    RSS Feeds (7+ sources)                          │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    1. NewsCollectorAgent                           │
│  • Fetch RSS feeds (fetch_all_feeds)                               │
│  • Filter duplicates (filter_new_entries)                          │
│  • Analyze relevance (analyze_article_relevance)                   │
│  • Extract content (fetch_article_content)                        │
│  • Extract entities (extract_all_unified)                           │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
            ┌───────────────┐          ┌───────────────┐
            │  SQLite Store │          │ Technology    │
            │ (all articles)│          │ Mentions      │
            └───────────────┘          └───────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 2. TechnologyAnalyzerAgent                         │
│  • Identify new technologies (identify_new_technologies)          │
│  • Analyze existing technologies (analyze_existing_technologies)  │
│  • Calculate promising scores (identify_promising_technologies)   │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    3. MemoryManagerAgent                            │
│  • Store new technologies (store_new_technologies)               │
│  • Update existing technologies (update_existing_technologies)     │
│  • Add developments and mentions to vector store                   │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
            ┌───────────────┐          ┌───────────────┐
            │ Vector Memory │          │ SQLite Store  │
            │ (ChromaDB)    │          │ (metadata)    │
            └───────────────┘          └───────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 4. DevelopmentTrackerAgent                        │
│  • Analyze trajectory (analyze_technology_trajectory)             │
│  • Detect developments (detect_significant_developments)          │
│  • Recommend status changes (recommend_status_change)             │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  5. ReportGeneratorAgent                           │
│  • Gather data from SQLite                                         │
│  • Generate LLM content (single optimized call)                    │
│  • Build report sections                                           │
│  • Save report to file + store metadata                           │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Output                                      │
│              GeneratedReport + Markdown File                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Main Pipeline Flow

### Step 1: News Collection ([NewsCollectorAgent](src/agents/news_collector.py:28))

**Location**: `src/agents/news_collector.py`

**Process:**
1. **Fetch RSS feeds** - [`fetch_all_feeds()`](src/agents/news_collector.py:157)
   - Fetches from 7+ RSS sources (TechCrunch, The Verge, Ars Technica, Wired, Hacker News, ZDNet, The Next Web)
   - Uses aiohttp for async HTTP requests
   
2. **Filter duplicates** - [`filter_new_entries()`](src/agents/news_collector.py:177)
   - Batch checks URLs against SQLite database
   - Skips already-collected articles
   
3. **Analyze relevance** - [`analyze_article_relevance()`](src/agents/news_collector.py:247)
   - **LLM mode**: Uses LLM to classify if article is tech-related (if LLM enabled)
   - **Fallback mode**: Keyword-based matching with ~90 tech keywords
   
4. **Analyze sentiment** - [`analyze_sentiment()`](src/agents/news_collector.py:314)
   - Uses positive/negative word lists
   - Returns score from -1.0 to 1.0
   
5. **Fetch full article content** - [`fetch_article_content()`](src/agents/news_collector.py:95)
   - Multiple fallback strategies in order:
     1. Trafilatura (best for news)
     2. Newspaper3k
     3. Readability-lxml
     4. BeautifulSoup
     5. Playwright (headless browser for JS-protected sites)
   
6. **Extract entities** - [`extract_all_unified()`](src/utils/entity_extractor.py)
   - Extracts: Technologies, Companies, Countries
   - Uses LLM if available, regex fallback
   
7. **Store in SQLite** - All articles stored (for deduplication)
   - Only tech-related articles (relevance >= 0.1) become TechnologyMentions

**Output**: List of [TechnologyMention](src/models/schemas.py:14) objects

---

### Step 2: Technology Analysis ([TechnologyAnalyzerAgent](src/agents/technology_analyzer.py:15))

**Location**: `src/agents/technology_analyzer.py`

**Process:**
1. **Identify new technologies** - [`identify_new_technologies()`](src/agents/technology_analyzer.py:94)
   - Requires 2+ mentions of same technology
   - Must not exist in current tracked technologies
   - Categories: AI/ML, Quantum, Blockchain, Robotics, Cloud, Cybersecurity, IoT, AR/VR, Biotech, Energy, Semiconductors, etc.
   
2. **Analyze existing technologies** - [`analyze_existing_technologies()`](src/agents/technology_analyzer.py:157)
   - Updates existing tech with new mentions
   - Updates key_developments list
   - Recalculates sentiment, trend, hype level
   
3. **Calculate promising score** - [`identify_promising_technologies()`](src/agents/technology_analyzer.py:205)
   - Factors: confidence_score (0.2), hype_level (0.15), status (0.2), trend (0.15), recency (0.15), sentiment (0.15)
   - Threshold: >= 0.7 = promising

**Output**: 
- New [Technology](src/models/schemas.py:24) objects
- Updated Technology objects
- Promising Technology list

---

### Step 3: Memory Storage ([MemoryManagerAgent](src/agents/memory_manager.py:11))

**Location**: `src/agents/memory_manager.py`

**Process:**
1. **Store new technologies** - [`store_new_technologies()`](src/agents/memory_manager.py:74)
   - Stores in Vector Memory (ChromaDB)
   - Adds key_developments
   - Stores news mentions
   
2. **Update existing technologies** - [`update_existing_technologies()`](src/agents/memory_manager.py:104)
   - Updates metadata in vector store
   - Adds new developments

3. **Retrieve history** - [`retrieve_technology_history()`](src/agents/memory_manager.py:128)
   - Gets full technology history
   - Gets developments timeline
   - Finds similar technologies

**Storage**: Vector Memory (ChromaDB) + SQLite metadata

---

### Step 4: Development Tracking ([DevelopmentTrackerAgent](src/agents/development_tracker.py:10))

**Location**: `src/agents/development_tracker.py`

**Process:**
1. **Analyze trajectory** - [`analyze_technology_trajectory()`](src/agents/development_tracker.py:58)
   - Calculates mention timeline by week
   - Determines trajectory: accelerating / decelerating / stable
   - Analyzes sentiment trend: positive / negative / neutral

2. **Detect significant developments** - [`detect_significant_developments()`](src/agents/development_tracker.py:142)
   - Coverage surge: 5+ high-relevance articles in last 7 days
   - Positive sentiment surge: 3+ positive articles in last 7 days
   - Development cluster: 3+ developments on same date

3. **Recommend status changes** - [`recommend_status_change()`](src/agents/development_tracker.py:211)
   - Status lifecycle: EMERGING → GROWING → MATURE → DECLINING
   - Thresholds:
     - emerging_to_growing: 10 mentions in 7 days
     - growing_to_mature: 50 mentions in 30 days
     - mature_to_declining: 5 mentions in 30 days

**Output**: Development reports + promising technologies list

---

### Step 5: Report Generation ([ReportGeneratorAgent](src/agents/report_generator.py:17))

**Location**: `src/agents/report_generator.py`

**Process:**
1. **Gather data from SQLite**
   - Articles by date range
   - Top companies (by mention count)
   - Top countries (by mention count)

2. **Generate LLM content** - [`_generate_report_with_single_llm_call()`](src/agents/report_generator.py:158)
   - **Single optimized LLM call** generates all sections:
     - Executive summary
     - Technology trends
     - Geographic insights
     - Significance analysis
   - Reduces LLM calls from ~9 to 1
   - Falls back to template if LLM fails

3. **Build report sections** - [`_build_sections_from_llm_data()`](src/agents/report_generator.py:190)
   - Technology Trends
   - Key Developments
   - Companies in Focus
   - Geographic Insights
   - Significance Analysis

4. **Save report**
   - Markdown file in `./reports/` directory
   - Metadata stored in SQLite

**Output**: [GeneratedReport](src/models/schemas.py:169) object + markdown file

---

## Data Storage

### SQLite Store ([src/storage/sqlite_store.py](src/storage/sqlite_store.py:11))

**Database**: `./data/news_content.db`

**Tables:**
| Table | Purpose |
|-------|---------|
| `news_articles` | All collected articles with content, sentiment, relevance |
| `companies` | Company entities with country mapping |
| `countries` | Country mentions from articles |
| `technologies` | Technology entities extracted from articles |
| `article_companies` | Junction: article-company relationships |
| `article_countries` | Junction: article-country relationships |
| `article_technologies` | Junction: article-technology relationships |
| `reports` | Generated report metadata |

### Vector Memory ([src/memory/vector_store.py](src/memory/vector_store.py:12))

**Storage**: `./memory_db/` (ChromaDB PersistentClient)

**Collections:**
| Collection | Purpose |
|------------|---------|
| `technologies` | Technology metadata, status, developments |
| `developments` | Development timeline entries |
| `news_mentions` | News article embeddings for semantic search |

---

## Agent Communication

### Orchestration

The [AgentOrchestrator](src/agents/base.py:57) manages agent communication:

1. **Pipeline execution** - [`run_pipeline()`](src/agents/base.py:89)
   - Sequential execution of agents
   - Passes output of one agent as input to next
   
2. **Message passing** - [AgentMessage](src/models/schemas.py:54)
   ```python
   AgentMessage(
       sender="NewsCollectorAgent",
       recipient="TechnologyAnalyzerAgent", 
       message_type="technology_analysis",
       content={...}
   )
   ```

3. **Broadcast/Routing** - [`broadcast_message()`](src/agents/base.py:75), [`route_message()`](src/agents/base.py:82)

### Inter-Agent Messages

| From | To | Message Type | Content |
|------|-----|--------------|---------|
| TechnologyAnalyzerAgent | MemoryManagerAgent | technology_analysis | New/updated technologies |
| MemoryManagerAgent | DevelopmentTrackerAgent | memory_update | Stored technology IDs |
| DevelopmentTrackerAgent | ReportGeneratorAgent | development_tracking | Tracking results |
| ReportGeneratorAgent | MemoryManagerAgent | report_generated | Report metadata |

---

## Configuration

### Configuration Sources (in order of priority)

1. **`.env` file** - Environment variables
   - LLM API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, OPENROUTER_API_KEY)
   - Database paths
   - Feature flags

2. **[src/config/defaults.py](src/config/defaults.py)** - Default values
   - RSS sources (~7 default feeds)
   - Tech keywords (~90 keywords across 15+ categories)
   - Sentiment words (positive/negative)
   - Technology categories
   - Company-country mappings

3. **[src/config/rss_config.py](src/config/rss_config.py)** - RSS configuration
   - Feed URLs
   - Keywords for filtering
   - Timeout settings

4. **[src/config/llm_config.py](src/config/llm_config.py)** - LLM settings
   - Provider selection (openrouter/openai/anthropic)
   - Model per component
   - Temperature, max tokens

5. **[config/rss_sources.json](config/rss_sources.json)** - Custom RSS sources

---

## Key Data Models

### TechnologyMention
```python
class TechnologyMention(BaseModel):
    source: str           # News source name
    url: str             # Article URL
    title: str           # Article title
    published_date: datetime
    summary: str         # Article summary/content
    sentiment_score: float   # -1.0 to 1.0
    relevance_score: float  # 0.0 to 1.0
```

### Technology
```python
class Technology(BaseModel):
    id: str
    name: str
    description: str
    category: str                    # e.g., "AI/ML", "Quantum"
    status: TechnologyStatus         # EMERGING, GROWING, MATURE, DECLINING
    first_seen: datetime
    last_updated: datetime
    mentions: list[TechnologyMention]
    related_technologies: list[str]
    key_developments: list[str]
    confidence_score: float          # 0.0 to 1.0
    trend_direction: str             # "rising", "stable", "declining", "emerging"
    hype_level: float                # 0.0 to 1.0
```

### GeneratedReport
```python
class GeneratedReport(BaseModel):
    id: str
    generated_date: datetime
    period_start: datetime
    period_end: datetime
    title: str
    executive_summary: str
    sections: list[ReportSection]
    notable_technologies: list[dict]
    key_companies: list[dict]
    key_countries: list[dict]
    significance_analysis: dict
    file_path: str                   # Path to markdown file
```

---

## Technology Status Lifecycle

```
    ┌──────────────────────────────────────────┐
    │                                          │
    ▼                                          │
EMERGING ──(10+ mentions, 7 days)──▶ GROWING ──(50+ mentions, 30 days)──▶ MATURE
  │                                              │                                   │
  │◀─────────────────────────────────────────────┴────────────(5 mentions, 30 days)─┘
  │                                                                                  │
  └─────────────────────(10+ mentions)──────────────────────────────────────────────▶ DECLINING
```

**Automatic Status Transitions:**
- **EMERGING → GROWING**: 10+ mentions in 7 days
- **GROWING → MATURE**: 50+ mentions in 30 days  
- **MATURE → DECLINING**: 5 or fewer mentions in 30 days
- **DECLINING → MATURE**: 10+ mentions (recovery)

---

## Execution Flow Diagram

```
                              ┌─────────────────────┐
                              │   main.py: async    │
                              │   main()           │
                              └──────────┬──────────┘
                                         │
                                         ▼
                              ┌─────────────────────┐
                              │ TechNewsMultiAgent │
                              │ System.__init__()  │
                              │ - VectorMemory      │
                              │ - SQLiteStore       │
                              │ - 5 Agents          │
                              │ - Orchestrator      │
                              └──────────┬──────────┘
                                         │
                                         ▼
                              ┌─────────────────────┐
                              │ run_analysis()      │
                              │ max_age_days=7      │
                              └──────────┬──────────┘
                                         │
         ┌───────────────────────────────┼───────────────────────────────┐
         │                               │                               │
         ▼                               ▼                               ▼
┌─────────────────┐          ┌─────────────────┐          ┌─────────────────┐
│ Step 1: Collect │          │ Step 2: Analyze │          │ Step 3: Store   │
│ NewsCollector   │          │ Technology      │          │ MemoryManager   │
│ Agent           │          │ AnalyzerAgent   │          │ Agent           │
└────────┬────────┘          └────────┬────────┘          └────────┬────────┘
         │                            │                            │
         │                            │                            │
         ▼                            │                            │
┌─────────────────┐                   │                            │
│ - fetch feeds  │                   │                            │
│ - filter dupes │                   │                            │
│ - analyze      │───────────────────┘                            │
│ - extract      │                                                │
│ - store SQLite │                                                │
└────────┬────────┘                                                │
         │                                                         │
         ▼                                                         │
┌─────────────────┐                                                │
│ Output:         │                                                │
│ Technology     │────────────────────────────────────────────────┘
│ Mention[]      │                                                
└─────────────────┘                                                
                                                                  
         ┌───────────────────────────────┬───────────────────────────────┐
         │                               │                               │
         ▼                               ▼                               ▼
┌─────────────────┐          ┌─────────────────┐          ┌─────────────────┐
│ Step 4: Track   │          │ Step 5: Report   │          │ Return Results │
│ Development     │          │ GeneratorAgent  │          │ to Caller      │
│ TrackerAgent    │          │                 │          │                │
└────────┬────────┘          └────────┬────────┘          └─────────────────┘
         │                            │
         │                            ▼
         │                   ┌─────────────────┐
         │                   │ - gather data   │
         │                   │ - LLM generate  │
         │                   │ - build sections│
         │                   │ - save file     │
         │                   └────────┬────────┘
         │                            │
         ▼                            ▼
┌─────────────────┐          ┌─────────────────┐
│ Output:        │          │ Output:         │
│ - trajectory   │          │ - GeneratedRepo ││
│ - promising    │          │ - file_path    │
│ - status       │          └─────────────────┘
│   changes      │
└─────────────────┘
```

---

## Summary

This multi-agent system provides an end-to-end pipeline for technology intelligence:

1. **Collect** - Fetches and filters RSS news, extracts content and entities
2. **Analyze** - Identifies new technologies, tracks existing ones, scores promising technologies  
3. **Store** - Persists technologies and developments in vector + relational storage
4. **Track** - Monitors trajectory, detects significant developments, recommends status changes
5. **Report** - Generates comprehensive markdown analysis reports with LLM enhancement

The system is designed for extensibility with modular agents, configurable LLM integration, and dual storage (SQLite + Vector) for different use cases.
