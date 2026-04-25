"""
talent_agent.py
---------------
AI-Powered Talent Scouting & Engagement Agent
Agno + Groq + MongoDB

Pipeline:
  MongoDB resumes → JD Parser → Candidate Matcher → Outreach Simulator → Ranker → JSON result
"""

import os
import json
import re
from agno.agent import Agent
from agno.models.groq import Groq
from pydantic import BaseModel
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# ── MongoDB ───────────────────────────────────────────────────
client     = MongoClient(os.getenv("MONGODB_URI"))
db         = client[os.getenv("MONGODB_DB", "talent_db")]
collection = db[os.getenv("MONGODB_COLLECTION", "candidates")]

GROQ_MODEL = "llama-3.3-70b-versatile"


# ── Pydantic model ────────────────────────────────────────────
class Candidate(BaseModel):
    id: str
    name: str
    title: str
    skills: list[str]
    experience_years: int
    domain: str
    summary: str


# ── Load candidates from MongoDB ──────────────────────────────
def load_candidates_from_mongo() -> list[Candidate]:
    docs = list(collection.find({"parsed": True}))
    candidates = []
    for i, doc in enumerate(docs):
        candidates.append(Candidate(
            id               = str(doc["_id"]),
            name             = doc.get("name", "Unknown"),
            title            = doc.get("title", ""),
            skills           = doc.get("skills", []),
            experience_years = int(doc.get("experience_years", 0)),
            domain           = doc.get("domain", ""),
            summary          = doc.get("summary", ""),
        ))
    print(f"      Loaded {len(candidates)} candidate(s) from MongoDB.")
    return candidates


# ── Agents ────────────────────────────────────────────────────
jd_parser_agent = Agent(
    name="JD Parser", model=Groq(id=GROQ_MODEL),
    instructions=[
        "Extract structured information from the job description.",
        "Return ONLY a valid JSON object — no markdown, no preamble.",
        'Schema: {"title":"str","required_skills":["str"],"preferred_skills":["str"],'
        '"experience_years":0,"domain":"str","key_responsibilities":["str"],"seniority":"str"}',
    ], markdown=False,
)

matcher_agent = Agent(
    name="Candidate Matcher", model=Groq(id=GROQ_MODEL),
    instructions=[
        "Score each candidate against the JD (0-100):",
        "  Skill overlap → 50 pts | Experience match → 25 pts | Domain alignment → 25 pts",
        "Return ONLY a valid JSON array — no markdown, no preamble.",
        'Each element: {"candidate_id":"str","match_score":0.0,"match_reasons":["str"],"gaps":["str"]}',
    ], markdown=False,
)

outreach_agent = Agent(
    name="Outreach Simulator", model=Groq(id=GROQ_MODEL),
    instructions=[
        "Simulate a 4-turn recruiter <-> candidate conversation.",
        "Turn 1 – recruiter: personalised opening. Turn 2 – candidate: realistic reply.",
        "Turn 3 – recruiter: probe availability. Turn 4 – candidate: interest indication.",
        "Return ONLY a valid JSON object — no markdown, no preamble.",
        'Schema: {"conversation":[{"role":"str","message":"str"}],"interest_score":0.0,"conversation_summary":"str"}',
    ], markdown=False,
)

ranker_agent = Agent(
    name="Ranker", model=Groq(id=GROQ_MODEL),
    instructions=[
        "Compute final_score = 0.6 * match_score + 0.4 * interest_score.",
        "Sort descending, assign rank from 1.",
        "Recommendation: >=80 Strong hire | 65-79 Good fit | 50-64 Consider | <50 Pass",
        "Return ONLY a valid JSON array — no markdown, no preamble.",
        "Each element: {rank,name,title,match_score,interest_score,final_score,"
        "match_reasons,gaps,conversation_summary,recommendation}",
    ], markdown=False,
)


# ── Helpers ───────────────────────────────────────────────────
def safe_json(text: str):
    text = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()
    positions = [i for i in [text.find("["), text.find("{")] if i != -1]
    if not positions:
        raise ValueError(f"No JSON in response:\n{text[:300]}")
    return json.loads(text[min(positions):])

def cstr(r) -> str:
    c = r.content
    return c if isinstance(c, str) else (c.text if hasattr(c, "text") else str(c))


