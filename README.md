# AI Job Application Agent

An intelligent, production-oriented autonomous job search and application assistant that parses candidate resumes, discovers and ranks jobs across multiple platforms, prepares applications with grounded Q&A, and submits applications with strict human-in-the-loop approval.

---

## Architecture Overview

```
Resume (PDF/DOCX) ─► Resume Analyzer (LLM) ─► Structured Candidate Profile
                                                       │
Job Aggregators (Greenhouse, Lever, etc.) ─► Job Collector ─► DB (PostgreSQL + pgvector)
                                                                 │
                                                       AI Job Matcher (Hybrid)
                                                                 │
                                                       Application Agent (Playwright)
                                                                 │
                                                       Grounded Q&A Agent
                                                                 │
                                                       Human Review & Approval
                                                                 │
                                                       Submission & Tracking
```

---

## Project Structure

```text
ai-job-agent/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/routes/
│   │   ├── agents/
│   │   ├── browser/
│   │   ├── ai/
│   │   ├── models/
│   │   ├── services/
│   │   └── db/
│   └── requirements.txt
├── frontend/
├── workers/
├── tests/
├── .env.example
├── .gitignore
└── README.md
```

---

## Getting Started

### 1. Prerequisites
- Python 3.11+ (Tested with Python 3.12)
- Node.js 18+ (for frontend)
- PostgreSQL with `pgvector` extension

### 2. Backend Setup
```bash
# Create and activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Run the FastAPI development server
uvicorn backend.app.main:app --reload --port 8000
```

### 3. Verify Server Health
Visit `http://localhost:8000/health` or `http://localhost:8000/docs` for the interactive OpenAPI documentation.
