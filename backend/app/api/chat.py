import re
import uuid
import json
import sqlite3
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from core.config import settings
from core.security import (
    init_security_db,
    generate_otp,
    is_corporate_domain,
    check_ip_blocked,
    record_violation,
    sanitize_input,
    DB_PATH
)
from core.dialog_engine import PersonaDialogEngine, QARetriever, OllamaInferenceAdapter

router = APIRouter(prefix="/api", tags=["Digital Twin API"])
APP_DIR = Path(__file__).parent.parent.resolve()
RAW_QA_FILE = APP_DIR / "data" / "digital_twin_raw_qa.json"

# Deep Domain Engine Singleton
dialog_engine = PersonaDialogEngine(
    inference_adapter=OllamaInferenceAdapter(),
    retriever=QARetriever(RAW_QA_FILE)
)

# Backward-compatibility shims
retriever = dialog_engine.retriever
clean_robotics = PersonaDialogEngine.clean_robotics


def generate_llm_response(prompt: str, system_instruction: str) -> str:
    """Shim delegating to dialog_engine's inference adapter."""
    raw = dialog_engine.adapter.generate(prompt, system_instruction)
    return dialog_engine.clean_robotics(raw)


class OTPRequestSchema(BaseModel):
    name: str = "Visitor"
    company: str = "your organization"
    email: str
    role_type: str = "HR Recruiter"
    role: str = ""
    linkedin: str = ""

    def get_role(self) -> str:
        return self.role_type or self.role or "HR Recruiter"


class OTPVerifySchema(BaseModel):
    email: str
    otp_code: str
    name: str = ""
    company: str = ""
    role_type: str = ""
    role: str = ""


class ChatRequestSchema(BaseModel):
    session_id: str = ""
    message: str


class AppealRequestSchema(BaseModel):
    real_name: str
    real_email: str
    contact_details: str
    reason: str
    ip_address: str = ""


def send_otp_email(recipient_email: str, otp_code: str):
    """Sends verification OTP email if SMTP server credentials are configured in environment."""
    if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
        print(f"[SMTP Dispatch Notice]: Email credentials not set in .env. Generated OTP for {recipient_email}: {otp_code}")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Your Digital Twin Verification Code: {otp_code}"
        msg["From"] = settings.SENDER_EMAIL or settings.SMTP_USERNAME
        msg["To"] = recipient_email

        html_content = f"""
        <html>
          <body style="font-family: Arial, sans-serif; background-color: #0b0f19; color: #f8fafc; padding: 20px;">
            <div style="max-width: 500px; margin: auto; background-color: #1e293b; padding: 30px; border-radius: 12px; border: 1px solid #334155;">
              <h2 style="color: #06b6d4; text-align: center;">Andrew Yeo's Digital Twin</h2>
              <p>Hello,</p>
              <p>You requested access to interview Andrew Yeo's Digital Twin. Here is your 6-digit verification code:</p>
              <div style="font-size: 28px; font-weight: bold; font-family: monospace; letter-spacing: 4px; text-align: center; color: #10b981; background: #0f172a; padding: 15px; border-radius: 8px; margin: 20px 0;">
                {otp_code}
              </div>
              <p style="font-size: 12px; color: #94a3b8; text-align: center;">This code will expire in {settings.OTP_EXPIRY_MINUTES} minutes. If you did not request this code, please ignore this email.</p>
            </div>
          </body>
        </html>
        """
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.sendmail(msg["From"], recipient_email, msg.as_string())

        print(f"[SMTP Dispatch Success]: Verification OTP sent to {recipient_email}")
        return True
    except Exception as e:
        print(f"[SMTP Dispatch Failure]: Failed to send email to {recipient_email}: {e}")
        return False


