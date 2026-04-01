"""Centralized defaults configuration module.

This module contains all default values used across the application,
providing a single source of truth for configuration defaults.

Defaults are organized into the following categories:
- RSS feed sources and keywords
- LLM model configurations
- HTTP timeouts and retry settings
- File paths and logging defaults
"""

# =============================================================================
# RSS FEED DEFAULTS
# =============================================================================

# Default RSS sources for tech news
DEFAULT_RSS_SOURCES = [
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://arstechnica.com/feed/",
    "https://www.wired.com/feed/rss",
    "https://news.ycombinator.com/rss",
    "https://www.zdnet.com/news/rss/",
    "https://thenextweb.com/feed/",
]

# Default technology keywords for filtering
DEFAULT_TECH_KEYWORDS = [
    # AI/ML
    "AI", "artificial intelligence", "machine learning", "deep learning",
    "neural network", "LLM", "large language model", "transformer",
    "diffusion model", "generative AI", "computer vision", "NLP",
    "RAG", "agent", "multi-agent", "GPT", "ChatGPT", "Claude", "Gemini",
    "OpenAI", "Anthropic", "Hugging Face",
    
    # Quantum Computing
    "quantum computing", "quantum", "qubit", "quantum supremacy",
    "quantum error correction", "IBM Quantum", "Google Quantum",
    
    # Blockchain/Web3
    "blockchain", "cryptocurrency", "web3", "crypto", "NFT", "DeFi",
    "smart contract", "Bitcoin", "Ethereum", "Solana",
    
    # Robotics
    "robotics", "robot", "autonomous", "humanoid", "automation",
    "Boston Dynamics", "Tesla Optimus",
    
    # Cloud/Infrastructure
    "cloud computing", "edge computing", "serverless", "kubernetes",
    "microservices", "devops", "API", "AWS", "Azure", "Google Cloud",
    
    # Cybersecurity
    "cybersecurity", "zero trust", "encryption", "authentication",
    "security", "data breach", "hacking",
    
    # Telecommunications
    "5G", "6G", "telecommunications", "network", "Starlink",
    
    # IoT
    "IoT", "Internet of Things", "sensor", "connected devices",
    
    # AR/VR/MR
    "augmented reality", "virtual reality", "AR", "VR", "mixed reality",
    "metaverse", "Apple Vision Pro", "Meta Quest",
    
    # Biotech
    "biotech", "gene editing", "CRISPR", "synthetic biology",
    "biomedical", "mRNA",
    
    # Energy/Cleantech
    "battery technology", "renewable energy", "solar", "fusion",
    "hydrogen fuel", "carbon capture", "climate tech", "EV", "electric vehicle",
    
    # Semiconductors
    "semiconductor", "chip", "processor", "GPU", "NVIDIA", "AMD", "Intel",
    "TSMC", "ARM", "RISC-V",
    
    # Software Development
    "software development", "programming", "developer", "API",
    "open source", "GitHub", "GitLab",
    
    # Additional emerging technologies
    "natural language processing",
    "autonomous vehicle",
    "space technology",
    "satellite",
    "rocket",
    "3D printing",
    "additive manufacturing",
    "material science",
    "graphene",
    "superconductor",
    "brain-computer interface",
    "agritech",
    "food tech",
    "nanotechnology",
]

# =============================================================================
# LLM DEFAULTS
# =============================================================================

# Default models for each LLM provider
DEFAULT_LLM_MODELS = {
    "openrouter": "qwen/qwen3.5-27b",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-haiku-20240307",
}

# Fallback models for 40x errors (provider-specific defaults)
DEFAULT_FALLBACK_MODELS = {
    "openrouter": "anthropic/claude-3-haiku",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-haiku-20240307",
}

# Default LLM temperature
DEFAULT_LLM_TEMPERATURE = 0.7

# Component-specific model env var names
LLM_COMPONENT_MODEL_VARS = {
    "news_collector": "NEWS_COLLECTOR_LLM_MODEL",
    "report_generator": "REPORT_GENERATOR_LLM_MODEL",
    "entity_extractor": "ENTITY_EXTRACTOR_LLM_MODEL",
    "technology_analyzer": "TECHNOLOGY_ANALYZER_LLM_MODEL",
}

