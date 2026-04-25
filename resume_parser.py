"""
resume_parser.py
----------------
Uses Groq LLM to parse raw resume text from MongoDB into structured
Candidate objects, then saves parsed fields back to MongoDB.

Run this ONCE after upload_resumes.py to enrich all documents.
"""

import os
import json
import re
from dotenv import load_dotenv
from pymongo import MongoClient
from agno.agent import Agent
from agno.models.groq import Groq

load_dotenv()

# ── MongoDB ───────────────────────────────────────────────────
client     = MongoClient(os.getenv("MONGODB_URI"))
db         = client[os.getenv("MONGODB_DB", "talent_db")]
collection = db[os.getenv("MONGODB_COLLECTION", "candidates")]

# ── Parser Agent ──────────────────────────────────────────────
parser_agent = Agent(
    name="Resume Parser",
    model=Groq(id="llama-3.3-70b-versatile"),
    description="Extracts structured candidate info from raw resume text.",
    instructions=[
        "Extract candidate information from the resume text provided.",
        "Return ONLY a valid JSON object — no markdown, no preamble.",
        "JSON schema:",
        '{',
        '  "name": "str",',
        '  "title": "str",            // current or most recent job title',
        '  "skills": ["str"],         // technical skills only',
        '  "experience_years": 0,     // total years of work experience (integer)',
        '  "domain": "str",           // primary domain e.g. AI/ML, Web Dev, Data Science',
        '  "summary": "str"           // 1-2 sentence professional summary',
        '}',
    ],
    markdown=False,
)


def safe_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()
    start = min(
        (text.find("{") if text.find("{") != -1 else len(text)),
        (text.find("[") if text.find("[") != -1 else len(text)),
    )
    return json.loads(text[start:])


def parse_all_resumes():
    unparsed = list(collection.find({"parsed": {"$ne": True}}))
    print(f"Found {len(unparsed)} unparsed resume(s).\n")

    for doc in unparsed:
        fname    = doc.get("filename", doc["_id"])
        raw_text = doc.get("raw_text", "")

        if not raw_text.strip():
            print(f"  [SKIP] {fname} — empty text")
            continue

        try:
            response = parser_agent.run(
                f"Parse this resume and return structured JSON:\n\n{raw_text[:4000]}"
            )
            content = response.content if isinstance(response.content, str) else str(response.content)
            parsed  = safe_json(content)

            collection.update_one(
                {"_id": doc["_id"]},
                {"$set": {
                    "name"            : parsed.get("name", "Unknown"),
                    "title"           : parsed.get("title", ""),
                    "skills"          : parsed.get("skills", []),
                    "experience_years": int(parsed.get("experience_years", 0)),
                    "domain"          : parsed.get("domain", ""),
                    "summary"         : parsed.get("summary", ""),
                    "parsed"          : True,
                }}
            )
            print(f"  [OK] {fname} → {parsed.get('name')} | {parsed.get('title')} | {parsed.get('experience_years')}yr")

        except Exception as e:
            print(f"  [ERROR] {fname}: {e}")

    print("\nParsing complete.")


if __name__ == "__main__":
    parse_all_resumes()
