"""FastAPI Application for Synapse Agent.

Provides REST API, WebSocket, and Chat Protocol endpoints.
"""

import json
import logging
import os
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from backend.models import GoalRequest, GoalResponse, GoalStatusResponse, ChatRequest
from backend.websocket_manager import WebSocketManager
from core.agent import AutonomousAgent
from core.config import Config
from core.memory import MemoryStore
from agents.orchestrator import MasterOrchestrator

# Setup
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

config = Config()
memory = MemoryStore(config.database_path)
ws_manager = WebSocketManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("data", exist_ok=True)
    logger.info("🚀 Synapse Agent API ready")
    yield
    logger.info("Synapse Agent API shutting down")


app = FastAPI(
    title="Synapse Agent API",
    description="Autonomous AI Agent that thinks, plans, and delivers.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════
# REST API Endpoints
# ═══════════════════════════════════════

@app.get("/")
async def root():
    """Health check."""
    return {"service": "Synapse Agent", "status": "running", "version": "1.0.0"}


@app.post("/api/goals", response_model=GoalResponse)
async def create_goal(request: GoalRequest):
    """Submit a new goal for the agent to accomplish.

    The agent will Think → Plan → Execute → Verify → Adapt → Deliver.
    """
    goal_record = await memory.create_goal(request.goal)

    # Run agent in the background (non-blocking)
    import asyncio
    asyncio.create_task(_run_agent(goal_record.id, request.goal))

    return GoalResponse(
        goal_id=goal_record.id,
        status="accepted",
        message=f"Goal accepted. Track progress at /api/goals/{goal_record.id}",
    )


@app.get("/api/goals")
async def list_goals():
    """List all submitted goals."""
    goals = await memory.list_goals()
    return {
        "goals": [
            {
                "id": g.id,
                "goal": g.goal_text,
                "status": g.status,
                "created_at": g.created_at,
                "adaptation_count": g.adaptation_count,
            }
            for g in goals
        ]
    }


@app.get("/api/goals/{goal_id}")
async def get_goal(goal_id: str):
    """Get full status of a goal including plan, results, and logs."""
    goal = await memory.get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    logs = await memory.get_logs(goal_id)

    return {
        "goal_id": goal.id,
        "goal": goal.goal_text,
        "status": goal.status,
        "interpretation": goal.interpretation,
        "plan": goal.plan,
        "step_results": goal.step_results,
        "adaptation_count": goal.adaptation_count,
        "final_outcome": goal.final_outcome,
        "created_at": goal.created_at,
        "updated_at": goal.updated_at,
        "logs": logs,
    }


@app.get("/api/goals/{goal_id}/plan")
async def get_goal_plan(goal_id: str):
    """Get just the execution plan for a goal."""
    goal = await memory.get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"goal_id": goal.id, "plan": goal.plan}


@app.get("/api/goals/{goal_id}/logs")
async def get_goal_logs(goal_id: str):
    """Get all agent logs for a goal."""
    logs = await memory.get_logs(goal_id)
    return {"goal_id": goal_id, "logs": logs}


# ═══════════════════════════════════════
# Chat Protocol (ASI:One compatible)
# ═══════════════════════════════════════

@app.post("/chat")
async def chat(request: ChatRequest):
    """Chat Protocol endpoint.

    Accepts a message and starts a new goal, or continues an existing one.
    """
    user_message = next(
        (m.content for m in reversed(request.messages) if m.role == "user"),
        None,
    )
    if not user_message:
        raise HTTPException(status_code=400, detail="No user message found")

    # Create and run agent synchronously for chat
    agent = AutonomousAgent(goal=user_message, config=config)
    result = await agent.run()

    return {
        "response": {
            "role": "assistant",
            "content": result.get("final_report", str(result)),
            "timestamp": int(time.time() * 1000),
            "metadata": {
                "goal_id": result.get("goal_id"),
                "plan_title": result.get("plan_title"),
                "steps_completed": result.get("steps_completed"),
                "adaptations": result.get("adaptations"),
            },
        }
    }


# ═══════════════════════════════════════
# WebSocket for real-time streaming
# ═══════════════════════════════════════

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time agent status updates.

    Client sends: {"type": "goal", "content": "my goal text"}
    Server streams: {"event": "thinking|planning|executing_step|...", "data": {...}}
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "goal":
                goal_text = message.get("content", "")
                history = message.get("history", [])
                
                if goal_text:
                    # Create status callback for this websocket
                    status_callback = await ws_manager.create_status_callback(websocket)
                    agent = AutonomousAgent(
                        goal=goal_text,
                        history=history,
                        config=config,
                        on_status=status_callback,
                    )
                    # The agent's internal lifecycle will emit "completed"
                    # so we don't need to manually send it again
                    await agent.run()

    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await ws_manager.disconnect(websocket)


# ═══════════════════════════════════════
# Helper functions
# ═══════════════════════════════════════

async def _run_agent(goal_id: str, goal_text: str):
    """Run the autonomous agent in the background and broadcast updates."""
    async def status_callback(event: str, data: dict):
        await ws_manager.broadcast(event, {**data, "goal_id": goal_id})

    agent = AutonomousAgent(
        goal=goal_text,
        config=config,
        on_status=status_callback,
    )

    try:
        result = await agent.run()
        await ws_manager.broadcast("goal_completed", {
            "goal_id": goal_id,
            "result": result,
        })
    except Exception as e:
        logger.error(f"Background agent error: {e}")
        await memory.update_goal(goal_id, status="failed")
        await ws_manager.broadcast("goal_failed", {
            "goal_id": goal_id,
            "error": str(e),
        })