# LLMAnalyzer function-specific model env var names
LLM_FUNCTION_MODEL_VARS = {
    "executive_summary": "LLM_EXECUTIVE_SUMMARY_MODEL",
    "significance": "LLM_SIGNIFICANCE_MODEL",
    "extract_entities": "LLM_EXTRACT_ENTITIES_MODEL",
    "extract_entities_with_context": "LLM_EXTRACT_ENTITIES_MODEL",
    "extract_all_entities": "LLM_EXTRACT_ENTITIES_MODEL",
    "trend_analysis": "LLM_TREND_ANALYSIS_MODEL",
    "market_impact_summary": "LLM_MARKET_IMPACT_MODEL",
    "geographic_insights": "LLM_GEOGRAPHIC_INSIGHTS_MODEL",
    "article_relevance": "LLM_ARTICLE_RELEVANCE_MODEL",
    "complete_report": "LLM_COMPLETE_REPORT_MODEL",
}

# =============================================================================
# HTTP & NETWORK DEFAULTS
# =============================================================================

# Default HTTP timeout in seconds
DEFAULT_HTTP_TIMEOUT = 30

# Default user agent for HTTP requests
DEFAULT_USER_AGENT = "TechNews-MultiAgent/1.0"

# =============================================================================
# FILE PATH DEFAULTS
# =============================================================================

# Default failure log file path
DEFAULT_FAILURE_LOG_PATH = "./logs/rss_failures.log"

# Default database path
DEFAULT_DATABASE_PATH = "./data/tech_news.db"

# Default reports output directory
DEFAULT_REPORTS_DIR = "./reports"

# =============================================================================
# SCHEMA DEFAULTS
# =============================================================================

# Default sentiment score (neutral)
DEFAULT_SENTIMENT_SCORE = 0.0

# Default relevance score
DEFAULT_RELEVANCE_SCORE = 0.0

# Default confidence score
DEFAULT_CONFIDENCE_SCORE = 0.5

# Default hype level
DEFAULT_HYPE_LEVEL = 0.0

# Default significance score
DEFAULT_SIGNIFICANCE_SCORE = 0.5

# Default category for articles
DEFAULT_ARTICLE_CATEGORY = "General"

# Default category for technologies
DEFAULT_TECHNOLOGY_CATEGORY = "General Technology"

# Default trend direction
DEFAULT_TREND_DIRECTION = "stable"

# =============================================================================
# SENTIMENT ANALYSIS DEFAULTS
# =============================================================================

# Positive words for sentiment analysis
SENTIMENT_POSITIVE_WORDS = [
    "breakthrough",
    "innovative",
    "revolutionary",
    "promising",
    "exciting",
    "impressive",
    "advanced",
    "successful",
    "growth",
    "improve",
    "better",
    "faster",
    "efficient",
    "powerful",
    "leading",
    "cutting-edge",
    "game-changing",
    "transformative",
]

# Negative words for sentiment analysis
SENTIMENT_NEGATIVE_WORDS = [
    "failed",
    "failure",
    "concern",
    "risk",
    "threat",
    "problem",
    "issue",
    "challenge",
    "decline",
    "slow",
    "weak",
    "lagging",
    "controversial",
    "criticism",
    "lawsuit",
    "ban",
    "investigation",
]

# =============================================================================
# THEME KEYWORDS DEFAULTS
# =============================================================================

# Theme keywords for report generation
THEME_KEYWORDS = {
    "Artificial Intelligence": ["AI", "artificial intelligence", "machine learning", "deep learning", "neural network", "LLM", "GPT"],
    "Cloud Computing": ["cloud", "AWS", "Azure", "Google Cloud", "kubernetes", "serverless"],
    "Cybersecurity": ["security", "cyber", "hack", "breach", "encryption", "zero trust"],
    "Semiconductors": ["chip", "semiconductor", "processor", "GPU", "NVIDIA", "Intel", "AMD"],
    "Blockchain/Web3": ["blockchain", "crypto", "bitcoin", "ethereum", "web3", "NFT"],
    "Quantum Computing": ["quantum", "qubit", "quantum computing"],
    "Robotics": ["robot", "robotics", "autonomous", "drone"],
    "Biotechnology": ["biotech", "gene", "CRISPR", "genomic", "pharmaceutical"],
}

