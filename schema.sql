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
