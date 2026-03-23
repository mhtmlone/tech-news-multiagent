#!/usr/bin/env python3
"""Database migration script to update schema from article_entities to separate junction tables.

This script migrates the database from the old schema:
- article_entities (article_id, company_id, country_id, context)

To the new schema:
- article_companies (article_id, company_id, relevance, context)
- article_countries (article_id, country_id, relevance, context)
- article_technologies (article_id, technology_id, relevance, context)
- technologies (id, name, category, first_mentioned, last_mentioned, mention_count)

Usage:
    python scripts/migrate_db_schema.py [--db-path PATH] [--backup] [--dry-run]

Options:
    --db-path PATH   Path to the SQLite database (default: ./data/news_content.db)
    --backup         Create a backup before migration (default: True)
    --dry-run        Show what would be done without making changes
"""

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


def create_backup(db_path: Path) -> Path:
    """Create a backup of the database.
    
    Args:
        db_path: Path to the database file.
        
    Returns:
        Path to the backup file.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"{db_path.stem}_backup_{timestamp}{db_path.suffix}"
    shutil.copy2(db_path, backup_path)
    return backup_path


def check_old_schema(cursor: sqlite3.Cursor) -> bool:
    """Check if the old article_entities table exists.
    
    Args:
        cursor: Database cursor.
        
    Returns:
        True if old schema exists, False otherwise.
    """
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='article_entities'
    """)
    return cursor.fetchone() is not None


def check_new_schema(cursor: sqlite3.Cursor) -> bool:
    """Check if the new tables already exist.
    
    Args:
        cursor: Database cursor.
        
    Returns:
        True if new schema exists, False otherwise.
    """
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name IN 
        ('article_companies', 'article_countries', 'article_technologies', 'technologies')
    """)
    return len(cursor.fetchall()) == 4


def get_migration_stats(cursor: sqlite3.Cursor) -> dict:
    """Get statistics about data to migrate.
    
    Args:
        cursor: Database cursor.
        
    Returns:
        Dictionary with migration statistics.
    """
    stats = {}
    
    # Count article_entities rows
    cursor.execute("SELECT COUNT(*) FROM article_entities")
    stats['article_entities_count'] = cursor.fetchone()[0]
    
    # Count unique article-company pairs
    cursor.execute("SELECT COUNT(DISTINCT article_id || '|' || company_id) FROM article_entities WHERE company_id IS NOT NULL")
    stats['unique_article_companies'] = cursor.fetchone()[0]
    
    # Count unique article-country pairs
    cursor.execute("SELECT COUNT(DISTINCT article_id || '|' || country_id) FROM article_entities WHERE country_id IS NOT NULL")
    stats['unique_article_countries'] = cursor.fetchone()[0]
    
    # Count companies
    cursor.execute("SELECT COUNT(*) FROM companies")
    stats['companies_count'] = cursor.fetchone()[0]
    
    # Count countries
    cursor.execute("SELECT COUNT(*) FROM countries")
    stats['countries_count'] = cursor.fetchone()[0]
    
    # Count articles
    cursor.execute("SELECT COUNT(*) FROM news_articles")
    stats['articles_count'] = cursor.fetchone()[0]
    
    return stats


def create_new_tables(cursor: sqlite3.Cursor, dry_run: bool = False) -> list[str]:
    """Create the new tables.
    
    Args:
        cursor: Database cursor.
        dry_run: If True, return SQL without executing.
        
    Returns:
        List of SQL statements executed or to be executed.
    """
    statements = []
    
    # Create technologies table
    statements.append("""
        CREATE TABLE IF NOT EXISTS technologies (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            category TEXT,
            first_mentioned DATETIME,
            last_mentioned DATETIME,
            mention_count INTEGER DEFAULT 1
        )
    """)
    
    # Create index on technologies
    statements.append("""
        CREATE INDEX IF NOT EXISTS idx_technologies_category 
        ON technologies(category)
    """)
    
    # Create article_companies table
    statements.append("""
        CREATE TABLE IF NOT EXISTS article_companies (
            article_id TEXT,
            company_id TEXT,
            relevance REAL DEFAULT 0.5,
            context TEXT,
            PRIMARY KEY (article_id, company_id),
            FOREIGN KEY (article_id) REFERENCES news_articles(id),
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)
    
    # Create index on article_companies
    statements.append("""
        CREATE INDEX IF NOT EXISTS idx_article_companies_company 
        ON article_companies(company_id)
    """)
    
    # Create article_countries table
    statements.append("""
        CREATE TABLE IF NOT EXISTS article_countries (
            article_id TEXT,
            country_id TEXT,
            relevance REAL DEFAULT 0.5,
            context TEXT,
            PRIMARY KEY (article_id, country_id),
            FOREIGN KEY (article_id) REFERENCES news_articles(id),
            FOREIGN KEY (country_id) REFERENCES countries(id)
        )
    """)
    
    # Create index on article_countries
    statements.append("""
        CREATE INDEX IF NOT EXISTS idx_article_countries_country 
        ON article_countries(country_id)
    """)
    
    # Create article_technologies table
    statements.append("""
        CREATE TABLE IF NOT EXISTS article_technologies (
            article_id TEXT,
            technology_id TEXT,
            relevance REAL DEFAULT 0.5,
            context TEXT,
            PRIMARY KEY (article_id, technology_id),
            FOREIGN KEY (article_id) REFERENCES news_articles(id),
            FOREIGN KEY (technology_id) REFERENCES technologies(id)
        )
    """)
    
    # Create index on article_technologies
    statements.append("""
        CREATE INDEX IF NOT EXISTS idx_article_technologies_technology 
        ON article_technologies(technology_id)
    """)
    
    if not dry_run:
        for stmt in statements:
            cursor.execute(stmt)
    
    return statements


