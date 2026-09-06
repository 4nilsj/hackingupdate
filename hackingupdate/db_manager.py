"""
SQLite database manager for HackingUpdate.

Provides persistent storage of daily security findings with:
  - Date-wise storage (briefing_date)
  - Duplicate prevention via UNIQUE constraint on (briefing_date, link)
  - Pipeline run tracking
  - Query capabilities for historical data
"""

import sys
import json
import sqlite3
from datetime import date

import hackingupdate.config as config

logger = config.get_logger("db_manager")

# Database file path (defined in config.py)
DB_PATH = config.DB_PATH


def get_connection() -> sqlite3.Connection:
    """Get a connection to the SQLite database, creating it if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent read performance
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize the database schema (idempotent — safe to call multiple times)."""
    conn = get_connection()
    try:
        conn.executescript("""
            -- Daily findings table
            CREATE TABLE IF NOT EXISTS findings (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                briefing_date   DATE NOT NULL,
                title           TEXT NOT NULL,
                link            TEXT NOT NULL,
                source          TEXT,
                published_date  TEXT,
                rank            INTEGER DEFAULT 0,
                severity        TEXT,
                tags            TEXT,
                rank_reason     TEXT,
                content_text    TEXT,
                cves            TEXT,
                is_cisa_kev     INTEGER DEFAULT 0,
                epss_score      REAL DEFAULT 0.0,
                cisa_ransomware INTEGER DEFAULT 0,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                -- Prevent duplicate articles on the same briefing date
                UNIQUE(briefing_date, link)
            );

            -- Index for fast date-based queries
            CREATE INDEX IF NOT EXISTS idx_findings_date
                ON findings(briefing_date);

            -- Index for searching by rank
            CREATE INDEX IF NOT EXISTS idx_findings_rank
                ON findings(briefing_date, rank DESC);

            -- Pipeline run log
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                run_date                DATE NOT NULL,
                run_timestamp           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                articles_fetched        INTEGER DEFAULT 0,
                articles_after_filter   INTEGER DEFAULT 0,
                articles_stored         INTEGER DEFAULT 0,
                articles_skipped_dup    INTEGER DEFAULT 0,
                pipeline_duration_sec   REAL DEFAULT 0
            );
        """)

        # Safe schema migration for existing databases missing new columns
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(findings)").fetchall()}
        new_columns = [
            ("cves", "TEXT"),
            ("is_cisa_kev", "INTEGER DEFAULT 0"),
            ("epss_score", "REAL DEFAULT 0.0"),
            ("cisa_ransomware", "INTEGER DEFAULT 0"),
        ]
        for col_name, col_def in new_columns:
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE findings ADD COLUMN {col_name} {col_def}")
                logger.info(f"Migrated database: added column '{col_name}' to findings table")

        conn.commit()
        logger.info(f"Database initialized at {DB_PATH}")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    finally:
        conn.close()


def get_recent_finding_identifiers(days: int = 7, exclude_date: date | None = None) -> tuple[set[str], set[str]]:
    """
    Retrieve historical links and normalized titles from the findings table
    within the past `days` days. Excludes `exclude_date` (defaults to None)
    so re-running on the current briefing date does not suppress today's items.

    Returns:
        tuple of (set_of_links, set_of_normalized_titles)
    """
    if days <= 0:
        return set(), set()

    conn = get_connection()
    try:
        if exclude_date is not None:
            exclude_date_str = exclude_date.isoformat()
            rows = conn.execute("""
                SELECT link, title FROM findings
                WHERE briefing_date >= date('now', ? || ' days')
                  AND briefing_date != ?
            """, (f"-{days}", exclude_date_str)).fetchall()
        else:
            rows = conn.execute("""
                SELECT link, title FROM findings
                WHERE briefing_date >= date('now', ? || ' days')
            """, (f"-{days}",)).fetchall()

        links = {r["link"].strip() for r in rows if r["link"]}
        titles = {" ".join(r["title"].lower().split()) for r in rows if r["title"]}
        return links, titles
    except Exception as e:
        logger.warning(f"Failed to fetch historical finding identifiers: {e}")
        return set(), set()
    finally:
        conn.close()


