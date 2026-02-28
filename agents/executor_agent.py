"""Executor Agent — Step Execution.

Executes the current step in the plan using tools or LLM reasoning.
Maps to the 'Deliver' phase — the action-taking agent.
"""

import logging
from .state import AgentState
from core.executor import ExecutorEngine
from core.planner import Step
from llm.provider import LLMProvider

logger = logging.getLogger(__name__)


class ExecutorAgent:
    """Executes individual plan steps using tools and LLM."""

    def __init__(self, llm: LLMProvider = None):
        self.llm = llm or LLMProvider()
        self.executor = ExecutorEngine(self.llm)

    async def run(self, state: AgentState) -> dict:
        """Execute the current step in the plan.

        Args:
            state: Current state with 'plan' and 'current_step_index'.

        Returns:
            State updates with step result and logs.
        """
        plan = state["plan"]
        step_index = state["current_step_index"]
        steps = plan.get("steps", [])

        if step_index >= len(steps):
            return {
                "status": "all_steps_complete",
                "verification_status": "passed",
                "logs": [{"agent": "Executor", "event": "all_steps_done", "data": {}}],
            }

        step_data = steps[step_index]
        step = Step(
            id=step_data.get("id", step_index + 1),
            action=step_data.get("action", ""),
            tool=step_data.get("tool", "llm_reasoning"),
            params=step_data.get("params", {}),
            depends_on=step_data.get("depends_on", []),
            expected_output=step_data.get("expected_output", ""),
            verification_criteria=step_data.get("verification_criteria", ""),
        )

        logger.info(f"⚡ Executor: Running step {step.id}: {step.action}")

        # Build context from previous results
        context_parts = []
        for r in state.get("step_results", []):
            if isinstance(r, dict):
                context_parts.append(f"Step {r.get('step_id')}: {str(r.get('output', ''))[:200]}")
        context = "\n".join(context_parts[-5:])

        result = await self.executor.execute(step, context)

        return {
            "step_results": [result.to_dict()],
            "status": "step_executed",
            "logs": [{
                "agent": "Executor",
                "event": "step_executed",
                "data": {
                    "step_id": step.id,
                    "action": step.action,
                    "status": result.status,
                    "output_preview": result.output[:200] if result.output else "",
                },
            }],
        }
