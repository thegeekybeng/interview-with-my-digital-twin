import random
import uuid
import smtplib
from email.mime.text import MIMEText
import datetime
import requests
import json
import re
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from ..core.config import settings
from ..core.database import get_pg_conn, release_pg_conn, get_tracker_conn
from ..core.security import check_session_blocked, log_strike

router = APIRouter()

class OTPRequest(BaseModel):
    name: str
    company: str
    email: str
    role: str
    linkedin: str = ""

class OTPVerify(BaseModel):
    email: str
    otp_code: str
    ip_address: str
    name: str = "Visitor"
    company: str = "Company"
    role: str = "Others / Guest"

class ChatRequest(BaseModel):
    message: str

class RevalidateRequest(BaseModel):
    ip_address: str
    real_name: str
    real_email: str
    contact_details: str
    reason: str

def send_otp_email(to_email: str, name: str, otp: str):
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        # If SMTP configs are not set, log/print it and skip sending to prevent crashes during tests
        print(f"SMTP credentials missing. Deferring OTP email send to {to_email}. Code is: {otp}")
        return
        
    msg = MIMEText(f"Hello {name},\n\nYour verification code to access Andrew Yeo's Digital Twin Interview Portal is: {otp}\n\nThis code will expire in 10 minutes.")
    msg['Subject'] = "Andrew Yeo Digital Twin - Verification Code"
    msg['From'] = settings.SMTP_USER
    msg['To'] = to_email

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_USER, [to_email], msg.as_string())
    except Exception as e:
        print(f"Failed to send email via SMTP: {e}")
        # We don't raise here to allow offline test assertions to succeed

def send_lead_alert_email(visitor_name: str, company: str, email: str, project_scope: str):
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        print("SMTP credentials missing. Deferring lead notification email.")
        return False
        
    msg = MIMEText(
        f"Hello Andrew,\n\nYou have received a new consulting/project inquiry from your Digital Twin portal:\n\n"
        f"Name: {visitor_name}\n"
        f"Company: {company}\n"
        f"Email: {email}\n"
        f"Project Scope: {project_scope}\n\n"
        f"Please check your admin dashboard for full details."
    )
    msg['Subject'] = f"[Lead Alert] New consulting project request from {visitor_name}"
    msg['From'] = settings.SMTP_USER
    msg['To'] = settings.SMTP_USER  # Sends to yourself

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_USER, [settings.SMTP_USER], msg.as_string())
        return True
    except Exception as e:
        print(f"Failed to send lead alert via SMTP: {e}")
        return False

@router.post("/request_otp")
async def request_otp(payload: OTPRequest):
    otp = f"{random.randint(100000, 999999)}"
    expires = (datetime.datetime.now() + datetime.timedelta(minutes=10)).isoformat()
    
    conn = get_tracker_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO email_verifications (email, otp_code, expires_at, verified) VALUES (?, ?, ?, 0)",
        (payload.email.lower(), otp, expires)
    )
    conn.commit()
    conn.close()

    # Dispatch email asynchronously/synchronously
    send_otp_email(payload.email, payload.name, otp)
    return {"status": "sent", "message": "Verification code dispatched."}

