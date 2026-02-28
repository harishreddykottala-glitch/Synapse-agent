"""Thinker Agent — Goal Interpreter.

Accepts natural language goals and produces structured interpretations.
Maps to the 'Think' phase of Think → Plan → Deliver.
"""

import logging
from .state import AgentState
from core.prompts import goal_interpretation_prompt
from llm.provider import LLMProvider

logger = logging.getLogger(__name__)


class ThinkerAgent:
    """Interprets user goals into structured understanding."""

    def __init__(self, llm: LLMProvider = None):
        self.llm = llm or LLMProvider()

    async def run(self, state: AgentState) -> dict:
        """Interpret the goal and classify it.

        Args:
            state: Current agent state with 'goal' set.

        Returns:
            State updates with interpretation and logs.
        """
        goal = state["goal"]
        logger.info(f"🧠 Thinker: Interpreting goal: {goal[:80]}...")

        messages = goal_interpretation_prompt(goal)
        interpretation = await self.llm.chat_json(messages, temperature=0.2)

        return {
            "interpretation": interpretation,
            "status": "thinking_complete",
            "logs": [{
                "agent": "Thinker",
                "event": "goal_interpreted",
                "data": {
                    "domain": interpretation.get("domain", "general"),
                    "objective": interpretation.get("objective", goal),
                    "complexity": interpretation.get("complexity", "medium"),
                },
            }],
        }