def migrate_article_entities(cursor: sqlite3.Cursor, dry_run: bool = False) -> tuple[int, int]:
    """Migrate data from article_entities to new tables.
    
    Args:
        cursor: Database cursor.
        dry_run: If True, return counts without making changes.
        
    Returns:
        Tuple of (companies_migrated, countries_migrated).
    """
    if dry_run:
        # Just count what would be migrated
        cursor.execute("""
            SELECT COUNT(DISTINCT article_id || '|' || company_id) 
            FROM article_entities 
            WHERE company_id IS NOT NULL
        """)
        companies_count = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(DISTINCT article_id || '|' || country_id) 
            FROM article_entities 
            WHERE country_id IS NOT NULL
        """)
        countries_count = cursor.fetchone()[0]
        
        return companies_count, countries_count
    
    # Migrate article-company relationships
    cursor.execute("""
        INSERT OR IGNORE INTO article_companies (article_id, company_id, relevance, context)
        SELECT DISTINCT 
            article_id, 
            company_id, 
            0.5 as relevance,
            context
        FROM article_entities
        WHERE company_id IS NOT NULL
    """)
    companies_migrated = cursor.rowcount
    
    # Migrate article-country relationships
    cursor.execute("""
        INSERT OR IGNORE INTO article_countries (article_id, country_id, relevance, context)
        SELECT DISTINCT 
            article_id, 
            country_id, 
            0.5 as relevance,
            context
        FROM article_entities
        WHERE country_id IS NOT NULL
    """)
    countries_migrated = cursor.rowcount
    
    return companies_migrated, countries_migrated


def drop_old_table(cursor: sqlite3.Cursor, dry_run: bool = False) -> str:
    """Drop the old article_entities table.
    
    Args:
        cursor: Database cursor.
        dry_run: If True, return SQL without executing.
        
    Returns:
        SQL statement executed or to be executed.
    """
    stmt = "DROP TABLE IF EXISTS article_entities"
    
    if not dry_run:
        cursor.execute(stmt)
    
    return stmt


def run_migration(db_path: Path, backup: bool = True, dry_run: bool = False) -> None:
    """Run the database migration.
    
    Args:
        db_path: Path to the SQLite database.
        backup: Whether to create a backup before migration.
        dry_run: If True, show what would be done without making changes.
    """
    print(f"Database path: {db_path}")
    print(f"Dry run: {dry_run}")
    print()
    
    if not db_path.exists():
        print(f"Error: Database file not found: {db_path}")
        return
    
    # Connect to database
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Check current schema
        has_old_schema = check_old_schema(cursor)
        has_new_schema = check_new_schema(cursor)
        
        print("Schema status:")
        print(f"  - Old article_entities table: {'EXISTS' if has_old_schema else 'NOT FOUND'}")
        print(f"  - New junction tables: {'EXISTS' if has_new_schema else 'NOT FOUND'}")
        print()
        
        if not has_old_schema and not has_new_schema:
            print("No migration needed - database appears to be empty or new.")
            return
        
        if not has_old_schema and has_new_schema:
            print("Migration already completed - new schema is in place.")
            return
        
        # Get migration statistics
        stats = get_migration_stats(cursor)
        print("Migration statistics:")
        print(f"  - Articles: {stats['articles_count']}")
        print(f"  - Companies: {stats['companies_count']}")
        print(f"  - Countries: {stats['countries_count']}")
        print(f"  - Article-entities rows: {stats['article_entities_count']}")
        print(f"  - Unique article-company pairs: {stats['unique_article_companies']}")
        print(f"  - Unique article-country pairs: {stats['unique_article_countries']}")
        print()
        
        if dry_run:
            print("DRY RUN - No changes will be made")
            print()
        
        # Create backup
        if backup and not dry_run:
            backup_path = create_backup(db_path)
            print(f"Backup created: {backup_path}")
            print()
        
        # Create new tables
        print("Creating new tables...")
        statements = create_new_tables(cursor, dry_run)
        for stmt in statements:
            # Format for display
            stmt_display = ' '.join(stmt.split())
            print(f"  - {stmt_display[:80]}...")
        
        if not dry_run:
            conn.commit()
        print()
        
        # Migrate data
        print("Migrating data from article_entities...")
        companies_migrated, countries_migrated = migrate_article_entities(cursor, dry_run)
        print(f"  - Article-company links: {companies_migrated}")
        print(f"  - Article-country links: {countries_migrated}")
        
        if not dry_run:
            conn.commit()
        print()
        
        # Drop old table
        print("Dropping old article_entities table...")
        drop_stmt = drop_old_table(cursor, dry_run)
        print(f"  - {drop_stmt}")
        
        if not dry_run:
            conn.commit()
        print()
        
        # Final status
        if dry_run:
            print("DRY RUN COMPLETE - No changes were made")
            print("Run without --dry-run to apply changes")
        else:
            print("MIGRATION COMPLETE")
            print(f"  - Created 4 new tables: technologies, article_technologies, article_companies, article_countries")
            print(f"  - Migrated {companies_migrated} article-company links")
            print(f"  - Migrated {countries_migrated} article-country links")
            print(f"  - Dropped old article_entities table")
        
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Migrate database schema from article_entities to separate junction tables"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="./data/news_content.db",
        help="Path to the SQLite database (default: ./data/news_content.db)"
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        default=True,
        help="Create a backup before migration (default: True)"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating a backup"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    
    args = parser.parse_args()
    
    db_path = Path(args.db_path)
    backup = args.backup and not args.no_backup
    
    run_migration(db_path, backup=backup, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