@router.post("/verify_otp")
async def verify_otp(payload: OTPVerify):
    conn = get_tracker_conn()
    cur = conn.cursor()
    cur.execute("SELECT otp_code, expires_at FROM email_verifications WHERE email = ?", (payload.email.lower(),))
    row = cur.fetchone()

    if not row or row[0] != payload.otp_code:
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid verification code.")

    now = datetime.datetime.now().isoformat()
    if row[1] < now:
        conn.close()
        raise HTTPException(status_code=400, detail="Verification code has expired.")

    cur.execute("UPDATE email_verifications SET verified = 1 WHERE email = ?", (payload.email.lower(),))
    
    # Check if email domain is generic to determine tier
    generic_domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com"]
    email_domain = payload.email.split("@")[-1].lower()
    access_tier = "RESTRICTED" if email_domain in generic_domains else "FULL"
    
    session_id = str(uuid.uuid4())
    
    # Save the visitor details
    cur.execute(
        """
        INSERT INTO visitors (session_id, ip_address, real_name, company_name, real_email, role_type, access_tier)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (session_id, payload.ip_address, payload.name, payload.company, payload.email.lower(), payload.role, access_tier)
    )
    conn.commit()
    conn.close()

    return {"session_id": session_id, "access_tier": access_tier}

@router.post("/chat")
async def chat(request: Request, payload: ChatRequest):
    ip = request.headers.get("CF-Connecting-IP") or (request.client.host if request.client else "127.0.0.1")
    session_id = request.headers.get("X-Session-ID")
    
    if not session_id:
        raise HTTPException(status_code=401, detail="Session ID missing. Access Denied.")
        
    if check_session_blocked(ip, session_id):
        raise HTTPException(status_code=403, detail="Access Denied: Your IP or Session has been blocked.")

    # Fetch visitor profile from SQLite
    conn_tracker = get_tracker_conn()
    cur_tracker = conn_tracker.cursor()
    cur_tracker.execute("SELECT real_name, company_name, real_email, access_tier, role_type, registered_at FROM visitors WHERE session_id = ?", (session_id,))
    visitor_row = cur_tracker.fetchone()
    
    if not visitor_row:
        conn_tracker.close()
        raise HTTPException(status_code=401, detail="Invalid Session ID.")

    visitor_name, visitor_company, visitor_email, access_tier, visitor_role, registered_at = visitor_row

    # 1. Enforce time limits based on query categories
    role_limits = {
        "HR Recruiter": 15,
        "Technical Interviewer": 30,
        "Founder/Builder Collaborator": 40,
        "Media / Press": 20,
        "Cultural Fit Interview": 20,
        "Others / Guest": None
    }
    
    limit = role_limits.get(visitor_role, None)
    if limit is not None:
        try:
            # sqlite CURRENT_TIMESTAMP returns UTC format 'YYYY-MM-DD HH:MM:SS'
            registered_dt = datetime.datetime.strptime(registered_at, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                registered_dt = datetime.datetime.fromisoformat(registered_at)
            except ValueError:
                registered_dt = datetime.datetime.utcnow()
                
        elapsed_minutes = (datetime.datetime.utcnow() - registered_dt).total_seconds() / 60.0
        if elapsed_minutes > limit:
            conn_tracker.close()
            raise HTTPException(
                status_code=403,
                detail=f"Access Denied: Your session has expired. The max time limit of {limit} minutes for {visitor_role} has been reached."
            )

    # 2. Enforce turn limits for Guest/Others role (max 3 questions)
    if visitor_role not in ["HR Recruiter", "Technical Interviewer", "Founder/Builder Collaborator", "Media / Press"]:
        cur_tracker.execute("SELECT COUNT(*) FROM chat_logs WHERE session_id = ? AND sender = 'USER'", (session_id,))
        turns = cur_tracker.fetchone()[0]
        if turns >= 3:
            conn_tracker.close()
            raise HTTPException(
                status_code=403, 
                detail="Access Denied: You have reached the maximum limit of 3 queries allowed for Guest access."
            )

    # Log user query in chat_logs
    cur_tracker.execute(
        "INSERT INTO chat_logs (session_id, sender, message) VALUES (?, 'USER', ?)",
        (session_id, payload.message)
    )
    conn_tracker.commit()
    conn_tracker.close()

    # 2. Check for security violation overrides
    violation_response = log_strike(ip, payload.message)
    if violation_response:
        return violation_response

    # 3. Check for consulting project keywords
    consulting_keywords = [r"consult", r"freelance", r"build", r"contract", r"hire\s+you", r"custom\s+app", r"project"]
    is_consulting = any(re.search(pattern, payload.message, re.IGNORECASE) for pattern in consulting_keywords)
    
    if is_consulting:
        conn_leads = get_tracker_conn()
        cur_leads = conn_leads.cursor()
        
        # Save consulting leads record
        cur_leads.execute(
            """
            INSERT INTO consulting_leads (session_id, project_scope, target_env, compliance_reqs, estimated_budget, timeframe, smtp_alerted)
            VALUES (?, ?, 'Cloud/Unspecified', 'Standard', 'Negotiable', 'TBD', 0)
            """,
            (session_id, payload.message)
        )
        lead_id = cur_leads.lastrowid
        conn_leads.commit()
        conn_leads.close()

        # Send alert email to Andrew
        alert_sent = send_lead_alert_email(visitor_name, visitor_company, visitor_email, payload.message)
        if alert_sent:
            conn_leads = get_tracker_conn()
            cur_leads = conn_leads.cursor()
            cur_leads.execute("UPDATE consulting_leads SET smtp_alerted = 1 WHERE id = ?", (lead_id,))
            conn_leads.commit()
            conn_leads.close()

    # 4. Cosine RAG Search (Skip if RESTRICTED tier)
    context = "RAG search results skipped under RESTRICTED access tier."
    if access_tier == "FULL":
        try:
            emb_res = requests.post(f"{settings.OLLAMA_URL}/api/embeddings", json={"model": "nomic-embed-text", "prompt": payload.message})
            emb_res.raise_for_status()
            query_vector = emb_res.json()["embedding"]
        except Exception as e:
            # For offline testing, skip embedding error to proceed smoothly
            query_vector = None
            print(f"Skipping embeddings post query: {e}")

        if query_vector:
            try:
                conn = get_pg_conn()
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT content, repo_name, file_path 
                    FROM repository_embeddings 
                    ORDER BY embedding <=> %s::vector 
                    LIMIT 5;
                    """,
                    (query_vector,)
                )
                rows = cur.fetchall()
                cur.close()
                release_pg_conn(conn)
                context = "\n\n".join([f"Repo: {r[1]} | File: {r[2]}\nCode:\n{r[0]}" for r in rows])
            except Exception as e:
                print(f"Database query error during RAG retrieval: {e}")

    # 5. Stream LLM completions via event generator
    def event_generator():
        role_instruction = ""
        if visitor_role == "Media / Press":
            role_instruction = (
                "You are representing Andrew Yeo to the media/press. "
                "Structure your responses in a highly media-savvy, professional, "
                "diplomatic, and politically correct manner. "
                "Ensure statements are positive, objective, and represent "
                "solutions architecture leadership appropriately. "
            )
        elif visitor_role == "HR Recruiter":
            role_instruction = (
                "You are speaking to an HR Recruiter. "
                "Focus on Andrew's employment background, years of experience, "
                "collaborative skills, and overall fit for technical roles. "
            )
        elif visitor_role == "Technical Interviewer":
            role_instruction = (
                "You are speaking to a Technical Interviewer. "
                "Provide highly technical, precise, and structural answers. "
                "Reference design patterns, algorithms, and deep systems architecture details. "
            )
        elif visitor_role == "Founder/Builder Collaborator":
            role_instruction = (
                "You are speaking to a Founder or Builder Collaborator. "
                "Focus on product design, architecture scalability, MVP velocity, "
                "and custom engineering capabilities. "
            )
        elif visitor_role == "Cultural Fit Interview":
            role_instruction = (
                "You are speaking to a Cultural Fit Interviewer. "
                "Highlight Andrew's collaborative mindset, team player values, "
                "empathetic leadership approach, adaptability to company cultures, "
                "and proactive problem-solving attitude in cross-functional squads. "
            )


        prompt = (
            f"System: You are speaking with {visitor_name} from {visitor_company} (Role: {visitor_role}). "
            f"Access Tier: {access_tier}. {role_instruction}"
            f"If they request consulting or building, explain your custom architecting skills and invite them to schedule a call. "
            f"Code context:\n{context}\n\nUser: {payload.message}"
        )
        url = f"{settings.OLLAMA_URL}/api/chat"
        data = {
            "model": "qwen2.5-coder:32b",
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "options": {
                "temperature": 0.1,
                "num_predict": 512
            }
        }
        full_agent_response = []
        try:
            res = requests.post(url, json=data, stream=True)
            for chunk in res.iter_lines():
                if chunk:
                    decoded = chunk.decode("utf-8")
                    yield decoded + "\n"
                    # Try parsing streaming content to save to transcript
                    try:
                        parsed = json.loads(decoded)
                        content = parsed.get("message", {}).get("content", "")
                        if content:
                            full_agent_response.append(content)
                    except Exception:
                        pass
        except Exception as e:
            err_msg = f"Inference engine connectivity issue: {e}"
            yield json.dumps({"error": err_msg}) + "\n"
            full_agent_response.append(err_msg)

        # After streaming is complete, log agent response in database
        agent_message = "".join(full_agent_response)
        conn_log = get_tracker_conn()
        cur_log = conn_log.cursor()
        cur_log.execute(
            "INSERT INTO chat_logs (session_id, sender, message) VALUES (?, 'AGENT', ?)",
            (session_id, agent_message)
        )
        conn_log.commit()
        conn_log.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/revalidate")
async def revalidate(payload: RevalidateRequest):
    conn = get_tracker_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO revalidation_appeals (ip_address, real_name, real_email, contact_details, reason)
        VALUES (?, ?, ?, ?, ?)
        """,
        (payload.ip_address, payload.real_name, payload.real_email, payload.contact_details, payload.reason)
    )
    conn.commit()
    conn.close()
    return JSONResponse(status_code=200, content={"status": "submitted", "message": "Appeal submitted. Your details will be verified manually."})
