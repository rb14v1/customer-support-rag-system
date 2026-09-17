from fastapi import FastAPI
from config import API_KEY

app = FastAPI()

@app.get("/config-status")
def config_status():
    return {
        "api_key_configured": bool(API_KEY)
    }