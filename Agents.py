"""
AI-Powered Talent Scouting & Engagement Agent
Agno framework + Groq (llama-3.3-70b-versatile) + MongoDB

Setup:
    pip install agno groq pydantic python-dotenv pymongo pymupdf python-docx
    Add to .env:
        GROQ_API_KEY=your_key
        MONGODB_URI=mongodb+srv://...
        MONGODB_DB=talent_db
        MONGODB_COLLECTION=candidates
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


# ─────────────────────────────────────────────────────────────
# Pydantic Model
# ─────────────────────────────────────────────────────────────

class Candidate(BaseModel):
    id: str
    name: str
    title: str
    skills: list[str]
    experience_years: int
    domain: str
    summary: str




def load_candidates_from_mongo() -> list[Candidate]:
    """Fetch all parsed candidates from MongoDB."""
    uri        = os.getenv("MONGODB_URI")
    db_name    = os.getenv("MONGODB_DB", "talent_db")
    col_name   = os.getenv("MONGODB_COLLECTION", "candidates")

    if not uri:
        raise RuntimeError("MONGODB_URI not set in .env file.")

    client     = MongoClient(uri)
    db         = client[db_name]
    collection = db[col_name]

    docs = list(collection.find({"parsed": True}))
    client.close()

    if not docs:
        raise RuntimeError(
            "No parsed candidates found in MongoDB.\n"
            "Please run:  python upload_resumes.py\n"
            "Then run:    python resume_parser.py"
        )

    candidates = []
    for doc in docs:
        try:
            candidates.append(Candidate(
                id               = str(doc["_id"]),
                name             = doc.get("name", "Unknown"),
                title            = doc.get("title", ""),
                skills           = doc.get("skills", []),
                experience_years = int(doc.get("experience_years", 0)),
                domain           = doc.get("domain", ""),
                summary          = doc.get("summary", ""),
            ))
        except Exception as e:
            print(f"      [SKIP] Bad doc {doc.get('_id')}: {e}")

    print(f"      Loaded {len(candidates)} candidate(s) from MongoDB.")
    return candidates




GROQ_MODEL = "llama-3.3-70b-versatile"




jd_parser_agent = Agent(
    name="JD Parser",
    model=Groq(id=GROQ_MODEL),
    description="Parses a job description into structured JSON.",
    instructions=[
        "Extract structured information from the job description provided by the user.",
        "Identify required vs preferred skills explicitly.",
        "Infer seniority from context clues (years, scope, leadership).",
        "Your entire response must be ONLY a single valid JSON object — "
        "no markdown fences, no explanation, no preamble, no trailing text.",
        'JSON schema: {"title": "str", "required_skills": ["str"], "preferred_skills": ["str"], '
        '"experience_years": 0, "domain": "str", "key_responsibilities": ["str"], "seniority": "str"}',
    ],
    markdown=False,
)




matcher_agent = Agent(
    name="Candidate Matcher",
    model=Groq(id=GROQ_MODEL),
    description="Scores candidates against a parsed job description.",
    instructions=[
        "You receive a parsed JD and a list of candidates as JSON.",
        "For each candidate compute match_score (0-100):",
        "  Skill overlap with required_skills → 50 pts",
        "  Experience years match              → 25 pts",
        "  Domain alignment                    → 25 pts",
        "List specific match_reasons and skill/experience gaps.",
        "Your entire response must be ONLY a valid JSON array — no markdown, no explanation.",
        'Each element: {"candidate_id": "str", "match_score": 0.0, "match_reasons": ["str"], "gaps": ["str"]}',
    ],
    markdown=False,
)




outreach_agent = Agent(
    name="Outreach Simulator",
    model=Groq(id=GROQ_MODEL),
    description="Simulates a recruiter-to-candidate conversation.",
    instructions=[
        "Simulate a 4-turn recruiter <-> candidate conversation.",
        "Turn 1 - recruiter: personalised opening referencing the candidate's background.",
        "Turn 2 - candidate: realistic reply based on how well the role fits them.",
        "Turn 3 - recruiter: probe for availability, timeline, excitement level.",
        "Turn 4 - candidate: final reply indicating genuine interest (or lack of it).",
        "Assign interest_score (0-100) based on enthusiasm and availability signals.",
        "Your entire response must be ONLY a valid JSON object — no markdown, no explanation.",
        'Schema: {"conversation": [{"role": "str", "message": "str"}], '
        '"interest_score": 0.0, "conversation_summary": "str"}',
    ],
    markdown=False,
)




ranker_agent = Agent(
    name="Ranker",
    model=Groq(id=GROQ_MODEL),
    description="Produces the final ranked shortlist.",
    instructions=[
        "You receive scored candidates with match_score and interest_score.",
        "Compute: final_score = (0.7 * match_score) + (0.3 * interest_score)",
        "Sort by final_score descending. Assign rank starting at 1.",
        "Assign recommendation using these thresholds:",
        "  final_score >= 80  -> 'Strong hire'",
        "  final_score 65-79  -> 'Good fit'",
        "  final_score 50-64  -> 'Consider'",
        "  final_score < 50   -> 'Not fit'",
        "Your entire response must be ONLY a valid JSON array — no markdown, no explanation.",
        "Each element: {rank, name, title, match_score, interest_score, final_score, "
        "match_reasons, gaps, conversation_summary, recommendation}",
    ],
    markdown=False,
)




def safe_json(text: str):
    """Strip markdown fences, skip preamble, then parse JSON safely."""
    text = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()
    positions = [i for i in [text.find("["), text.find("{")] if i != -1]
    if not positions:
        raise ValueError(f"No JSON found in response:\n{text[:300]}")
    return json.loads(text[min(positions):])


def content_str(response) -> str:
    """Extract plain string from an Agno RunResponse."""
    c = response.content
    if isinstance(c, str):
        return c
    if hasattr(c, "text"):
        return c.text
    return str(c)




def run_talent_scouting_agent(job_description: str) -> dict:
    SEP = "=" * 62

    print(f"\n{SEP}")
    print("  AI TALENT SCOUTING & ENGAGEMENT AGENT  (Groq + MongoDB)")
    print(SEP)

   
    print("\n[1/4] Parsing Job Description...")
    r1 = jd_parser_agent.run(
        f"Parse this job description into structured JSON:\n\n{job_description}"
    )
    parsed_jd = safe_json(content_str(r1))
    print(f"      Role      : {parsed_jd['title']}")
    print(f"      Domain    : {parsed_jd['domain']}  |  Seniority: {parsed_jd['seniority']}")
    print(f"      Req skills: {', '.join(parsed_jd['required_skills'][:6])}")

    
    print("\n[2/4] Loading candidates from MongoDB & matching...")
    candidates   = load_candidates_from_mongo()
    cands_json   = json.dumps([c.model_dump() for c in candidates], indent=2)

    r2 = matcher_agent.run(
        f"Parsed JD:\n{json.dumps(parsed_jd, indent=2)}\n\n"
        f"Candidates:\n{cands_json}\n\n"
        "Score every candidate and return a JSON array."
    )
    match_scores   = safe_json(content_str(r2))
    all_candidates = sorted(match_scores, key=lambda x: x["match_score"], reverse=True)
    print(f"      Scored {len(all_candidates)} candidates.")
    print(f"      Order  : {[c['candidate_id'] for c in all_candidates]}")

    
    print("\n[3/4] Simulating outreach conversations...")

    
    cand_map = {c.id: c   for c in candidates}
    name_map = {c.name: c for c in candidates}
    enriched = []

    for m in all_candidates:
        cid  = m["candidate_id"]
        cand = cand_map.get(cid) or name_map.get(cid)

        if not cand:
            print(f"      WARNING: '{cid}' not found in MongoDB data — skipping.")
            continue

        r3 = outreach_agent.run(
            f"Role: {parsed_jd['title']} at a fast-growing AI startup.\n"
            f"Candidate:\n{json.dumps(cand.model_dump(), indent=2)}\n"
            f"Why they match: {m['match_reasons']}\n\n"
            "Simulate the 4-turn conversation and return JSON."
        )
        od = safe_json(content_str(r3))

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
        print(f"      {cand.name:<24} match={m['match_score']:.0f}  interest={od['interest_score']:.0f}")

    
    print(f"\n[4/4] Ranking {len(enriched)} candidates...")
    r4 = ranker_agent.run(
        f"Role: {parsed_jd['title']}\n"
        f"Candidates:\n{json.dumps(enriched, indent=2)}\n\n"
        "Rank by final_score and return the JSON array."
    )
    shortlist = safe_json(content_str(r4))

  
    print(f"\n{SEP}")
    print("  FINAL RANKED SHORTLIST")
    print(SEP)
    print(f"  {'#':<4} {'Name':<24} {'Match':>6} {'Interest':>9} {'Final':>7}  Recommendation")
    print("  " + "-" * 60)
    for c in shortlist:
        print(
            f"  #{c['rank']:<3} {c['name']:<24} "
            f"{c['match_score']:>5.1f}  "
            f"{c['interest_score']:>8.1f}  "
            f"{c['final_score']:>6.1f}   "
            f"{c.get('recommendation', '')}"
        )
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

    We are looking for a Senior ML Engineer to join our fast-growing AI product team.

    Requirements:
    - 5+ years of experience in machine learning engineering
    - Strong proficiency in Python and deep learning frameworks (PyTorch or TensorFlow)
    - Experience deploying ML models in production (MLOps, Docker, Kubernetes)
    - Familiarity with LLMs, RAG systems, and prompt engineering
    - AWS or GCP cloud experience

    Preferred:
    - Experience with Agno, LangChain, or similar agent frameworks
    - NLP research background or publications
    - Startup experience

    Responsibilities:
    - Design and deploy production ML pipelines
    - Build and maintain LLM-powered features
    - Collaborate with product and research teams
    - Mentor junior engineers
    """

    result = run_talent_scouting_agent(SAMPLE_JD)

    with open("talent_scouting_output.json", "w") as f:
        json.dump(result, f, indent=2)
    print("\nSaved → talent_scouting_output.json")

