from contextlib import asynccontextmanager

from fastapi import FastAPI

from config import API_KEY, validate_config


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate required environment variables before the app begins serving traffic."""
    validate_config()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/config-status")
def config_status():
    return {
        "api_key_configured": bool(API_KEY)
    }