# =============================================================================
# TECHNOLOGY CATEGORIES DEFAULTS
# =============================================================================

# Technology categories with keywords
TECH_CATEGORIES = {
    "AI/ML": [
        "AI", "artificial intelligence", "machine learning", "deep learning",
        "neural network", "LLM", "large language model", "transformer",
        "diffusion model", "generative AI", "computer vision", "NLP",
        "RAG", "agent", "multi-agent", "GPT", "Claude", "Gemini"
    ],
    "Quantum Computing": [
        "quantum computing", "quantum", "qubit", "quantum supremacy"
    ],
    "Blockchain/Web3": [
        "blockchain", "cryptocurrency", "web3", "crypto", "NFT", "DeFi",
        "smart contract", "Bitcoin", "Ethereum"
    ],
    "Robotics": [
        "robotics", "robot", "autonomous", "humanoid", "automation"
    ],
    "Cloud/Infrastructure": [
        "cloud computing", "edge computing", "serverless", "kubernetes",
        "microservices", "devops", "API", "AWS", "Azure", "Google Cloud"
    ],
    "Cybersecurity": [
        "cybersecurity", "zero trust", "encryption", "authentication",
        "security", "hacking", "vulnerability"
    ],
    "Telecommunications": [
        "5G", "6G", "telecommunications", "network"
    ],
    "IoT": [
        "IoT", "Internet of Things", "sensor", "connected"
    ],
    "AR/VR/MR": [
        "augmented reality", "virtual reality", "AR", "VR",
        "mixed reality", "metaverse", "XR"
    ],
    "Biotech": [
        "biotech", "gene editing", "CRISPR", "synthetic biology", "biomedical"
    ],
    "Energy/Cleantech": [
        "battery technology", "renewable energy", "solar", "fusion",
        "hydrogen fuel", "carbon capture", "climate tech", "electric vehicle", "EV"
    ],
    "Semiconductors": [
        "semiconductor", "chip", "processor", "GPU", "TPU", "neuromorphic"
    ],
    "Hardware/Interfaces": [
        "brain-computer interface", "wearable", "hardware"
    ],
    "Space Tech": [
        "space technology", "satellite", "rocket", "spaceX"
    ],
    "Manufacturing": [
        "3D printing", "additive manufacturing", "nanotechnology"
    ],
    "Materials": [
        "material science", "graphene", "superconductor"
    ],
}

# =============================================================================
# ENTITY EXTRACTION DEFAULTS
# =============================================================================

