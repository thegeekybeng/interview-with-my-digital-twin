import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from .config import settings

pg_pool = None

def init_pg_pool():
    global pg_pool
    try:
        pg_pool = ThreadedConnectionPool(5, 20, dsn=settings.PG_DSN)
        init_db()
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

def init_db():
    try:
        conn = get_pg_conn()
        cur = conn.cursor()
        
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS visitors (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(64) UNIQUE NOT NULL,
                email VARCHAR(255) NOT NULL,
                full_name VARCHAR(120),
                company VARCHAR(120),
                role_type VARCHAR(50) NOT NULL,
                access_tier VARCHAR(20) NOT NULL DEFAULT 'RESTRICTED',
                questions_remaining INT NOT NULL DEFAULT 3,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                session_expires_at TIMESTAMP WITH TIME ZONE NOT NULL
            );
            """
        )
        
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS email_verifications (
                email VARCHAR(255) PRIMARY KEY,
                otp_code VARCHAR(6) NOT NULL,
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                attempts INT DEFAULT 0
            );
            """
        )
        
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ip_strikes (
                ip_address VARCHAR(45) PRIMARY KEY,
                strikes INT DEFAULT 0,
                is_blocked BOOLEAN DEFAULT FALSE,
                blocked_until TIMESTAMP WITH TIME ZONE,
                last_violation TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_logs (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(64) REFERENCES visitors(session_id) ON DELETE CASCADE,
                role VARCHAR(20) NOT NULL,
                content TEXT NOT NULL,
                prompt_tokens INT,
                completion_tokens INT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS consulting_leads (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(64) REFERENCES visitors(session_id),
                company VARCHAR(120),
                budget_range VARCHAR(50),
                scope_summary TEXT,
                notified_via_smtp BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS repository_embeddings (
                id SERIAL PRIMARY KEY,
                doc_type VARCHAR(30) NOT NULL DEFAULT 'code',
                repo_name VARCHAR(100) NOT NULL,
                file_path TEXT NOT NULL,
                chunk_index INT NOT NULL,
                content TEXT NOT NULL,
                embedding vector(768) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS revalidation_appeals (
                id SERIAL PRIMARY KEY,
                ip_address VARCHAR(45) NOT NULL,
                real_name VARCHAR(120) NOT NULL,
                real_email VARCHAR(255) NOT NULL,
                contact_details VARCHAR(255) NOT NULL,
                reason TEXT NOT NULL,
                submitted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS repo_embeddings_cosine_idx 
            ON repository_embeddings USING hnsw (embedding vector_cosine_ops);
            """
        )
        
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS semantic_policy_anchors (
                id SERIAL PRIMARY KEY,
                role_type VARCHAR(50) NOT NULL,
                anchor_type VARCHAR(20) NOT NULL,
                description TEXT NOT NULL,
                embedding vector(768) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS policy_anchors_idx 
            ON semantic_policy_anchors USING hnsw (embedding vector_cosine_ops);
            """
        )
        
        conn.commit()
        cur.close()
        
        # Seed baseline semantic anchors
        seed_semantic_policy_anchors(conn)
        
        release_pg_conn(conn)
        print("Postgres database schema initialized/verified successfully.")
    except Exception as e:
        print(f"Failed to initialize Postgres database schema: {e}")

def seed_semantic_policy_anchors(conn):
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM semantic_policy_anchors;")
        if cur.fetchone()[0] > 0:
            cur.close()
            return

        print("Seeding baseline semantic policy anchors...")
        anchors = [
            # Global Taboos
            ("global", "taboo_topic", "Exact salary negotiation, compensation numbers, or equity splits"),
            ("global", "taboo_topic", "Proprietary internal codebase secrets, API keys, or infrastructure passwords"),
            ("global", "negative_tone", "Arrogant, confrontational, dismissive, or condescending phrasing"),
            
            # Technical Interviewer
            ("technical", "positive_tone", "Precise, concrete, pragmatic architectural trade-offs, design patterns, and code specifics"),
            ("technical", "negative_tone", "Vague hand-waving, buzzword-heavy fluff without architectural reasoning"),
            
            # HR / Recruiter
            ("hr", "positive_tone", "Clear career milestones, quantifiable impact, leadership scope, and collaborative team mindset"),
            
            # Media / Press
            ("media", "positive_tone", "Diplomatic, forward-looking, professional, and well-structured public-facing messaging")
        ]
        
        import requests
        for role, anchor_type, text in anchors:
            try:
                res = requests.post(
                    f"{settings.OLLAMA_URL.rstrip('/')}/api/embeddings",
                    json={"model": "nomic-embed-text", "prompt": text},
                    timeout=5
                )
                if res.status_code == 200:
                    vec = res.json()["embedding"]
                    vec_str = f"[{','.join(map(str, vec))}]"
                    cur.execute(
                        """
                        INSERT INTO semantic_policy_anchors (role_type, anchor_type, description, embedding)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (role, anchor_type, text, vec_str)
                    )
            except Exception as e:
                print(f"Skipped seeding anchor '{text}' due to error: {e}")
        
        conn.commit()
        cur.close()
        print("Baseline semantic policy anchors seeded.")
    except Exception as e:
        print(f"Failed to seed semantic policy anchors: {e}")


from contextlib import contextmanager

@contextmanager
def pg_connection():
    conn = get_pg_conn()
    try:
        yield conn
    finally:
        release_pg_conn(conn)
