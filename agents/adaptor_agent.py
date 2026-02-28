"""Adaptor Agent — Adaptive Re-planning.

Re-plans execution when steps fail, creating revised strategies.
Implements the adaptive loop in Execute → Verify → Adapt.
"""

import logging
from .state import AgentState
from core.adaptor import AdaptorEngine
from core.planner import ExecutionPlan, Step
from llm.provider import LLMProvider

logger = logging.getLogger(__name__)


class AdaptorAgent:
    """Re-plans execution when steps fail."""

    def __init__(self, llm: LLMProvider = None):
        self.llm = llm or LLMProvider()
        self.adaptor = AdaptorEngine(self.llm)

    async def run(self, state: AgentState) -> dict:
        """Adapt the plan after a verification failure.

        Args:
            state: Current state with plan, failed step info, and context.

        Returns:
            State updates with revised plan and logs.
        """
        plan_dict = state["plan"]
        step_index = state["current_step_index"]
        steps = plan_dict.get("steps", [])
        adaptation_count = state.get("adaptation_count", 0)
        failure_reason = state.get("verification_reason", "Unknown failure")

        if step_index >= len(steps):
            return {"status": "nothing_to_adapt", "logs": []}

        step_data = steps[step_index]
        failed_step = Step(
            id=step_data.get("id", step_index + 1),
            action=step_data.get("action", ""),
            tool=step_data.get("tool", "llm_reasoning"),
            params=step_data.get("params", {}),
        )

        plan = ExecutionPlan.from_dict(plan_dict)

        logger.info(f"🔄 Adaptor: Re-planning after step {failed_step.id} failure")

        # Build context
        context_parts = []
        for r in state.get("step_results", []):
            if isinstance(r, dict) and r.get("status") == "completed":
                context_parts.append(f"Step {r.get('step_id')}: {str(r.get('output', ''))[:200]}")
        context = "\n".join(context_parts)

        revised_plan, resume_from = await self.adaptor.replan(
            state["goal"], plan, failed_step, failure_reason, context
        )

        # Find new step index
        new_index = next(
            (i for i, s in enumerate(revised_plan.steps) if s.id >= resume_from),
            step_index,
        )

        return {
            "plan": revised_plan.to_dict(),
            "plan_title": revised_plan.title,
            "current_step_index": new_index,
            "adaptation_count": adaptation_count + 1,
            "status": "plan_adapted",
            "logs": [{
                "agent": "Adaptor",
                "event": "plan_revised",
                "data": {
                    "adaptation_number": adaptation_count + 1,
                    "new_total_steps": len(revised_plan.steps),
                    "resume_from_step": resume_from,
                    "strategy": "adaptive_replanning",
                },
            }],
        }