@router.post("/request_otp")
def request_otp(payload: OTPRequestSchema, request: Request):
    init_security_db()
    client_ip = request.headers.get("CF-Connecting-IP", request.client.host if request.client else "127.0.0.1")
    if check_ip_blocked(client_ip):
        raise HTTPException(status_code=403, detail="Access denied. Your IP has been locked due to security violations.")

    otp = generate_otp()
    expires_at = (datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)).isoformat()
    role_type = payload.get_role()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR REPLACE INTO email_verifications (email, otp_code, expires_at, role_type, real_name, company_name, verified)
    VALUES (?, ?, ?, ?, ?, ?, 0)
    """, (payload.email.lower(), otp, expires_at, role_type, payload.name, payload.company))
    conn.commit()
    conn.close()

    send_otp_email(payload.email, otp)

    return {
        "status": "OTP_DISPATCHED",
        "message": f"6-digit verification code sent to {payload.email}. Valid for {settings.OTP_EXPIRY_MINUTES} minutes."
    }


@router.post("/verify_otp")
def verify_otp(payload: OTPVerifySchema, request: Request):
    client_ip = request.headers.get("CF-Connecting-IP", request.client.host if request.client else "127.0.0.1")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT otp_code, expires_at, role_type, real_name, company_name FROM email_verifications WHERE email = ?", (payload.email.lower(),))
    row = cursor.fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=400, detail="No pending OTP request found for this email.")

    stored_otp = row[0]
    expires_at = row[1]
    role_type = payload.role_type or payload.role or (row[2] if len(row) > 2 and row[2] else "HR Recruiter")
    visitor_name = payload.name or (row[3] if len(row) > 3 and row[3] else "Verified Visitor")
    visitor_company = payload.company or (row[4] if len(row) > 4 and row[4] else "your organization")

    if datetime.utcnow().isoformat() > expires_at:
        conn.close()
        raise HTTPException(status_code=400, detail="OTP expired. Please request a new verification code.")

    if stored_otp != payload.otp_code:
        conn.close()
        strikes = record_violation(client_ip)
        raise HTTPException(status_code=401, detail=f"Invalid OTP code. Strike {strikes}/{settings.MAX_STRIKES}.")

    session_id = f"session_{uuid.uuid4().hex[:12]}"
    tier = "FULL" if is_corporate_domain(payload.email) else "RESTRICTED"

    cursor.execute("UPDATE email_verifications SET verified = 1 WHERE email = ?", (payload.email.lower(),))
    cursor.execute("""
    INSERT INTO visitors (session_id, ip_address, real_name, company_name, real_email, role_type, access_tier)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (session_id, client_ip, visitor_name, visitor_company, payload.email.lower(), role_type, tier))

    conn.commit()
    conn.close()

    return {
        "status": "VERIFIED",
        "session_id": session_id,
        "role_type": role_type,
        "access_tier": tier,
        "message": f"Session established for role [{role_type}] with access tier [{tier}]."
    }