# ── Main pipeline ─────────────────────────────────────────────
def run_talent_scouting_agent(job_description: str) -> dict:
    SEP = "=" * 62
    print(f"\n{SEP}\n  AI TALENT SCOUTING AGENT  (Groq + MongoDB)\n{SEP}")

    # 1. Parse JD
    print("\n[1/4] Parsing Job Description...")
    parsed_jd = safe_json(cstr(jd_parser_agent.run(
        f"Parse this job description into structured JSON:\n\n{job_description}"
    )))
    print(f"      Role: {parsed_jd['title']} | Domain: {parsed_jd['domain']} | Seniority: {parsed_jd['seniority']}")

    # 2. Load candidates from MongoDB & match
    print("\n[2/4] Loading candidates from MongoDB & matching...")
    candidates = load_candidates_from_mongo()
    if not candidates:
        raise RuntimeError("No parsed candidates found in MongoDB. Run upload_resumes.py and resume_parser.py first.")

    match_scores = safe_json(cstr(matcher_agent.run(
        f"Parsed JD:\n{json.dumps(parsed_jd, indent=2)}\n\n"
        f"Candidates:\n{json.dumps([c.model_dump() for c in candidates], indent=2)}\n\n"
        "Score every candidate and return a JSON array."
    )))
    print(f"      Scored {len(match_scores)} candidates.")

    all_candidates = sorted(match_scores, key=lambda x: x["match_score"], reverse=True)

    # 3. Outreach for ALL candidates
    print("\n[3/4] Simulating outreach for all candidates...")
    cand_map = {c.id: c for c in candidates}

    # Build a name→id map as fallback (LLM sometimes returns name as candidate_id)
    name_map = {c.name: c for c in candidates}

    enriched = []
    for m in all_candidates:
        cid  = m["candidate_id"]
        cand = cand_map.get(cid) or name_map.get(cid)
        if not cand:
            print(f"      WARNING: '{cid}' not found — skipping.")
            continue

        od = safe_json(cstr(outreach_agent.run(
            f"Role: {parsed_jd['title']} at a fast-growing AI startup.\n"
            f"Candidate:\n{json.dumps(cand.model_dump(), indent=2)}\n"
            f"Why they match: {m['match_reasons']}\n\n"
            "Simulate the 4-turn conversation and return JSON."
        )))

        enriched.append({
            "candidate_id"        : cid,
            "name"                : cand.name,
            "title"               : cand.title,
            "match_score"         : m["match_score"],
            "match_reasons"       : m["match_reasons"],
            "gaps"                : m["gaps"],
            "interest_score"      : od["interest_score"],
            "conversation"        : od.get("conversation", []),
            "conversation_summary": od["conversation_summary"],
        })
        print(f"      {cand.name:<22} match={m['match_score']:.0f}  interest={od['interest_score']:.0f}")

    # 4. Rank
    print(f"\n[4/4] Ranking {len(enriched)} candidates...")
    shortlist = safe_json(cstr(ranker_agent.run(
        f"Role: {parsed_jd['title']}\n"
        f"Candidates:\n{json.dumps(enriched, indent=2)}\n\n"
        "Rank by final_score and return the JSON array."
    )))

    # Print summary
    print(f"\n{SEP}\n  FINAL RANKED SHORTLIST\n{SEP}")
    print(f"  {'#':<4} {'Name':<22} {'Match':>6} {'Interest':>9} {'Final':>7}  Recommendation")
    print("  " + "-" * 58)
    for c in shortlist:
        print(f"  #{c['rank']:<3} {c['name']:<22} {c['match_score']:>5.1f}  "
              f"{c['interest_score']:>8.1f}  {c['final_score']:>6.1f}   {c.get('recommendation','')}")
    print(SEP)

    return {
        "job_description"           : job_description,
        "parsed_jd"                 : parsed_jd,
        "shortlist"                 : shortlist,
        "total_candidates_evaluated": len(candidates),
        "candidates_contacted"      : len(enriched),
    }


if __name__ == "__main__":
    SAMPLE_JD = """
    Senior ML Engineer - AI Product Team
    Requirements:
    - 5+ years in machine learning engineering
    - Python, PyTorch or TensorFlow
    - MLOps, Docker, Kubernetes
    - LLMs, RAG systems, prompt engineering
    - AWS or GCP
    Preferred: Agno/LangChain, NLP research, startup experience
    Responsibilities: Deploy ML pipelines, build LLM features, mentor engineers
    """
    result = run_talent_scouting_agent(SAMPLE_JD)
    with open("talent_scouting_output.json", "w") as f:
        json.dump(result, f, indent=2)
    print("\nSaved → talent_scouting_output.json")
