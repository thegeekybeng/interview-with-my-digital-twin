import re
import datetime
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from .database import get_pg_conn, release_pg_conn

BANNED_PHRASES = [
    r"ignore\s+(all\s+)?instructions",
    r"system\s+override",
    r"developer\s+mode",
    r"you\s+are\s+now\s+a\s+simulator"
]

def check_session_blocked(ip: str, session_id: str = None) -> bool:
    conn = get_pg_conn()
    cur = conn.cursor()
    try:
        # Check if IP is blocked directly
        cur.execute("SELECT is_blocked FROM ip_strikes WHERE ip_address = %s AND is_blocked = TRUE", (ip,))
        row = cur.fetchone()
        if row:
            return True
            
        # Check if session_id is associated with a blocked IP
        if session_id:
            cur.execute(
                """
                SELECT is_blocked FROM ip_strikes 
                WHERE ip_address = (SELECT ip_address FROM visitors WHERE session_id = %s)
                AND is_blocked = TRUE
                """, 
                (session_id,)
            )
            row = cur.fetchone()
            if row:
                return True
        return False
    finally:
        cur.close()
        release_pg_conn(conn)

def log_strike(ip: str, text: str) -> JSONResponse | None:
    # 1. Message Length Validation (Strict characters limit)
    if len(text) > 800:
        return increment_strike(ip, "Message length exceeded 800 characters limit.")
        
    # 2. Strict instruction override scanner
    for pattern in BANNED_PHRASES:
        if re.search(pattern, text, re.IGNORECASE):
            return increment_strike(ip, "Security Violation: Policy flout detected via pattern match.")
            
    return None

def increment_strike(ip: str, reason: str) -> JSONResponse:
    conn = get_pg_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT strikes FROM ip_strikes WHERE ip_address = %s", (ip,))
        row = cur.fetchone()
        
        now = datetime.datetime.now(datetime.timezone.utc)
        if not row:
            cur.execute("INSERT INTO ip_strikes (ip_address, strikes, last_violation) VALUES (%s, 1, %s)", (ip, now))
            conn.commit()
            return JSONResponse(
                status_code=200,
                content={
                    "status": "warning", 
                    "message": "Security Alert: Please keep the query related to Andrew's professional profile. This is warning 1 of 3."
                }
            )
        else:
            strikes = row[0] + 1
            if strikes == 2:
                cur.execute("UPDATE ip_strikes SET strikes = 2, last_violation = %s WHERE ip_address = %s", (now, ip))
                conn.commit()
                return JSONResponse(
                    status_code=200,
                    content={
                        "status": "warning", 
                        "message": "System Security Warning: Access policies strictly forbid system override attempts. This is warning 2 of 3."
                    }
                )
            else:
                cur.execute("UPDATE ip_strikes SET strikes = %s, last_violation = %s, is_blocked = TRUE WHERE ip_address = %s", (strikes, now, ip))
                conn.commit()
                return JSONResponse(
                    status_code=403,
                    content={
                        "status": "blocked", 
                        "message": f"Access Suspended: Your IP and actions have been logged due to multiple policy violations. System access is blocked. To request review and strike removal, verify your identity via our Secure Revalidation Portal: /revalidate?ip={ip}"
                    }
                )
    finally:
        cur.close()
        release_pg_conn(conn)

