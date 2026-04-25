# AI Talent Scout Agent

An intelligent, multi-agent AI system built with the **Agno framework** and **Groq LLM (Llama 3)** to automate the recruitment workflow. This system can ingest resumes (PDF/DOCX), parse them into structured data, match candidates against job descriptions, simulate personalized recruiter outreach conversations, and provide a ranked shortlist—all accessible via a modern React frontend dashboard.

## Features

- **Resume Parsing Engine**: Automatically extracts text from PDF and DOCX files and uses AI to structure raw text into structured candidate profiles (skills, experience, domain, summary) in MongoDB.
- **Multi-Agent Recruitment Pipeline**:
  - **JD Parser Agent**: Extracts structured requirements, skills, and seniority from raw Job Descriptions.
  - **Candidate Matcher Agent**: Compares the JD against the candidate pool and calculates a `match_score` along with match reasons and skill gaps.
  - **Outreach Simulator Agent**: Simulates a 4-turn conversation between a recruiter and the candidate to gauge interest and availability, assigning an `interest_score`.
  - **Ranker Agent**: Weighs match and interest scores to generate a final ranked shortlist with hiring recommendations (Strong hire, Good fit, Consider, Pass).
- **Modern Dashboard UI**: A beautiful, responsive React single-page application (with modern typography and UI elements) that allows you to paste a JD and visualize the entire process, including score bars, candidate cards, and simulated conversations.

## Architecture

1. **Database Layer (`MongoDB`)**: Stores raw resume text and structured candidate profiles.
2. **Data Pipeline**:
   - `upload_resumes.py`: Reads files from the `resumes/` folder, extracts text, and pushes to MongoDB.
   - `resume_parser.py`: Runs an LLM agent over unparsed MongoDB records to enrich them with structured JSON metadata.
3. **Agent Backend (`Agents.py`)**: Defines the Agno agents and the AI reasoning pipeline.
4. **API Layer (`api.py`)**: A `FastAPI` server exposing the agent logic at `/api/scout`.
5. **Frontend (`frontend.html`)**: React-based UI that calls the API and beautifully renders the ranked results.

## Prerequisites

- **Python 3.10+**
- **MongoDB** (Local or MongoDB Atlas)
- **Groq API Key** (for Llama 3 models)

## Setup & Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Hari-Prasad0055/TALENT-SCOUNT-AGENT.git
   cd TALENT-SCOUNT-AGENT
   ```

2. **Set up a Virtual Environment (Recommended)**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Mac/Linux:
   source venv/bin/activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables**
   Create a `.env` file in the root directory and add the following keys:
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   MONGODB_URI=mongodb+srv://<username>:<password>@cluster.mongodb.net/
   MONGODB_DB=talent_db
   MONGODB_COLLECTION=candidates
   ```

## Usage Workflow

### 1. Ingest Resumes
Place your PDF or DOCX resume files into the `resumes/` folder, then run the upload script:
```bash
python upload_resumes.py
```
This will extract raw text and store it in MongoDB.

### 2. Parse Resumes
Run the parser agent to convert raw text into structured profiles:
```bash
python resume_parser.py
```
This updates the MongoDB documents with structured fields (`name`, `skills`, `experience_years`, etc.).

### 3. Start the API Server
Launch the FastAPI backend:
```bash
uvicorn api:app --reload --port 8000
```
*(The server will be available at `https://talent-scount-agent-production.up.railway.app/`)*

### 4. Open the Dashboard
Simply open the `frontend.html` file in your browser (or serve it through a static file server). Paste a job description into the text box and click **Run Talent Scout** to see the magic happen!

## Technologies Used

- **AI/LLM**: [Agno Framework](https://docs.agno.com/), Groq API (Llama 3.3 70B Versatile)
- **Backend**: Python, FastAPI, Pydantic
- **Database**: MongoDB (PyMongo)
- **Frontend**: React 18 (via CDN), Babel, Vanilla CSS
- **Utilities**: PyMuPDF (`fitz`), python-docx

## License

