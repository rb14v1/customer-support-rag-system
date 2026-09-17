from fastapi import FastAPI, Depends
from auth import authenticate

app = FastAPI()

@app.get("/api/private")
def private_route(user=Depends(authenticate)):
    return {"message": "Authenticated"}