# Known tech companies with country mapping
TECH_COMPANIES = {
    # USA
    "OpenAI": "USA",
    "Google": "USA",
    "Microsoft": "USA",
    "Apple": "USA",
    "Meta": "USA",
    "Facebook": "USA",
    "Amazon": "USA",
    "NVIDIA": "USA",
    "Tesla": "USA",
    "Anthropic": "USA",
    "Intel": "USA",
    "AMD": "USA",
    "IBM": "USA",
    "Oracle": "USA",
    "Salesforce": "USA",
    "Adobe": "USA",
    "Cisco": "USA",
    "Qualcomm": "USA",
    "Broadcom": "USA",
    "Texas Instruments": "USA",
    "Palantir": "USA",
    "Snowflake": "USA",
    "Databricks": "USA",
    "Stripe": "USA",
    "SpaceX": "USA",
    "Uber": "USA",
    "Lyft": "USA",
    "Airbnb": "USA",
    "Netflix": "USA",
    "Spotify": "Sweden",
    # UK
    "DeepMind": "UK",
    "ARM": "UK",
    "Graphcore": "UK",
    "Wayve": "UK",
    # China
    "Huawei": "China",
    "Alibaba": "China",
    "Tencent": "China",
    "Baidu": "China",
    "ByteDance": "China",
    "Xiaomi": "China",
    "DJ": "China",
    "OPPO": "China",
    "Vivo": "China",
    "Lenovo": "China",
    "SMIC": "China",
    "DiDi": "China",
    "JD.com": "China",
    "PDD": "China",
    # South Korea
    "Samsung": "South Korea",
    "LG": "South Korea",
    "SK Hynix": "South Korea",
    "Kakao": "South Korea",
    "Naver": "South Korea",
    # Japan
    "Sony": "Japan",
    "Toyota": "Japan",
    "SoftBank": "Japan",
    "Nintendo": "Japan",
    "Panasonic": "Japan",
    "Hitachi": "Japan",
    "Fujitsu": "Japan",
    "NEC": "Japan",
    "Renesas": "Japan",
    "NTT": "Japan",
    # Taiwan
    "TSMC": "Taiwan",
    "Foxconn": "Taiwan",
    "MediaTek": "Taiwan",
    # Netherlands
    "ASML": "Netherlands",
    "NXP": "Netherlands",
    # Germany
    "SAP": "Germany",
    "Siemens": "Germany",
    "Bosch": "Germany",
    "Infineon": "Germany",
    # France
    "Thales": "France",
    "Dassault": "France",
    "STMicroelectronics": "France/Switzerland",
    # Israel
    "Mobileye": "Israel",
    "Wiz": "Israel",
    # India
    "TCS": "India",
    "Infosys": "India",
    "Wipro": "India",
    # Canada
    "Shopify": "Canada",
    "Element AI": "Canada",
    # Singapore
    "Grab": "Singapore",
    "Sea": "Singapore",
}

# Country names and their ISO codes
COUNTRIES = {
    "USA": ("United States", "US", "USA", "America", "American", "U.S.", "U.S.A."),
    "UK": ("United Kingdom", "UK", "Britain", "British", "England", "English", "U.K."),
    "China": ("China", "Chinese", "PRC", "P.R.C."),
    "Japan": ("Japan", "Japanese"),
    "South Korea": ("South Korea", "Korea", "Korean", "Republic of Korea", "ROK"),
    "Germany": ("Germany", "German", "Deutschland"),
    "France": ("France", "French"),
    "India": ("India", "Indian"),
    "Israel": ("Israel", "Israeli"),
    "Taiwan": ("Taiwan", "Taiwanese"),
    "Netherlands": ("Netherlands", "Dutch", "Holland"),
    "Singapore": ("Singapore", "Singaporean"),
    "Canada": ("Canada", "Canadian"),
    "Australia": ("Australia", "Australian"),
    "Sweden": ("Sweden", "Swedish"),
    "Switzerland": ("Switzerland", "Swiss"),
    "South Africa": ("South Africa", "South African"),
    "Brazil": ("Brazil", "Brazilian"),
    "Russia": ("Russia", "Russian"),
    "Italy": ("Italy", "Italian"),
    "Spain": ("Spain", "Spanish"),
    "Mexico": ("Mexico", "Mexican"),
    "Indonesia": ("Indonesia", "Indonesian"),
    "Vietnam": ("Vietnam", "Vietnamese"),
    "Thailand": ("Thailand", "Thai"),
    "Malaysia": ("Malaysia", "Malaysian"),
    "Philippines": ("Philippines", "Filipino"),
    "UAE": ("UAE", "United Arab Emirates", "Dubai", "Abu Dhabi"),
    "Saudi Arabia": ("Saudi Arabia", "Saudi", "Saudi Arabian"),
}

# Technology name normalizations
TECH_NAME_NORMALIZATIONS = {
    "ai": "AI",
    "ml": "ML",
    "llm": "LLM",
    "nlp": "NLP",
    "rag": "RAG",
    "ar": "AR",
    "vr": "VR",
    "xr": "XR",
    "iot": "IoT",
    "ev": "EV",
    "gpu": "GPU",
    "tpu": "TPU",
    "5g": "5G",
    "6g": "6G",
    "nft": "NFT",
    "defi": "DeFi",
    "web3": "Web3",
    "crispr": "CRISPR",
}
