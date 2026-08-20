# Interview with My Digital Twin

A secure, production-grade Model Context Protocol (MCP) compatible generative
AI agent designed to represent Andrew Yeo (Solutions Architect) during
technical recruiting interviews. The system runs an automated Codebase
Retrieval-Augmented Generation (RAG) backend utilizing a PostgreSQL database
(with pgvector) and local Ollama inference models, protected by a Know Your
Visitor (KYV) access verification loop.

---

## Technical Stack

- **Frontend**: React client SPA compiled with Vite and styled using clean,
  responsive CSS rules.
- **Backend**: FastAPI (Python 3.12) running under Uvicorn.
- **Database (Vector)**: PostgreSQL 15 with pgvector extension enabled for
  repository indexing.
- **Database (Session & Security)**: SQLite 3 (`abuse_tracker.db`) for
  rate-limiting, registration, and lead tracking.
- **Inference Engine**: Ollama running nomic-embed-text for embeddings and
  Qwen2.5-Coder for streaming chat inference.
- **Tunnels**: Cloudflare Tunnel for secure remote exposure without public
  port forwarding.

---

## Directory Layout

```text
interview-with-my-digital-twin/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── chat.py       # Chat endpoints, SMTP alerts, and OTP flows
│   │   ├── core/
│   │   │   ├── config.py     # Configuration bindings and settings loaders
│   │   │   ├── database.py   # Connection pools (Postgres / SQLite schemas)
│   │   │   └── security.py   # Sliding-window rate limiting & strike rules
│   │   └── main.py           # FastAPI router mounts & middleware setups
│   ├── Dockerfile            # Container build specification
│   └── requirements.txt      # Python package dependencies
├── frontend/
│   ├── src/
│   │   ├── App.tsx           # React UI gate and main application view
│   │   └── index.css         # Outfits & Inter typography layouts
│   ├── tsconfig.json         # TypeScript configuration
│   └── vite.config.ts        # Vite build properties
├── ingest.py                 # Codebase ingestion and vector storage pipeline
├── schema.sql                # pgvector table schemas
└── docker-compose.yml        # Multi-container orchestration config
```

---

## Database Architecture

### pgvector Schema (PostgreSQL)

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS repository_embeddings (
    id SERIAL PRIMARY KEY,
    repo_name VARCHAR(100) NOT NULL,
    file_path TEXT NOT NULL,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(768) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS repo_embeddings_cosine_idx 
ON repository_embeddings 
USING hnsw (embedding vector_cosine_ops);
```

### Security & Lead Management (SQLite)

- **`ip_strikes`**: Tracks IP addresses and strike escalations.
- **`email_verifications`**: Records generated 6-digit OTP codes and their
  expiration limits.
- **`visitors`**: Persists registered session metadata, role types, and
  granted access tiers.
- **`chat_logs`**: Logs historical user and agent messages for audit trail
  tracking.
- **`consulting_leads`**: Details scoped custom development opportunities
  including budgets, environments, and SMTP notification states.
- **`revalidation_appeals`**: Stores lockout release requests submitted by
  blocked users.

---

## Setup & Running Instructions

### 1. Ingestion Pipeline

To ingest codebases and populate vectors in the pgvector database:

```bash
# Export the database connection string
export PG_DSN="postgresql://user:pass@host:port/dbname"
export OLLAMA_URL="http://100.64.0.1:11434"

# Run the ingestion script
python ingest.py <path_to_codebase> interview-with-my-digital-twin
```

### 2. Environment Variables (.env)

Create a `.env` file at the root containing the following credentials:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
```

### 3. Docker Compose Build

To compile and deploy the backend FastAPI container service:

```bash
docker compose up --build -d
```

The server will start listening on port `3099` on the host machine.

---

## API Documentation

- **`POST /api/request_otp`**: Accepts visitor profile info, generates
  a 6-digit code, and dispatches it via SMTP.
- **`POST /api/verify_otp`**: Checks the validity of the submitted OTP
  code. If the domain is corporate, sets `access_tier` to `FULL`, otherwise
  `RESTRICTED`. Returns a secure `session_id`.
- **`POST /api/chat`**: Handles streaming chat queries. Executes pgvector
  similarity matches against context rows for `FULL` tier sessions.
- **`POST /api/revalidate`**: Receives revalidation request payloads from
  locked-out users.
