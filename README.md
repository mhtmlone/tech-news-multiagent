# Tech News Multi-Agent Analysis System

A sophisticated multi-agent system for analyzing tech news, identifying emerging technologies, and tracking their development over time with long-term memory capabilities.

## Features

- **Multi-Agent Architecture**: Four specialized agents working together:
  - **NewsCollectorAgent**: Fetches and filters technology news from multiple sources
  - **TechnologyAnalyzerAgent**: Identifies and categorizes new technologies
  - **MemoryManagerAgent**: Stores and retrieves technology information using vector embeddings
  - **DevelopmentTrackerAgent**: Monitors technology trajectories and identifies promising developments

- **Long-Term Memory**: Vector-based storage using ChromaDB for:
  - Technology information and metadata
  - Development history and timelines
  - News mentions and sentiment tracking
  - Similar technology matching

- **Intelligent Analysis**:
  - Automatic technology categorization (16+ categories)
  - Sentiment analysis of news coverage
  - Trend detection and trajectory analysis
  - Hype level calculation
  - Promising technology identification

## Installation

```bash
# Clone the repository
cd multiagents

# Install dependencies
pip install -e .

# For development
pip install -e ".[dev]"
```

## Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Add your API keys if using LLM-based features (optional for basic functionality)

## Usage

### Run Complete Analysis

```bash
# Using the CLI
tech-analyzer analyze --days 7 --verbose

# Or run directly
python -m src.main
```

### Search Technologies

```bash
# Search for specific technologies
tech-analyzer search "artificial intelligence" --limit 10

# Get detailed information
tech-analyzer details "Generative AI"

# List all tracked technologies
tech-analyzer list

# Filter by category
tech-analyzer list --category "AI/ML"
```

### Generate Reports

```bash
# Summary report
tech-analyzer summary

# Track specific technology development
tech-analyzer track "Quantum Computing"
```

### Programmatic Usage

```python
import asyncio
from src.main import TechNewsMultiAgentSystem

async def main():
    system = TechNewsMultiAgentSystem()
    
    # Run analysis
    results = await system.run_analysis(max_age_days=7)
    
    # Display results
    system.display_results(results)
    
    # Search technologies
    techs = await system.search_technologies("machine learning", limit=5)
    
    # Get details
    details = await system.get_technology_details("Neural Networks")
    
    # Generate summary
    report = await system.generate_summary_report()
    print(report)

asyncio.run(main())
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                 TechNews Multi-Agent System              │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐  ┌────────────────┐  ┌──────────────┐
│   News        │  │  Technology    │  │   Memory     │
│  Collector    │──▶│   Analyzer    │──▶│  Manager     │
│   Agent       │  │    Agent       │  │    Agent     │
└───────────────┘  └────────────────┘  └──────────────┘
                          │                   │
                          ▼                   ▼
                   ┌────────────────┐  ┌──────────────┐
                   │  Development   │  │  Vector DB   │
                   │    Tracker     │◀─│  (ChromaDB)  │
                   │    Agent       │  │              │
                   └────────────────┘  └──────────────┘
```

## Agent Descriptions

### NewsCollectorAgent
- Fetches RSS feeds from major tech news sources
- Filters articles based on technology keywords
- Calculates relevance and sentiment scores
- Sources include: TechCrunch, The Verge, Ars Technica, Wired, Hacker News, etc.

### TechnologyAnalyzerAgent
- Extracts technology names from news articles
- Categorizes technologies into 16+ categories
- Identifies new vs. existing technologies
- Calculates confidence scores and hype levels
- Determines trend direction (rising/stable/declining)

### MemoryManagerAgent
- Stores technologies in vector database
- Tracks development history
- Enables semantic search
- Finds similar technologies
- Maintains mention history

### DevelopmentTrackerAgent
- Analyzes technology trajectories
- Detects significant developments
- Recommends status changes
- Generates development reports
- Identifies promising technologies

## Technology Categories

- AI/ML
- Quantum Computing
- Blockchain/Web3
- Robotics
- Cloud/Infrastructure
- Cybersecurity
- Telecommunications
- IoT
- AR/VR/MR
- Biotech
- Energy/Cleantech
- Semiconductors
- Hardware/Interfaces
- Space Tech
- Manufacturing
- Materials

## Data Storage

All technology data is stored locally in ChromaDB:
- `memory_db/technologies`: Technology metadata
- `memory_db/developments`: Development timeline
- `memory_db/news_mentions`: News article references

## CLI Commands

```
tech-analyzer --help
tech-analyzer analyze --days 7
tech-analyzer search "query"
tech-analyzer details "Tech Name"
tech-analyzer summary
tech-analyzer track "Tech Name"
tech-analyzer list --category "AI/ML"
```

## Development

```bash
# Run tests
pytest

# Format code
black src/

# Lint
ruff check src/
```

## Article Content Extraction

The `NewsCollectorAgent` uses a multi-strategy approach to extract full article content:

1. **Standard HTTP** — aiohttp with trafilatura, newspaper3k, readability-lxml, and BeautifulSoup fallbacks
2. **Playwright headless browser** — Used as a fallback for sites protected by JavaScript challenges (e.g., **AWS WAF Bot Control** used by Ars Technica). The headless Chromium browser executes the WAF challenge JavaScript, obtains the required cookies, and then loads the actual page.

### Known Limitations (KIV)

The following sites use **DataDome** bot protection, which performs behavioral analysis and blocks all automated access including headless browsers. Content extraction from these sites is **not currently possible** without a paid DataDome bypass service or manual intervention:

| Site | Protection | Status |
|------|-----------|--------|
| reuters.com | DataDome (HTTP 401, `x-datadome` header) | ❌ KIV — cannot bypass |
| wsj.com | DataDome (HTTP 401, `x-datadome` header) | ❌ KIV — cannot bypass |

Articles from these sources will fall back to using the RSS feed summary only (no full article content).

## Requirements

- Python 3.10+
- ChromaDB
- Pydantic
- Rich (for CLI output)
- aiohttp
- BeautifulSoup4
- feedparser
- playwright (for AWS WAF bypass)

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
