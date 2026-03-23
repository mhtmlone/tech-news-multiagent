"""SQLite storage module for news content persistence."""

import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional


class SQLiteStore:
    """SQLite-based storage for news articles and related data."""
    
    def __init__(self, db_path: str = "./data/news_content.db"):
        """Initialize SQLite storage.
        
        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_database(self):
        """Initialize database tables."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # News articles table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS news_articles (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                source TEXT NOT NULL,
                author TEXT,
                published_date DATETIME,
                collected_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                summary TEXT,
                content TEXT,
                sentiment_score REAL,
                relevance_score REAL,
                is_tech_related BOOLEAN DEFAULT TRUE,
                category TEXT,
                keywords TEXT,
                processed BOOLEAN DEFAULT FALSE
            )
        """)
        
        # Create indexes for news_articles
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_news_published 
            ON news_articles(published_date)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_news_source 
            ON news_articles(source)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_news_category 
            ON news_articles(category)
        """)
        
        # Companies table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                country TEXT,
                industry TEXT,
                first_mentioned DATETIME,
                last_mentioned DATETIME,
                mention_count INTEGER DEFAULT 1
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_companies_country 
            ON companies(country)
        """)
        
        # Countries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS countries (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                code TEXT,
                mention_count INTEGER DEFAULT 1,
                last_mentioned DATETIME
            )
        """)
        
        # Technologies table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS technologies (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                category TEXT,
                first_mentioned DATETIME,
                last_mentioned DATETIME,
                mention_count INTEGER DEFAULT 1
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_technologies_category
            ON technologies(category)
        """)
        
        # Article-Company junction table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS article_companies (
                article_id TEXT,
                company_id TEXT,
                relevance REAL,
                context TEXT,
                PRIMARY KEY (article_id, company_id),
                FOREIGN KEY (article_id) REFERENCES news_articles(id),
                FOREIGN KEY (company_id) REFERENCES companies(id)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_article_companies_company
            ON article_companies(company_id)
        """)
        
        # Article-Country junction table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS article_countries (
                article_id TEXT,
                country_id TEXT,
                relevance REAL,
                context TEXT,
                PRIMARY KEY (article_id, country_id),
                FOREIGN KEY (article_id) REFERENCES news_articles(id),
                FOREIGN KEY (country_id) REFERENCES countries(id)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_article_countries_country
            ON article_countries(country_id)
        """)
        
        # Article-Technology junction table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS article_technologies (
                article_id TEXT,
                technology_id TEXT,
                relevance REAL,
                context TEXT,
                PRIMARY KEY (article_id, technology_id),
                FOREIGN KEY (article_id) REFERENCES news_articles(id),
                FOREIGN KEY (technology_id) REFERENCES technologies(id)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_article_technologies_technology
            ON article_technologies(technology_id)
        """)
        
        # Reports table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                generated_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                report_type TEXT,
                period_start DATETIME,
                period_end DATETIME,
                file_path TEXT,
                summary TEXT
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reports_date 
            ON reports(generated_date)
        """)
        
        conn.commit()
        conn.close()
    
    def store_article(self, article_data: dict) -> str:
        """Store a news article.
        
        Args:
            article_data: Dictionary containing article data.
            
        Returns:
            The article ID.
        """
        article_id = article_data.get("id") or str(uuid.uuid4())
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO news_articles 
                (id, title, url, source, author, published_date, collected_date,
                 summary, content, sentiment_score, relevance_score, is_tech_related, category, keywords, processed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                article_id,
                article_data.get("title", ""),
                article_data.get("url", ""),
                article_data.get("source", ""),
                article_data.get("author"),
                article_data.get("published_date"),
                article_data.get("collected_date", datetime.now().isoformat()),
                article_data.get("summary", ""),
                article_data.get("content"),
                article_data.get("sentiment_score", 0.0),
                article_data.get("relevance_score", 0.0),
                article_data.get("is_tech_related", True),
                article_data.get("category", "General"),
                json.dumps(article_data.get("keywords", [])),
                article_data.get("processed", False)
            ))
            conn.commit()
        except sqlite3.IntegrityError as e:
            # URL already exists, update instead
            cursor.execute("""
                UPDATE news_articles SET
                    title = ?, source = ?, author = ?, published_date = ?,
                    summary = ?, content = ?, sentiment_score = ?,
                    relevance_score = ?, is_tech_related = ?, category = ?, keywords = ?
                WHERE url = ?
            """, (
                article_data.get("title", ""),
                article_data.get("source", ""),
                article_data.get("author"),
                article_data.get("published_date"),
                article_data.get("summary", ""),
                article_data.get("content"),
                article_data.get("sentiment_score", 0.0),
                article_data.get("relevance_score", 0.0),
                article_data.get("is_tech_related", True),
                article_data.get("category", "General"),
                json.dumps(article_data.get("keywords", [])),
                article_data.get("url", "")
            ))
            # Get the existing ID
            cursor.execute("SELECT id FROM news_articles WHERE url = ?", (article_data.get("url", ""),))
            row = cursor.fetchone()
            if row:
                article_id = row["id"]
            conn.commit()
        finally:
            conn.close()
        
        return article_id
    
    def store_company(self, company_data: dict) -> str:
        """Store or update a company.
        
        Args:
            company_data: Dictionary containing company data.
            
        Returns:
            The company ID.
        """
        company_id = company_data.get("id") or str(uuid.uuid4())
        company_name = company_data.get("name", "")
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Check if company exists
            cursor.execute("SELECT id, mention_count FROM companies WHERE name = ?", (company_name,))
            row = cursor.fetchone()
            
            if row:
                # Update existing company
                company_id = row["id"]
                cursor.execute("""
                    UPDATE companies SET
                        country = COALESCE(?, country),
                        industry = COALESCE(?, industry),
                        last_mentioned = ?,
                        mention_count = mention_count + 1
                    WHERE id = ?
                """, (
                    company_data.get("country"),
                    company_data.get("industry"),
                    datetime.now().isoformat(),
                    company_id
                ))
            else:
                # Insert new company
                cursor.execute("""
                    INSERT INTO companies (id, name, country, industry, first_mentioned, last_mentioned)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    company_id,
                    company_name,
                    company_data.get("country"),
                    company_data.get("industry"),
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))
            conn.commit()
        finally:
            conn.close()
        
        return company_id
    
    def store_country(self, country_data: dict) -> str:
        """Store or update a country.
        
        Args:
            country_data: Dictionary containing country data.
            
        Returns:
            The country ID.
        """
        country_id = country_data.get("id") or str(uuid.uuid4())
        country_name = country_data.get("name", "")
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Check if country exists
            cursor.execute("SELECT id, mention_count FROM countries WHERE name = ?", (country_name,))
            row = cursor.fetchone()
            
            if row:
                # Update existing country
                country_id = row["id"]
                cursor.execute("""
                    UPDATE countries SET
                        code = COALESCE(?, code),
                        last_mentioned = ?,
                        mention_count = mention_count + 1
                    WHERE id = ?
                """, (
                    country_data.get("code"),
                    datetime.now().isoformat(),
                    country_id
                ))
            else:
                # Insert new country
                cursor.execute("""
                    INSERT INTO countries (id, name, code, last_mentioned)
                    VALUES (?, ?, ?, ?)
                """, (
                    country_id,
                    country_name,
                    country_data.get("code"),
                    datetime.now().isoformat()
                ))
            conn.commit()
        finally:
            conn.close()
        
        return country_id
    
    def store_technology(self, technology_data: dict) -> str:
        """Store or update a technology.
        
        Args:
            technology_data: Dictionary containing technology data.
                Expected keys: name, category, relevance, context
            
        Returns:
            The technology ID.
        """
        technology_id = technology_data.get("id") or str(uuid.uuid4())
        technology_name = technology_data.get("name", "")
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Check if technology exists
            cursor.execute("SELECT id, mention_count FROM technologies WHERE name = ?", (technology_name,))
            row = cursor.fetchone()
            
            if row:
                # Update existing technology
                technology_id = row["id"]
                cursor.execute("""
                    UPDATE technologies SET
                        category = COALESCE(?, category),
                        last_mentioned = ?,
                        mention_count = mention_count + 1
                    WHERE id = ?
                """, (
                    technology_data.get("category"),
                    datetime.now().isoformat(),
                    technology_id
                ))
            else:
                # Insert new technology
                cursor.execute("""
                    INSERT INTO technologies (id, name, category, first_mentioned, last_mentioned)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    technology_id,
                    technology_name,
                    technology_data.get("category", "General Technology"),
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))
            conn.commit()
        finally:
            conn.close()
        
        return technology_id
    
    def link_article_technologies(
        self,
        article_id: str,
        technology_ids: list[str],
        technology_data: list[dict] = None
    ):
        """Link article with technologies.
        
        Args:
            article_id: The article ID.
            technology_ids: List of technology IDs.
            technology_data: Optional list of dicts with relevance and context for each technology.
                Each dict should have keys: technology_id, relevance, context
        """
        technology_ids = technology_ids or []
        technology_data = technology_data or []
        
        # Create a lookup for technology metadata
        tech_meta = {td.get("technology_id"): td for td in technology_data if td.get("technology_id")}
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            for tech_id in technology_ids:
                meta = tech_meta.get(tech_id, {})
                relevance = meta.get("relevance", 0.5)
                context = meta.get("context", "")
                
                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO article_technologies
                        (article_id, technology_id, relevance, context)
                        VALUES (?, ?, ?, ?)
                    """, (article_id, tech_id, relevance, context))
                except sqlite3.IntegrityError:
                    pass
            conn.commit()
        finally:
            conn.close()
    
    def link_article_companies(
        self,
        article_id: str,
        company_ids: list[str],
        company_data: list[dict] = None
    ):
        """Link article with companies.
        
        Args:
            article_id: The article ID.
            company_ids: List of company IDs.
            company_data: Optional list of dicts with relevance and context for each company.
                Each dict should have keys: company_id, relevance, context
        """
        company_ids = company_ids or []
        company_data = company_data or []
        
        # Create a lookup for company metadata
        company_meta = {cd.get("company_id"): cd for cd in company_data if cd.get("company_id")}
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            for company_id in company_ids:
                meta = company_meta.get(company_id, {})
                relevance = meta.get("relevance", 0.5)
                context = meta.get("context", "")
                
                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO article_companies
                        (article_id, company_id, relevance, context)
                        VALUES (?, ?, ?, ?)
                    """, (article_id, company_id, relevance, context))
                except sqlite3.IntegrityError:
                    pass
            conn.commit()
        finally:
            conn.close()
    
    def link_article_countries(
        self,
        article_id: str,
        country_ids: list[str],
        country_data: list[dict] = None
    ):
        """Link article with countries.
        
        Args:
            article_id: The article ID.
            country_ids: List of country IDs.
            country_data: Optional list of dicts with relevance and context for each country.
                Each dict should have keys: country_id, relevance, context
        """
        country_ids = country_ids or []
        country_data = country_data or []
        
        # Create a lookup for country metadata
        country_meta = {cd.get("country_id"): cd for cd in country_data if cd.get("country_id")}
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            for country_id in country_ids:
                meta = country_meta.get(country_id, {})
                relevance = meta.get("relevance", 0.5)
                context = meta.get("context", "")
                
                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO article_countries
                        (article_id, country_id, relevance, context)
                        VALUES (?, ?, ?, ?)
                    """, (article_id, country_id, relevance, context))
                except sqlite3.IntegrityError:
                    pass
            conn.commit()
        finally:
            conn.close()
    
    def link_article_entities(
        self,
        article_id: str,
        company_ids: list[str] = None,
        country_ids: list[str] = None,
        context: str = None
    ):
        """Link article with companies and countries (legacy method for backward compatibility).
        
        This method is deprecated. Use link_article_companies() and link_article_countries() instead.
        
        Args:
            article_id: The article ID.
            company_ids: List of company IDs.
            country_ids: List of country IDs.
            context: Context string for the relationship.
        """
        # Use the new methods for backward compatibility
        if company_ids:
            self.link_article_companies(article_id, company_ids)
        if country_ids:
            self.link_article_countries(article_id, country_ids)
    
    def get_articles_by_date_range(
        self, 
        start_date: datetime, 
        end_date: datetime,
        limit: int = 100
    ) -> list[dict]:
        """Get articles within a date range.
        
        Args:
            start_date: Start of date range.
            end_date: End of date range.
            limit: Maximum number of articles to return.
            
        Returns:
            List of article dictionaries.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM news_articles
                WHERE published_date >= ? AND published_date <= ?
                ORDER BY published_date DESC
                LIMIT ?
            """, (start_date.isoformat(), end_date.isoformat(), limit))
            
            articles = []
            for row in cursor.fetchall():
                article = dict(row)
                article["keywords"] = json.loads(article["keywords"] or "[]")
                articles.append(article)
            
            return articles
        finally:
            conn.close()
    
    def get_article_by_id(self, article_id: str) -> Optional[dict]:
        """Get an article by ID.
        
        Args:
            article_id: The article ID.
            
        Returns:
            Article dictionary or None if not found.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT * FROM news_articles WHERE id = ?", (article_id,))
            row = cursor.fetchone()
            
            if row:
                article = dict(row)
                article["keywords"] = json.loads(article["keywords"] or "[]")
                return article
            return None
        finally:
            conn.close()
    
    def get_companies_by_article(self, article_id: str) -> list[dict]:
        """Get companies mentioned in an article.
        
        Args:
            article_id: The article ID.
            
        Returns:
            List of company dictionaries.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT c.*, ae.context
                FROM companies c
                JOIN article_entities ae ON c.id = ae.company_id
                WHERE ae.article_id = ?
            """, (article_id,))
            
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_countries_by_article(self, article_id: str) -> list[dict]:
        """Get countries mentioned in an article.
        
        Args:
            article_id: The article ID.
            
        Returns:
            List of country dictionaries.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT c.*, ae.context
                FROM countries c
                JOIN article_entities ae ON c.id = ae.country_id
                WHERE ae.article_id = ?
            """, (article_id,))
            
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_top_companies(self, limit: int = 10) -> list[dict]:
        """Get most mentioned companies.
        
        Args:
            limit: Maximum number of companies to return.
            
        Returns:
            List of company dictionaries.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM companies
                ORDER BY mention_count DESC
                LIMIT ?
            """, (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_top_countries(self, limit: int = 10) -> list[dict]:
        """Get most mentioned countries.
        
        Args:
            limit: Maximum number of countries to return.
            
        Returns:
            List of country dictionaries.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM countries
                ORDER BY mention_count DESC
                LIMIT ?
            """, (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_company_by_name(self, name: str) -> Optional[dict]:
        """Get a company by name.
        
        Args:
            name: The company name.
            
        Returns:
            Company dictionary or None if not found.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT * FROM companies WHERE name = ?", (name,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    
    def get_articles_by_company(self, company_name: str, limit: int = 50) -> list[dict]:
        """Get articles mentioning a specific company.
        
        Args:
            company_name: The company name.
            limit: Maximum number of articles to return.
            
        Returns:
            List of article dictionaries.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT DISTINCT a.*
                FROM news_articles a
                JOIN article_entities ae ON a.id = ae.article_id
                JOIN companies c ON ae.company_id = c.id
                WHERE c.name = ?
                ORDER BY a.published_date DESC
                LIMIT ?
            """, (company_name, limit))
            
            articles = []
            for row in cursor.fetchall():
                article = dict(row)
                article["keywords"] = json.loads(article["keywords"] or "[]")
                articles.append(article)
            
            return articles
        finally:
            conn.close()
    
    def store_report_metadata(self, report_data: dict) -> str:
        """Store report metadata.
        
        Args:
            report_data: Dictionary containing report metadata.
            
        Returns:
            The report ID.
        """
        report_id = report_data.get("id") or str(uuid.uuid4())
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO reports 
                (id, generated_date, report_type, period_start, period_end, file_path, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                report_id,
                report_data.get("generated_date", datetime.now().isoformat()),
                report_data.get("report_type", "analysis"),
                report_data.get("period_start"),
                report_data.get("period_end"),
                report_data.get("file_path"),
                report_data.get("summary", "")[:500]  # Truncate summary
            ))
            conn.commit()
        finally:
            conn.close()
        
        return report_id
    
    def get_recent_reports(self, limit: int = 10) -> list[dict]:
        """Get recent reports.
        
        Args:
            limit: Maximum number of reports to return.
            
        Returns:
            List of report dictionaries.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM reports
                ORDER BY generated_date DESC
                LIMIT ?
            """, (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_article_count(self) -> int:
        """Get total article count.
        
        Returns:
            Total number of articles.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT COUNT(*) as count FROM news_articles")
            row = cursor.fetchone()
            return row["count"] if row else 0
        finally:
            conn.close()
    
    def get_company_count(self) -> int:
        """Get total company count.
        
        Returns:
            Total number of companies.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT COUNT(*) as count FROM companies")
            row = cursor.fetchone()
            return row["count"] if row else 0
        finally:
            conn.close()
    
    def get_country_count(self) -> int:
        """Get total country count.
        
        Returns:
            Total number of countries.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT COUNT(*) as count FROM countries")
            row = cursor.fetchone()
            return row["count"] if row else 0
        finally:
            conn.close()
    
    def search_articles(self, query: str, limit: int = 20) -> list[dict]:
        """Search articles by title, summary, content, or keywords.
        
        Args:
            query: Search query.
            limit: Maximum number of articles to return.
            
        Returns:
            List of matching article dictionaries.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            search_pattern = f"%{query}%"
            cursor.execute("""
                SELECT * FROM news_articles
                WHERE title LIKE ? 
                   OR summary LIKE ? 
                   OR content LIKE ?
                   OR keywords LIKE ?
                ORDER BY published_date DESC
                LIMIT ?
            """, (search_pattern, search_pattern, search_pattern, search_pattern, limit))
            
            articles = []
            for row in cursor.fetchall():
                article = dict(row)
                article["keywords"] = json.loads(article["keywords"] or "[]")
                articles.append(article)
            
            return articles
        finally:
            conn.close()
    
    # =========================================================================
    # URL Deduplication Methods
    # =========================================================================
    
    def url_exists(self, url: str) -> bool:
        """Check if a URL has already been collected.
        
        This method is used for URL deduplication to prevent collecting
        the same article multiple times.
        
        Args:
            url: The URL to check.
            
        Returns:
            True if URL exists in database, False otherwise.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "SELECT 1 FROM news_articles WHERE url = ? LIMIT 1",
                (url,)
            )
            return cursor.fetchone() is not None
        finally:
            conn.close()
    
    def get_urls_batch(self, urls: list) -> set:
        """Check which URLs from a batch already exist in the database.
        
        This is an efficient way to check multiple URLs at once for
        deduplication purposes.
        
        Args:
            urls: List of URLs to check.
            
        Returns:
            Set of URLs that already exist in the database.
        """
        if not urls:
            return set()
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            placeholders = ",".join("?" * len(urls))
            cursor.execute(
                f"SELECT url FROM news_articles WHERE url IN ({placeholders})",
                urls
            )
            return {row["url"] for row in cursor.fetchall()}
        finally:
            conn.close()
    
    def get_collected_urls_since(self, since_date: datetime) -> set:
        """Get all URLs collected since a specific date.
        
        This can be used to get a snapshot of recently collected URLs
        for deduplication or analysis purposes.
        
        Args:
            since_date: The starting date.
            
        Returns:
            Set of URLs collected since the specified date.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "SELECT url FROM news_articles WHERE collected_date >= ?",
                (since_date.isoformat(),)
            )
            return {row["url"] for row in cursor.fetchall()}
        finally:
            conn.close()
    
    # =========================================================================
    # Additional Search Methods
    # =========================================================================
    
    def get_articles_by_source(self, source: str, limit: int = 50) -> list[dict]:
        """Get articles from a specific source.
        
        Args:
            source: Source name (e.g., 'TechCrunch', 'The Verge').
            limit: Maximum number of results.
            
        Returns:
            List of articles from the source.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM news_articles 
                WHERE source = ?
                ORDER BY published_date DESC
                LIMIT ?
            """, (source, limit))
            
            articles = []
            for row in cursor.fetchall():
                article = dict(row)
                article["keywords"] = json.loads(article["keywords"] or "[]")
                articles.append(article)
            
            return articles
        finally:
            conn.close()
    
    def get_articles_with_content(self, limit: int = 100) -> list[dict]:
        """Get articles that have non-empty content.
        
        This is useful for agents that need to perform analysis on
        full article content rather than just summaries.
        
        Args:
            limit: Maximum number of results.
            
        Returns:
            List of articles with content.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM news_articles 
                WHERE content IS NOT NULL AND content != ''
                ORDER BY published_date DESC
                LIMIT ?
            """, (limit,))
            
            articles = []
            for row in cursor.fetchall():
                article = dict(row)
                article["keywords"] = json.loads(article["keywords"] or "[]")
                articles.append(article)
            
            return articles
        finally:
            conn.close()
    
    def get_recent_articles(self, days: int = 7, limit: int = 100) -> list[dict]:
        """Get articles from the last N days.
        
        Args:
            days: Number of days to look back.
            limit: Maximum number of results.
            
        Returns:
            List of recent articles.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM news_articles 
                WHERE published_date >= datetime('now', ?)
                ORDER BY published_date DESC
                LIMIT ?
            """, (f'-{days} days', limit))
            
            articles = []
            for row in cursor.fetchall():
                article = dict(row)
                article["keywords"] = json.loads(article["keywords"] or "[]")
                articles.append(article)
            
            return articles
        finally:
            conn.close()
    
    def get_all_sources(self) -> list[str]:
        """Get a list of all unique article sources.
        
        Returns:
            List of unique source names.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT DISTINCT source FROM news_articles
                ORDER BY source
            """)
            return [row["source"] for row in cursor.fetchall()]
        finally:
            conn.close()
