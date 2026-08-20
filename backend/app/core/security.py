import re
import datetime
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from .database import get_tracker_conn

BANNED_PHRASES = [
    r"ignore\s+(all\s+)?instructions",
    r"system\s+override",
    r"developer\s+mode",
    r"you\s+are\s+now\s+a\s+simulator"
]

def check_session_blocked(ip: str, session_id: str = None) -> bool:
    conn = get_tracker_conn()
    cur = conn.cursor()
    
    # Check if IP is blocked directly
    cur.execute("SELECT blocked_at FROM ip_strikes WHERE ip_address = ? AND blocked_at IS NOT NULL", (ip,))
    row = cur.fetchone()
    if row:
        conn.close()
        return True
        
    # Check if session_id is associated with a blocked IP
    if session_id:
        cur.execute(
            """
            SELECT blocked_at FROM ip_strikes 
            WHERE ip_address = (SELECT ip_address FROM visitors WHERE session_id = ?)
            AND blocked_at IS NOT NULL
            """, 
            (session_id,)
        )
        row = cur.fetchone()
        if row:
            conn.close()
            return True
            
    conn.close()
    return False

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
    conn = get_tracker_conn()
    cur = conn.cursor()
    
    cur.execute("SELECT strike_count FROM ip_strikes WHERE ip_address = ?", (ip,))
    row = cur.fetchone()
    
    now = datetime.datetime.now().isoformat()
    if not row:
        cur.execute("INSERT INTO ip_strikes (ip_address, strike_count, last_violation) VALUES (?, 1, ?)", (ip, now))
        conn.commit()
        conn.close()
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
            cur.execute("UPDATE ip_strikes SET strike_count = 2, last_violation = ? WHERE ip_address = ?", (now, ip))
            conn.commit()
            conn.close()
            return JSONResponse(
                status_code=200,
                content={
                    "status": "warning", 
                    "message": "System Security Warning: Access policies strictly forbid system override attempts. This is warning 2 of 3."
                }
            )
        else:
            cur.execute("UPDATE ip_strikes SET strike_count = ?, last_violation = ?, blocked_at = ? WHERE ip_address = ?", (strikes, now, now, ip))
            conn.commit()
            conn.close()
            return JSONResponse(
                status_code=403,
                content={
                    "status": "blocked", 
                    "message": f"Access Suspended: Your IP and actions have been logged due to multiple policy violations. System access is blocked. To request review and strike removal, verify your identity via our Secure Revalidation Portal: /revalidate?ip={ip}"
                }
            )
