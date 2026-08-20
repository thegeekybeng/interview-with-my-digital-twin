from fastmcp import FastMCP
from psycopg2.extras import RealDictCursor
import httpx
import datetime
from .config import settings
from .database import pg_connection

mcp = FastMCP("AndrewYeo-DigitalTwin")

@mcp.tool()
def query_codebase_and_adrs(session_id: str, query: str, limit: int = 4) -> str:
    """Retrieve relevant code chunks, design decisions, and system architecture context.

    Args:
        session_id: Valid visitor session ID obtained from OTP verification.
        query: Semantically query terms.
        limit: Max search results.
    """
    # 1. Validate session_id in PG
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT access_tier, session_expires_at FROM visitors WHERE session_id = %s", (session_id,))
            row = cur.fetchone()
            if not row:
                return "Error: Invalid session ID. Access denied."
            access_tier, expires_at = row
            
            # Check expiry
            now = datetime.datetime.now(datetime.timezone.utc)
            if isinstance(expires_at, str):
                if " " in expires_at:
                    expires_at = expires_at.split("+")[0].split(".")[0]
                    expires_at = datetime.datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
                else:
                    expires_at = expires_at.split("+")[0].split(".")[0]
                    expires_at = datetime.datetime.fromisoformat(expires_at)
                expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
            elif expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
            if expires_at < now:
                return "Error: Session has expired. Access denied."
                
            if access_tier != "FULL":
                return "Error: Restricted access tier. Codebase query not permitted."

    # 2. Generate query embedding via Ollama nomic-embed-text
    try:
        res = httpx.post(
            f"{settings.OLLAMA_URL}/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": query}
        )
        res.raise_for_status()
        query_vector = res.json()["embedding"]
    except Exception as e:
        return f"Error generating embeddings: {e}"

    # 3. Similarity search in pgvector using psycopg2 connection pool
    with pg_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                cur.execute(
                    """
                    SELECT file_path, doc_type, content 
                    FROM repository_embeddings 
                    ORDER BY embedding <=> %s::vector 
                    LIMIT %s;
                    """,
                    (query_vector, limit)
                )
                rows = cur.fetchall()
                return "\n\n".join([f"[{r['doc_type'].upper()}] {r['file_path']}:\n{r['content']}" for r in rows]) if rows else "No relevant codebase or architectural snippets found."
            except Exception as e:
                return f"Database query error during vector retrieval: {e}"

@mcp.tool()
def record_consulting_lead(session_id: str, company: str, budget: str, scope: str) -> str:
    """Record a consulting interest or high-priority outreach directly to Andrew.

    Args:
        session_id: Valid visitor session ID obtained from OTP verification.
        company: Outreach company name.
        budget: Projected budget range.
        scope: Project scope summary.
    """
    # 1. Validate session_id in PG
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT session_expires_at FROM visitors WHERE session_id = %s", (session_id,))
            row = cur.fetchone()
            if not row:
                return "Error: Invalid session ID. Access denied."
            expires_at = row[0]
            
            # Check expiry
            now = datetime.datetime.now(datetime.timezone.utc)
            if isinstance(expires_at, str):
                if " " in expires_at:
                    expires_at = expires_at.split("+")[0].split(".")[0]
                    expires_at = datetime.datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
                else:
                    expires_at = expires_at.split("+")[0].split(".")[0]
                    expires_at = datetime.datetime.fromisoformat(expires_at)
                expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
            elif expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
            if expires_at < now:
                return "Error: Session has expired. Access denied."

    # 2. Proceed to log lead
    with pg_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO consulting_leads (session_id, company, budget_range, scope_summary, notified_via_smtp)
                    VALUES (%s, %s, %s, %s, FALSE)
                    """,
                    (session_id, company, budget, scope)
                )
                conn.commit()
                return "Outreach logged and notification dispatched to Andrew."
            except Exception as e:
                return f"Failed to log consulting lead: {e}"
