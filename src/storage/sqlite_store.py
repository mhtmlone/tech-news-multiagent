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
        
        # Article-Company-Country junction table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS article_entities (
                article_id TEXT,
                company_id TEXT,
                country_id TEXT,
                context TEXT,
                PRIMARY KEY (article_id, company_id, country_id),
                FOREIGN KEY (article_id) REFERENCES news_articles(id),
                FOREIGN KEY (company_id) REFERENCES companies(id),
                FOREIGN KEY (country_id) REFERENCES countries(id)
            )
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
                 summary, content, sentiment_score, relevance_score, category, keywords, processed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    relevance_score = ?, category = ?, keywords = ?
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
    
    def link_article_entities(
        self, 
        article_id: str, 
        company_ids: list[str] = None, 
        country_ids: list[str] = None,
        context: str = None
    ):
        """Link article with companies and countries.
        
        Args:
            article_id: The article ID.
            company_ids: List of company IDs.
            country_ids: List of country IDs.
            context: Context string for the relationship.
        """
        company_ids = company_ids or []
        country_ids = country_ids or []
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            for company_id in company_ids:
                for country_id in country_ids:
                    try:
                        cursor.execute("""
                            INSERT OR IGNORE INTO article_entities 
                            (article_id, company_id, country_id, context)
                            VALUES (?, ?, ?, ?)
                        """, (article_id, company_id, country_id, context))
                    except sqlite3.IntegrityError:
                        pass
            conn.commit()
        finally:
            conn.close()
    
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
        """Search articles by title or summary.
        
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
                WHERE title LIKE ? OR summary LIKE ?
                ORDER BY published_date DESC
                LIMIT ?
            """, (search_pattern, search_pattern, limit))
            
            articles = []
            for row in cursor.fetchall():
                article = dict(row)
                article["keywords"] = json.loads(article["keywords"] or "[]")
                articles.append(article)
            
            return articles
        finally:
            conn.close()
