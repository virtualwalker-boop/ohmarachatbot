from fastapi import FastAPI
from contextlib import asynccontextmanager

from api.v1.messenger import router as messenger_router
from core.database import engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: setup resources (e.g. redis pool if needed globally)
    yield
    # Shutdown: cleanup resources
    await engine.dispose()

app = FastAPI(
    title="Ohmara Chatbot Backend",
    description="Stateful multi-functional Facebook Messenger Chatbot Backend",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(messenger_router, prefix="/api/v1/messenger", tags=["messenger"])

@app.get("/health")
async def health_check():
    return {"status": "ok"}
