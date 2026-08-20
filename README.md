# Interview with My Digital Twin

A secure, production-grade Model Context Protocol (MCP) generative AI agent designed to represent Andrew Yeo (Solutions Architect) during technical recruiting interviews. The system runs an automated Codebase Retrieval-Augmented Generation (RAG) backend utilizing a PostgreSQL database (with pgvector) and local Ollama inference models, protected by a Know Your Visitor (KYV) access verification loop, semantic guardrails, and dynamic client-rendered systems architecture diagrams.

---

## Technical Stack

- **Frontend**: React client SPA compiled with Vite and styled using clean, responsive CSS rules. Integrates dynamic-import code-split Mermaid.js rendering with local SVG export.
- **Backend**: FastAPI (Python 3.12) running under Uvicorn with a thread-safe connection pool.
- **Database (Unified PostgreSQL)**: PostgreSQL 15 with pgvector extension enabled. All relational, session, OTP, security strikes, and vector embeddings are stored in a consolidated Postgres instance.
- **Inference Engine**: Ollama running nomic-embed-text for embeddings, Qwen2.5-Coder:32B (temp 0.1) for technical streams, and Llama3.1:8B (temp 0.2) for conversational/recruiting roles.
- **Tunnels**: Reverse Proxy Tunnel for secure remote exposure without public port forwarding.

---

## Directory Layout

```text
interview-with-my-digital-twin/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── chat.py               # Chat endpoints, SMTP alerts, and OTP flows
│   │   ├── core/
│   │   │   ├── config.py             # Configuration bindings and settings loaders
│   │   │   ├── database.py           # Threaded PostgreSQL connection pool & schema DDLs
│   │   │   ├── security.py           # Sliding-window rate limiting & strike rules
│   │   │   ├── mcp_server.py         # FastMCP SSE tool definitions (codebase query & leads)
│   │   │   └── semantic_validator.py # Cosine-similarity input intent & output tone validators
│   │   └── main.py                   # FastAPI app, FastMCP SSE mount, and middleware
│   ├── Dockerfile                    # Container build specification
│   └── requirements.txt              # Python package dependencies
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   └── MermaidBlock.tsx      # Dynamic-import client-side Mermaid rendering with export
│   │   ├── App.tsx                   # React UI main page, streaming parser, and chat gate
│   │   └── index.css                 # Outfits & Inter typography layouts
│   ├── tsconfig.json                 # TypeScript configuration
│   └── vite.config.ts                # Vite build properties
├── ingest.py                         # Codebase ingestion and vector storage pipeline
├── schema.sql                        # Consolidated PostgreSQL database schema
└── docker-compose.yml                # Multi-container orchestration config
```

---

## Database Architecture (Consolidated PostgreSQL)

All relational and vector dimensions are unified in PostgreSQL to prevent database locks and connection bottlenecks:

- **`visitors`**: Persists registered session metadata, role types, granted access tiers, and question count caps.
- **`email_verifications`**: Records generated 6-digit OTP codes and their expiration limits.
- **`ip_strikes`**: Tracks IP addresses and strike escalations for policy violations.
- **`chat_logs`**: Logs historical user and agent messages for audit trail tracking.
- **`consulting_leads`**: Details scoped custom development opportunities including budgets, environments, and SMTP notification states.
- **`revalidation_appeals`**: Stores lockout release requests submitted by blocked users.
- **`repository_embeddings`**: Stores 768-dimensional document chunks and repository vector definitions.
- **`semantic_policy_anchors`**: Stores pre-computed tone and taboo centroids representing guardrail boundaries.

---

## Setup & Running Instructions

### 1. Ingestion Pipeline
To ingest codebases and populate vectors in the pgvector database:

```bash
# Export the database connection string
export PG_DSN="postgresql://mps:password@host:port/dbname"
export OLLAMA_URL="http://localhost:11434"

# Run the ingestion script
python ingest.py <path_to_codebase> interview-with-my-digital-twin
```

### 2. Host Inference Environment (Ollama Settings)
To prevent VRAM contention, model swapping latency, and cold-start timeouts on the Ollama host (Edge Compute Node), pin the following environment variables:

```bash
# Environment configurations on Ollama service host
OLLAMA_NUM_PARALLEL=2          # Allows concurrent inference execution
OLLAMA_MAX_LOADED_MODELS=3     # Prevents unloading Qwen / Llama / Nomic Embed
OLLAMA_KEEP_ALIVE=24h          # Keeps models loaded in GPU VRAM
```

### 3. Environment Variables (.env)
Create a `.env` file at the root containing the following credentials:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
PG_DSN=postgresql://postgres:postgres@localhost:5432/your_pgdb_name
OLLAMA_URL=http://localhost:11434
```

### 4. Docker Compose Build
To compile and deploy the backend FastAPI container service:

```bash
docker compose up --build -d
```

The server will start listening on port `3099` on the host machine.

---

## API & Model Context Protocol (MCP) Endpoints

- **`POST /api/request_otp`**: Accepts visitor profile details (name, company, email, role, linkedin), generates a 6-digit OTP, and dispatches it via SMTP.
- **`POST /api/verify_otp`**: Validates the visitor's OTP. Saves the visitor profile, grants `FULL` access for corporate email domains, and returns a secure `session_id`.
- **`POST /api/chat`**: Streams chat responses. Enforces session time-limits, rate limits, and runs semantic validator guardrails before completing completions.
- **`POST /api/revalidate`**: Submits appeal forms for locked-out IPs.
- **`GET/POST /mcp/sse`**: Exposes the FastMCP SSE sub-app. Requires a valid `session_id` inside tool arguments:
  - `query_codebase_and_adrs(session_id, query, limit)`: Performs semantic similarity search on repository embeddings.
  - `record_consulting_lead(session_id, company, budget, scope)`: Logs consulting interests to the database.

---

## Advanced Systems Hardening

### 1. Semantic Validation Engine
- **Input Guardrail (`validate_input_intent`)**: Checks incoming queries via nomic embeddings against taboo centroids (e.g. salary splits, code credentials). Matches exceeding a 0.82 similarity threshold are rejected.
- **Output Guardrail (`validate_output_tone`)**: Triggers an asynchronous task on response completion to audit tone alignment (checking proximity to role-specific positive centroids and global negative/condescending style clusters).

### 2. Connection Pool Lifecycles
- Database connections are managed via a thread-safe `ThreadedConnectionPool` (sized 5 to 20 connections) to support high-concurrency stream operations.
- The context manager `pg_connection()` guarantees immediate release of connections back to the pool, preventing leakages due to client disconnections or coroutine cancellations.

### 3. Client-Side Diagramming & Chunk Separation
- **Vite Dynamic imports**: Resolves large bundle sizes by dynamic-importing the `mermaid` package only when a diagram rendering is triggered. This maintains a lightweight critical path bundle (**168 kB**).
- **Streaming Parser Stability**: Matches open code blocks during chunk reception, displaying a monospaced skeleton loading panel (`mermaid (generating diagram...)`) to avoid rendering incomplete flowchart definitions, mounting the interactive component once closed.
