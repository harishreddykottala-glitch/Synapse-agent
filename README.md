# 🧠 Synapse Agent

> **Autonomous AI Agent that Thinks, Plans, and Delivers**

An autonomous AI agent system built for Synapse 2026 (GDG Hackathon). Accepts natural language goals, decomposes them into structured execution plans, executes autonomously, verifies outcomes, and re-plans on failure.

## Architecture

```
 Think → Plan → Execute → Verify → Adapt → Deliver
   🧠      📋       ⚡        🔍       🔄       🎯
```

### Core Components

| Component | Path | Description |
|-----------|------|-------------|
| **Core Engine** | `core/` | AutonomousAgent orchestrator, PlannerEngine, ExecutorEngine, VerifierEngine, AdaptorEngine |
| **Multi-Agent** | `agents/` | LangGraph StateGraph with 5 specialized agents |
| **LLM Provider** | `llm/` | Google Gemini integration via google-genai |
| **Backend** | `backend/` | FastAPI with REST API, WebSocket, Chat Protocol |
| **Frontend** | `frontend/` | Next.js dashboard with chat interface & live tracking |
| **Tools** | `core/tools/` | Web search, calculator, calendar, knowledge base |
| **Memory** | `core/memory.py` | SQLite persistent storage for goals, plans, logs |

### Agent Pipeline

The system uses **LangGraph** to orchestrate 5 agents in a StateGraph:

```
START → Thinker → Planner → Executor → Verifier → [Adaptor if fail] → END
                                                   ↗ (loop back to Executor)
```

## Quick Start

### 1. Setup

```bash
cd synapse-agent
python -m venv .venv
.venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your GOOGLE_API_KEY
```

### 3. Run Backend

```bash
python main.py
# API at http://localhost:8000
# Docs at http://localhost:8000/docs
```

### 4. Run Frontend

```bash
cd frontend
npm install
npm run dev
# App at http://localhost:3000
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/goals` | POST | Submit a new goal |
| `/api/goals` | GET | List all goals |
| `/api/goals/{id}` | GET | Get goal status, plan, results |
| `/api/goals/{id}/plan` | GET | Get execution plan |
| `/api/goals/{id}/logs` | GET | Get agent logs |
| `/chat` | POST | Chat Protocol (ASI:One) |
| `/ws` | WebSocket | Real-time agent status streaming |

## Example Goals

- *"Plan my complete study schedule for GATE in 3 months"*
- *"Build me a personalised fitness and nutrition plan for 30 days"*
- *"Help me invest Rs. 10,000 smartly based on current market trends"*
- *"Analyse my startup's task backlog and prioritise by urgency and impact"*

## Tech Stack

- **Framework**: LangGraph (agent orchestration)
- **Backend**: FastAPI + WebSocket
- **LLM**: Google Gemini 2.0 Flash
- **Database**: SQLite (via aiosqlite)
- **Frontend**: Next.js 14 + TypeScript
- **Tools**: Tavily Search, Custom tools

## License

Built for Synapse 2026 — GDG Hackathon IIITDM Kurnool
