import sqlite3
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from .config import settings

pg_pool = None

def init_pg_pool():
    global pg_pool
    # Simple pool initialization. In tests, PG_DSN is mocked or skipped.
    try:
        pg_pool = SimpleConnectionPool(1, 10, dsn=settings.PG_DSN)
    except Exception as e:
        print(f"Postgres connection pool initialization deferred/skipped: {e}")

def get_pg_conn():
    global pg_pool
    if not pg_pool:
        init_pg_pool()
    return pg_pool.getconn()

def release_pg_conn(conn):
    global pg_pool
    if pg_pool:
        pg_pool.putconn(conn)

def get_tracker_conn():
    conn = sqlite3.connect(settings.TRACKER_DB)
    # Configure SQLite database schemas
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ip_strikes (
            ip_address TEXT PRIMARY KEY,
            strike_count INTEGER DEFAULT 0,
            last_violation TIMESTAMP,
            blocked_at TIMESTAMP DEFAULT NULL
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS email_verifications (
            email TEXT PRIMARY KEY,
            otp_code TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            verified INTEGER DEFAULT 0
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS visitors (
            session_id TEXT PRIMARY KEY,
            ip_address TEXT NOT NULL,
            real_name TEXT NOT NULL,
            company_name TEXT NOT NULL,
            real_email TEXT NOT NULL,
            role_type TEXT NOT NULL,
            access_tier TEXT NOT NULL,
            linkedin_url TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            sender TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(session_id) REFERENCES visitors(session_id)
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS consulting_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            project_scope TEXT NOT NULL,
            target_env TEXT NOT NULL,
            compliance_reqs TEXT,
            estimated_budget TEXT,
            timeframe TEXT,
            smtp_alerted INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(session_id) REFERENCES visitors(session_id)
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS revalidation_appeals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL,
            real_name TEXT NOT NULL,
            real_email TEXT NOT NULL,
            contact_details TEXT NOT NULL,
            reason TEXT NOT NULL,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP DEFAULT NULL
        );
        """
    )
    conn.commit()
    return conn
