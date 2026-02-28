"""Planner Agent — Goal Decomposition.

Takes the interpreted goal and creates a structured multi-step execution plan.
Maps to the 'Plan' phase of Think → Plan → Deliver.
"""

import logging
from .state import AgentState
from core.planner import PlannerEngine
from llm.provider import LLMProvider

logger = logging.getLogger(__name__)


class PlannerAgent:
    """Decomposes goals into executable multi-step plans."""

    def __init__(self, llm: LLMProvider = None):
        self.llm = llm or LLMProvider()
        self.planner = PlannerEngine(self.llm)

    async def run(self, state: AgentState) -> dict:
        """Create an execution plan from the goal interpretation.

        Args:
            state: Current state with 'goal' and 'interpretation'.

        Returns:
            State updates with plan, plan_title, and logs.
        """
        goal = state["goal"]
        interpretation = state["interpretation"]
        logger.info(f"📋 Planner: Decomposing goal into steps...")

        plan = await self.planner.decompose(goal, interpretation)

        return {
            "plan": plan.to_dict(),
            "plan_title": plan.title,
            "current_step_index": 0,
            "status": "planning_complete",
            "logs": [{
                "agent": "Planner",
                "event": "plan_created",
                "data": {
                    "title": plan.title,
                    "total_steps": len(plan.steps),
                    "steps": [{"id": s.id, "action": s.action, "tool": s.tool} for s in plan.steps],
                },
            }],
        }
