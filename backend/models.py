"""Pydantic request/response models for the Synapse API."""

from pydantic import BaseModel, Field
from typing import Optional


class GoalRequest(BaseModel):
    """Request to submit a new goal."""
    goal: str = Field(..., description="Natural language goal to accomplish")
    max_adaptations: int = Field(3, description="Max re-planning attempts")
    max_steps: int = Field(20, description="Max steps in the plan")


class GoalResponse(BaseModel):
    """Response after goal submission."""
    goal_id: str
    status: str
    message: str


class GoalStatusResponse(BaseModel):
    """Full status of a goal execution."""
    goal_id: str
    goal: str
    status: str
    interpretation: dict | None = None
    plan: dict | None = None
    step_results: list[dict] = []
    adaptation_count: int = 0
    final_outcome: dict | None = None
    logs: list[dict] = []


class ChatMessage(BaseModel):
    """A single chat message."""
    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: int | None = None
    metadata: dict | None = None


class ChatRequest(BaseModel):
    """Chat Protocol request (ASI:One compatible)."""
    messages: list[ChatMessage]
    goal_id: str | None = None
