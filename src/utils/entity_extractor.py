"""Entity extraction utilities for companies and countries."""

import re
from typing import Optional


class EntityExtractor:
    """Extract companies and countries from text."""
    
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
    
    # Build reverse lookup for countries
    COUNTRY_LOOKUP = {}
    for code, names in COUNTRIES.items():
        for name in names:
            COUNTRY_LOOKUP[name.lower()] = code
    
    def __init__(self, use_llm: bool = False, llm_analyzer=None):
        """Initialize the entity extractor.
        
        Args:
            use_llm: Whether to use LLM for enhanced extraction.
            llm_analyzer: LLMAnalyzer instance for enhanced extraction.
        """
        self.use_llm = use_llm
        self.llm_analyzer = llm_analyzer
        
        # Build regex patterns for companies
        company_names = list(self.TECH_COMPANIES.keys())
        self.company_pattern = re.compile(
            r"\b(" + "|".join(re.escape(name) for name in company_names) + r")\b",
            re.IGNORECASE
        )
        
        # Build regex patterns for countries
        country_names = list(self.COUNTRY_LOOKUP.keys())
        self.country_pattern = re.compile(
            r"\b(" + "|".join(re.escape(name) for name in country_names) + r")\b",
            re.IGNORECASE
        )
    
    def extract_companies(self, text: str) -> list[dict]:
        """Extract company mentions from text.
        
        Args:
            text: Text to extract companies from.
            
        Returns:
            List of company dictionaries with name and country.
        """
        companies = []
        seen = set()
        
        matches = self.company_pattern.findall(text)
        for match in matches:
            # Find the original case version
            company_name = None
            for name in self.TECH_COMPANIES.keys():
                if name.lower() == match.lower():
                    company_name = name
                    break
            
            if company_name and company_name.lower() not in seen:
                seen.add(company_name.lower())
                companies.append({
                    "name": company_name,
                    "country": self.TECH_COMPANIES[company_name],
                    "context": self._extract_context(text, match)
                })
        
        return companies
    
    def extract_countries(self, text: str) -> list[dict]:
        """Extract country mentions from text.
        
        Args:
            text: Text to extract countries from.
            
        Returns:
            List of country dictionaries with name and code.
        """
        countries = []
        seen = set()
        
        matches = self.country_pattern.findall(text)
        for match in matches:
            country_code = self.COUNTRY_LOOKUP.get(match.lower())
            
            if country_code and country_code not in seen:
                seen.add(country_code)
                # Get the primary name for the country
                primary_name = self.COUNTRIES[country_code][0]
                countries.append({
                    "name": primary_name,
                    "code": country_code,
                    "context": self._extract_context(text, match)
                })
        
        return countries
    
    def _extract_context(self, text: str, entity: str, context_length: int = 100) -> str:
        """Extract context around an entity mention.
        
        Args:
            text: Full text.
            entity: Entity to find context for.
            context_length: Number of characters before and after.
            
        Returns:
            Context string.
        """
        try:
            idx = text.lower().find(entity.lower())
            if idx == -1:
                return ""
            
            start = max(0, idx - context_length)
            end = min(len(text), idx + len(entity) + context_length)
            
            context = text[start:end]
            if start > 0:
                context = "..." + context
            if end < len(text):
                context = context + "..."
            
            return context.strip()
        except Exception:
            return ""
    
    def extract_all(self, text: str) -> dict:
        """Extract all entities from text.
        
        Args:
            text: Text to extract entities from.
            
        Returns:
            Dictionary with companies and countries lists.
        """
        return {
            "companies": self.extract_companies(text),
            "countries": self.extract_countries(text)
        }
    
    async def extract_all_with_llm(self, text: str) -> dict:
        """Extract entities using both pattern matching and LLM.
        
        Args:
            text: Text to extract entities from.
            
        Returns:
            Dictionary with companies and countries lists.
        """
        # First do pattern-based extraction
        pattern_results = self.extract_all(text)
        
        # If LLM is enabled, enhance with LLM extraction
        if self.use_llm and self.llm_analyzer:
            try:
                llm_results = await self.llm_analyzer.extract_entities_with_context(text)
                
                # Merge results, preferring LLM for context
                seen_companies = {c["name"].lower() for c in pattern_results["companies"]}
                seen_countries = {c["name"].lower() for c in pattern_results["countries"]}
                
                # Add LLM-found companies not in pattern results
                for company in llm_results.get("companies", []):
                    name = company.get("name", "")
                    if name.lower() not in seen_companies:
                        # Try to get country from our known companies
                        country = self.TECH_COMPANIES.get(name)
                        if country:
                            company["country"] = country
                        pattern_results["companies"].append(company)
                        seen_companies.add(name.lower())
                
                # Add LLM-found countries not in pattern results
                for country in llm_results.get("countries", []):
                    name = country.get("name", "")
                    if name.lower() not in seen_countries:
                        # Try to get code from our known countries
                        code = self.COUNTRY_LOOKUP.get(name.lower())
                        if code:
                            country["code"] = code
                        pattern_results["countries"].append(country)
                        seen_countries.add(name.lower())
                        
            except Exception as e:
                print(f"LLM extraction failed: {e}")
        
        return pattern_results
    
    def get_company_country(self, company_name: str) -> Optional[str]:
        """Get the country for a known company.
        
        Args:
            company_name: Name of the company.
            
        Returns:
            Country name or None if not found.
        """
        return self.TECH_COMPANIES.get(company_name)
    
    def is_known_company(self, name: str) -> bool:
        """Check if a name is a known company.
        
        Args:
            name: Name to check.
            
        Returns:
            True if known company, False otherwise.
        """
        return name in self.TECH_COMPANIES or name.lower() in {
            k.lower() for k in self.TECH_COMPANIES
        }
    
    def get_companies_by_country(self, country: str) -> list[str]:
        """Get all known companies for a country.
        
        Args:
            country: Country name or code.
            
        Returns:
            List of company names.
        """
        # Normalize country name
        country_code = self.COUNTRY_LOOKUP.get(country.lower(), country)
        
        return [
            name for name, c in self.TECH_COMPANIES.items()
            if c == country_code or c == country
        ]
