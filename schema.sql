-- schema.sql (Consolidated PostgreSQL Schema)
CREATE EXTENSION IF NOT EXISTS vector;

-- Visitors & Session Tracking
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

-- OTP & Abuse Management
CREATE TABLE IF NOT EXISTS email_verifications (
    email VARCHAR(255) PRIMARY KEY,
    otp_code VARCHAR(6) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    attempts INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ip_strikes (
    ip_address VARCHAR(45) PRIMARY KEY,
    strikes INT DEFAULT 0,
    is_blocked BOOLEAN DEFAULT FALSE,
    blocked_at TIMESTAMP WITH TIME ZONE,
    last_attempt TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Relational Audit Logs
CREATE TABLE IF NOT EXISTS chat_logs (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    role VARCHAR(20) NOT NULL, -- 'user', 'assistant'
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Consulting Leads & Outreach Logging
CREATE TABLE IF NOT EXISTS consulting_leads (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    company VARCHAR(120) NOT NULL,
    budget_range VARCHAR(50),
    scope_summary TEXT NOT NULL,
    notified_via_smtp BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Revalidation Appeals for locked-out users
CREATE TABLE IF NOT EXISTS revalidation_appeals (
    id SERIAL PRIMARY KEY,
    ip_address VARCHAR(45) NOT NULL,
    real_name VARCHAR(120) NOT NULL,
    real_email VARCHAR(255) NOT NULL,
    contact_details VARCHAR(255) NOT NULL,
    reason TEXT NOT NULL,
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Codebase Repository Embeddings
CREATE TABLE IF NOT EXISTS repository_embeddings (
    id SERIAL PRIMARY KEY,
    doc_type VARCHAR(30) NOT NULL DEFAULT 'code', -- 'code', 'adr', 'spec'
    repo_name VARCHAR(100) NOT NULL,
    file_path TEXT NOT NULL,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(768) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS repo_embeddings_cosine_idx 
ON repository_embeddings USING hnsw (embedding vector_cosine_ops);

-- Semantic Guardrail Policy Anchors
CREATE TABLE IF NOT EXISTS semantic_policy_anchors (
    id SERIAL PRIMARY KEY,
    role_type VARCHAR(50) NOT NULL,       -- 'technical', 'hr', 'founder', 'press', 'cultural', 'global'
    anchor_type VARCHAR(20) NOT NULL,     -- 'positive_tone', 'negative_tone', 'taboo_topic'
    description TEXT NOT NULL,
    embedding vector(768) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS policy_anchors_idx 
ON semantic_policy_anchors USING hnsw (embedding vector_cosine_ops);
