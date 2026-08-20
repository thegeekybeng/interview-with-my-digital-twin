import os
import sys
import glob
import requests
import psycopg2

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://100.64.0.1:11434")
PG_DSN = os.getenv("PG_DSN", "postgresql://postgres:postgres@localhost:5432/your_pgdb_name")
EMBEDDING_MODEL = "nomic-embed-text"

# File extensions to parse
VALID_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".html", ".css", 
    ".json", ".md", ".yml", ".yaml", ".sql", ".sh"
}

# Directories to completely skip
IGNORE_DIRS = {
    "node_modules", "dist", "build", "venv", ".venv", 
    ".git", ".pytest_cache", "__pycache__", "out", "target"
}

# Specific files to ignore
IGNORE_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", ".DS_Store"
}

def get_embedding(text):
    """
    Requests the vector embedding representation from Ollama on the M4 Pro.
    Supports both modern /api/embed and legacy /api/embeddings endpoints.
    """
    # 1. Try modern /api/embed endpoint
    try:
        url = f"{OLLAMA_URL.rstrip('/')}/api/embed"
        response = requests.post(url, json={
            "model": EMBEDDING_MODEL,
            "input": text
        }, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if "embeddings" in data and len(data["embeddings"]) > 0:
                return data["embeddings"][0]
    except Exception as e:
        print(f"DEBUG: /api/embed failed, trying legacy fallback: {e}")

    # 2. Try legacy /api/embeddings fallback
    try:
        url = f"{OLLAMA_URL.rstrip('/')}/api/embeddings"
        response = requests.post(url, json={
            "model": EMBEDDING_MODEL,
            "prompt": text
        }, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if "embedding" in data:
                return data["embedding"]
    except Exception as e:
        print(f"Error calling Ollama embeddings API: {e}")
    
    return None

def chunk_text(text, chunk_size=1500, overlap=200):
    """
    Splits text into chunks of character length chunk_size with overlap.
    """
    chunks = []
    start = 0
    if len(text) <= chunk_size:
        return [text]
    
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

def scan_and_ingest(repo_path, repo_name):
    print(f"Connecting to database to clear previous entries for '{repo_name}'...")
    conn = psycopg2.connect(PG_DSN)
    cur = conn.cursor()
    
    # Delete old records to prevent duplicates
    cur.execute("DELETE FROM repository_embeddings WHERE repo_name = %s", (repo_name,))
    conn.commit()
    
    print(f"Scanning directory: {repo_path}...")
    total_files = 0
    total_chunks = 0
    
    for root, dirs, files in os.walk(repo_path):
        # Modify dirs in-place to skip ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for file in files:
            if file in IGNORE_FILES or file.startswith("._"):
                continue
                
            _, ext = os.path.splitext(file)
            if ext not in VALID_EXTENSIONS:
                continue
                
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, repo_path)
            
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception as e:
                print(f"Skipping file {rel_path} due to read error: {e}")
                continue
                
            if not content.strip():
                continue
                
            print(f"Processing: {rel_path}...")
            chunks = chunk_text(content)
            
            for idx, chunk in enumerate(chunks):
                vector = get_embedding(chunk)
                if not vector:
                    print(f"Failed to generate embedding for {rel_path} chunk {idx}")
                    continue
                    
                # Format vector array as string representation required by pgvector
                vector_str = f"[{','.join(map(str, vector))}]"
                
                cur.execute(
                    """
                    INSERT INTO repository_embeddings (repo_name, file_path, chunk_index, content, embedding)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (repo_name, rel_path, idx, chunk, vector_str)
                )
                total_chunks += 1
            
            conn.commit()
            total_files += 1

    cur.close()
    conn.close()
    print(f"Ingestion Complete. Processed {total_files} files and created {total_chunks} chunks for '{repo_name}'.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python ingest.py <path_to_repo> <repo_name>")
        sys.exit(1)
        
    path_to_repo = sys.argv[1]
    repo_name = sys.argv[2]
    
    if not os.path.exists(path_to_repo):
        print(f"Error: Path {path_to_repo} does not exist.")
        sys.exit(1)
        
    scan_and_ingest(path_to_repo, repo_name)