def store_findings(articles: list[dict], briefing_date: date | None = None) -> dict:
    """
    Store findings into the database for a given briefing date.
    Duplicates (same link on same date) are silently skipped.

    Args:
        articles: List of article dicts from the working set.
        briefing_date: The briefing date. Defaults to today.

    Returns:
        Dict with counts: {"stored": N, "skipped_duplicate": N, "total": N}
    """
    if briefing_date is None:
        briefing_date = date.today()

    briefing_date_str = briefing_date.isoformat()

    conn = get_connection()
    stored = 0
    skipped = 0

    try:
        for article in articles:
            title = article.get("title", "")
            link = article.get("link", "")
            source = article.get("source", "")
            published_date = article.get("published_date", "")
            rank = article.get("rank", 0)
            tags = json.dumps(article.get("tags", []))
            rank_reason = article.get("rank_reason", "")
            content_text = article.get("content_text", "")

            # Threat intel enrichment fields
            cves = json.dumps(article.get("cves", []))
            is_cisa_kev = 1 if (article.get("cisa_kev", {}).get("is_kev") or article.get("is_cisa_kev")) else 0
            epss_val = article.get("epss", {}).get("max_score")
            if epss_val is None:
                epss_val = article.get("epss_score", 0.0)
            try:
                epss_score = float(epss_val or 0.0)
            except (ValueError, TypeError):
                epss_score = 0.0
            cisa_ransomware = 1 if (article.get("cisa_kev", {}).get("ransomware") or article.get("cisa_ransomware")) else 0

            # Determine severity from rank
            if rank >= 8:
                severity = "CRITICAL"
            elif rank >= 6:
                severity = "HIGH"
            elif rank >= 4:
                severity = "MEDIUM"
            else:
                severity = "LOW"

            try:
                conn.execute("""
                    INSERT INTO findings
                        (briefing_date, title, link, source, published_date,
                         rank, severity, tags, rank_reason, content_text,
                         cves, is_cisa_kev, epss_score, cisa_ransomware)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    briefing_date_str, title, link, source, published_date,
                    rank, severity, tags, rank_reason, content_text,
                    cves, is_cisa_kev, epss_score, cisa_ransomware
                ))
                stored += 1
            except sqlite3.IntegrityError:
                # Duplicate: same link on same date — skip silently
                skipped += 1
                logger.debug(f"Skipped duplicate: {title}")

        conn.commit()

        result = {
            "stored": stored,
            "skipped_duplicate": skipped,
            "total": len(articles),
            "briefing_date": briefing_date_str,
        }

        logger.info(
            f"Database: stored {stored} new findings for {briefing_date_str}, "
            f"skipped {skipped} duplicates (total input: {len(articles)})"
        )
        return result

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to store findings: {e}")
        raise
    finally:
        conn.close()


def log_pipeline_run(run_date: date | None = None, articles_fetched: int = 0,
                     articles_after_filter: int = 0, articles_stored: int = 0,
                     articles_skipped_dup: int = 0, pipeline_duration_sec: float = 0):
    """Log a pipeline execution to the database."""
    if run_date is None:
        run_date = date.today()

    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO pipeline_runs
                (run_date, articles_fetched, articles_after_filter,
                 articles_stored, articles_skipped_dup, pipeline_duration_sec)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            run_date.isoformat(), articles_fetched, articles_after_filter,
            articles_stored, articles_skipped_dup, pipeline_duration_sec
        ))
        conn.commit()
        logger.info(f"Logged pipeline run for {run_date.isoformat()}")
    except Exception as e:
        logger.error(f"Failed to log pipeline run: {e}")
    finally:
        conn.close()


def get_findings_by_date(target_date: date | None = None) -> list[dict]:
    """Retrieve all findings for a given date."""
    if target_date is None:
        target_date = date.today()

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM findings WHERE briefing_date = ? ORDER BY rank DESC",
            (target_date.isoformat(),)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_run_history(limit: int = 10) -> list[dict]:
    """Get recent pipeline run history."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM pipeline_runs ORDER BY run_timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_stats() -> dict:
    """Get summary statistics from the database."""
    conn = get_connection()
    try:
        total_findings = conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
        total_runs = conn.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0]
        unique_dates = conn.execute("SELECT COUNT(DISTINCT briefing_date) FROM findings").fetchone()[0]

        latest_row = conn.execute(
            "SELECT briefing_date, COUNT(*) as count FROM findings "
            "GROUP BY briefing_date ORDER BY briefing_date DESC LIMIT 1"
        ).fetchone()

        latest_date = latest_row["briefing_date"] if latest_row else "N/A"
        latest_count = latest_row["count"] if latest_row else 0

        # Query CISA KEV and EPSS metrics (safe even if columns newly migrated)
        try:
            total_cisa_kev = conn.execute("SELECT COUNT(*) FROM findings WHERE is_cisa_kev = 1").fetchone()[0]
            total_ransomware = conn.execute("SELECT COUNT(*) FROM findings WHERE cisa_ransomware = 1").fetchone()[0]
            max_epss_row = conn.execute("SELECT MAX(epss_score) FROM findings").fetchone()
            max_epss = float(max_epss_row[0] or 0.0) if max_epss_row else 0.0
        except sqlite3.OperationalError:
            total_cisa_kev = 0
            total_ransomware = 0
            max_epss = 0.0

        return {
            "total_findings": total_findings,
            "total_runs": total_runs,
            "unique_dates": unique_dates,
            "latest_date": latest_date,
            "latest_count": latest_count,
            "total_cisa_kev": total_cisa_kev,
            "total_ransomware": total_ransomware,
            "max_epss": max_epss,
            "db_path": str(DB_PATH),
        }
    finally:
        conn.close()


def main():
    """Initialize the database and store today's findings from the working set."""
    # Initialize schema
    init_db()

    # Load the working set
    if not config.WORKING_CACHE_FILE.exists():
        logger.warning(f"Working set not found: {config.WORKING_CACHE_FILE}. Nothing to store.")
        return

    try:
        with open(config.WORKING_CACHE_FILE, "r", encoding="utf-8") as f:
            articles = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load working set: {e}")
        sys.exit(1)

    # Store findings
    store_findings(articles)

    # Print summary
    stats = get_stats()
    logger.info(
        f"Database stats: {stats['total_findings']} total findings across "
        f"{stats['unique_dates']} days, {stats['total_runs']} pipeline runs"
    )


if __name__ == "__main__":
    main()
