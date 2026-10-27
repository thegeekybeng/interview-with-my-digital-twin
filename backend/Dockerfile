FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies (if any)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

EXPOSE 8000

ENV OLLAMA_URL=http://localhost:11434
ENV PG_DSN=postgresql://postgres:postgres@localhost:5432/twin_db
ENV TRACKER_DB=abuse_tracker.db
ENV PORT=8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