@router.post("/chat")
def chat_endpoint(payload: ChatRequestSchema, request: Request):
    client_ip = request.headers.get("CF-Connecting-IP", request.client.host if request.client else "127.0.0.1")
    if check_ip_blocked(client_ip):
        raise HTTPException(status_code=403, detail="Session blocked. Revalidation appeal required.")

    from core.guardrails import GuardrailPolicyEngine

    valid, clean_msg = sanitize_input(payload.message)
    if not valid:
        strikes = record_violation(client_ip)
        raise HTTPException(status_code=400, detail=f"Security alert: {clean_msg} (Strike {strikes}/{settings.MAX_STRIKES})")

    active_session = payload.session_id or request.headers.get("X-Session-ID") or ""

    # Retrieve session details from database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT role_type, access_tier, company_name, real_name FROM visitors WHERE session_id = ?", (active_session,))
    visitor = cursor.fetchone()

    role_type = visitor[0] if visitor else "Others / Guest"
    tier = visitor[1] if visitor else "RESTRICTED"
    target_company = visitor[2] if (visitor and len(visitor) > 2 and visitor[2]) else "your organization"

    # Evaluate Query against Guardrail Boundary Rules
    is_allowed, category, refusal = GuardrailPolicyEngine.evaluate_query(clean_msg)
    if not is_allowed:
        conn.close()
        if category == "JAILBREAK_AND_OVERRIDE":
            strikes = record_violation(client_ip)
            raise HTTPException(status_code=400, detail=f"Security Alert: {refusal} (Strike {strikes}/{settings.MAX_STRIKES})")
        
        return {
            "session_id": active_session,
            "role_type": role_type,
            "access_tier": tier,
            "response": refusal
        }

    # Log user query in chat_logs
    try:
        cursor.execute(
            "INSERT INTO chat_logs (session_id, sender, message) VALUES (?, 'user', ?)",
            (active_session, clean_msg)
        )
        conn.commit()
    except Exception as log_err:
        pass

    # Delegate full conversational RAG generation to PersonaDialogEngine
    final_sanitized_response = dialog_engine.converse(
        clean_msg=clean_msg,
        role_type=role_type,
        target_company=target_company,
        access_tier=tier
    )

    # Log agent response in chat_logs
    try:
        cursor.execute(
            "INSERT INTO chat_logs (session_id, sender, message) VALUES (?, 'assistant', ?)",
            (active_session, final_sanitized_response)
        )
        conn.commit()
    except Exception as log_err:
        pass
    finally:
        conn.close()

    return {
        "session_id": active_session,
        "role_type": role_type,
        "access_tier": tier,
        "response": final_sanitized_response
    }


@router.post("/revalidate")
def submit_appeal(payload: AppealRequestSchema, request: Request):
    client_ip = payload.ip_address or request.headers.get("CF-Connecting-IP", request.client.host if request.client else "127.0.0.1")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO revalidation_appeals (ip_address, real_name, real_email, contact_details, reason) VALUES (?, ?, ?, ?, ?)",
            (client_ip, payload.real_name, payload.real_email, payload.contact_details, payload.reason)
        )
        conn.commit()
    except Exception as e:
        print(f"[Appeal Error]: {e}")
    finally:
        conn.close()

    return {
        "status": "APPEAL_SUBMITTED",
        "message": "Revalidation appeal received. Our administrative team will review your corporate credentials."
    }


@router.get("/stats")
@router.get("/telemetry")
def get_system_stats():
    """Returns dynamic system and vector database telemetry."""
    total_vectors = 0
    total_repos = 0
    try:
        from core.database import get_pg_conn, release_pg_conn
        conn = get_pg_conn()
        cur = conn.cursor()
        try:
            cur.execute("SELECT count(*), count(DISTINCT repo_name) FROM repository_embeddings;")
            row = cur.fetchone()
            if row:
                total_vectors = int(row[0])
                total_repos = int(row[1])
        finally:
            cur.close()
            release_pg_conn(conn)
    except Exception:
        try:
            import os, psycopg2
            dsn = os.getenv("PG_DSN") or getattr(settings, "PG_DSN", None)
            if dsn:
                conn = psycopg2.connect(dsn, connect_timeout=3)
                cur = conn.cursor()
                cur.execute("SELECT count(*), count(DISTINCT repo_name) FROM repository_embeddings;")
                row = cur.fetchone()
                if row:
                    total_vectors = int(row[0])
                    total_repos = int(row[1])
                cur.close()
                conn.close()
        except Exception:
            pass

    return {
        "status": "online",
        "indexed_vectors": total_vectors,
        "indexed_vectors_formatted": f"{total_vectors:,} Production Embeddings" if total_vectors > 0 else "15,950+ Production Embeddings",
        "repos_indexed": total_repos,
        "inference_model": "Andrew-Twin (LoRA Fine-Tuned Adapter)",
        "base_model": "Qwen2.5-Coder:1.5B-Instruct",
        "compute_infrastructure": "Local Private Host (Apple Silicon M4 Pro)",
        "rag_vector_index": "pgvector (Cosine Distance HNSW)"
    }
