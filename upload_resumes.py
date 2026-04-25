"""
upload_resumes.py
-----------------
Reads PDF/DOCX resumes from a folder and stores them in MongoDB.
Each document stores: filename, raw_text, and parsed candidate fields.

Usage:
    1. Put all resume PDFs/DOCXs in a folder (e.g. ./resumes/)
    2. python upload_resumes.py
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient
import fitz          # PyMuPDF  — pip install pymupdf
import docx          # python-docx

load_dotenv()

# ── MongoDB connection ────────────────────────────────────────
client     = MongoClient(os.getenv("MONGODB_URI"))
db         = client[os.getenv("MONGODB_DB", "talent_db")]
collection = db[os.getenv("MONGODB_COLLECTION", "candidates")]

RESUME_FOLDER = Path("./resumes")   # <-- put your resume files here


def extract_text_pdf(path: Path) -> str:
    doc  = fitz.open(str(path))
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text.strip()


def extract_text_docx(path: Path) -> str:
    d    = docx.Document(str(path))
    text = "\n".join(p.text for p in d.paragraphs if p.text.strip())
    return text.strip()


def upload_resumes():
    if not RESUME_FOLDER.exists():
        print(f"ERROR: Folder '{RESUME_FOLDER}' not found. Create it and add resumes.")
        return

    files = list(RESUME_FOLDER.glob("*.pdf")) + list(RESUME_FOLDER.glob("*.docx"))
    if not files:
        print("No PDF or DOCX files found in ./resumes/")
        return

    print(f"Found {len(files)} resume(s). Uploading to MongoDB...\n")

    for f in files:
        try:
            raw_text = extract_text_pdf(f) if f.suffix == ".pdf" else extract_text_docx(f)

            doc = {
                "filename"  : f.name,
                "raw_text"  : raw_text,
                "source"    : "resume_upload",
            }

            # Upsert so re-running doesn't create duplicates
            result = collection.update_one(
                {"filename": f.name},
                {"$set": doc},
                upsert=True
            )
            status = "inserted" if result.upserted_id else "updated"
            print(f"  [{status}] {f.name}  ({len(raw_text)} chars)")

        except Exception as e:
            print(f"  [ERROR] {f.name}: {e}")

    print(f"\nDone. Total docs in collection: {collection.count_documents({})}")


if __name__ == "__main__":
    upload_resumes()
