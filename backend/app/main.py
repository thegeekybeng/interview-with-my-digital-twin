from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import chat
from .core.database import init_pg_pool

app = FastAPI(title="Interview with Andrew Yeo's Digital Twin API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    init_pg_pool()

app.include_router(chat.router, prefix="/api")

@app.get("/api/health")
def health():
    return {"status": "ok"}
