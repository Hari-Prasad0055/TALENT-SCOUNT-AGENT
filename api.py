"""
api.py  —  FastAPI backend
Run: uvicorn api:app --reload --port 8000
"""

import traceback
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()  # MUST be before importing Agents

from Agents import run_talent_scouting_agent

app = FastAPI(title="Talent Scouting API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class JDRequest(BaseModel):
    job_description: str

@app.post("/api/scout")
async def scout(req: JDRequest):
    if not req.job_description.strip():
        raise HTTPException(status_code=400, detail="job_description is required")
    try:
        result = run_talent_scouting_agent(req.job_description)
        return result
    except Exception as e:
        traceback.print_exc()  # prints FULL error in terminal
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok"}
