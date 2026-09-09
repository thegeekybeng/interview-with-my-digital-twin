# System Log & Technical Decision Records (TDR)

## Technical Decision Records (TDR)

### TDR-01: FastAPI Async Streaming SSE Backend

* **Status**: Approved & Implemented (2026-08-20)
* **Context**: The portfolio digital twin chatbot requires low-latency, real-time token streaming to simulate an interactive conversation with the candidate. Traditional synchronous frameworks block request threads while awaiting LLM generation.
* **Proposed Solution**: Adopt FastAPI with Python asynchronous generators delivering Server-Sent Events (SSE) responses backed by a pooled `psycopg2` / `asyncpg` relational client.
* **Trade-offs & Known Limitations**:
  * Python async event loop can be blocked if CPU-heavy vector calculations or un-threaded file reads occur in route handlers.
  * SSE is unidirectional (server-to-client); user messages must be posted via separate HTTP POST requests.
* **Alternatives Considered**:
  1. *Flask with gevent*: [Rejected: Flask requires complex monkey-patching and lacks native async generator ASGI support].
  2. *Django Channels*: [Rejected: Substantially heavier memory footprint (>150MB baseline) for a lightweight personal assistant service].
* **Decision**: Selected FastAPI due to its native ASGI streaming capabilities, high performance, and standard OpenAPI documentation generation.
* **Migration Path**: If WebSocket bidirectional streaming or distributed actor orchestration is needed in the future, endpoints can be migrated to Starlette WebSocket handlers or Node.js without schema changes.

---

### TDR-02: Vite + React Frontend SPA Architecture

* **Status**: Approved & Implemented (2026-08-20)
* **Context**: The portfolio chat UI must be fast, responsive, and deployable as static assets alongside or inside container reverse proxies without requiring a separate Node.js server runtime.
* **Proposed Solution**: Build a single-page application using Vite + React with TypeScript, compiling to static HTML/CSS/JS in `dist/`.
* **Trade-offs & Known Limitations**:
  * Client-side rendering does not execute search engine optimization (SEO) crawlers without headless prerendering.
  * Initial page load requires downloading the client JavaScript bundle.
* **Alternatives Considered**:
  1. *Next.js App Router*: [Rejected: Requires a continuous Node.js server runtime consuming 80-120MB memory for what is fundamentally a single conversational interface].
  2. *Vanilla JavaScript / HTML*: [Rejected: Lacks reactive state management and component abstractions for complex chat history, OTP modals, and retry state machines].
* **Decision**: Adopted Vite + React for minimal runtime footprint, instant client navigation, and static asset distribution.
* **Migration Path**: If public search indexing becomes necessary, Vite SSR or Next.js static export can be adopted by importing existing React components.
