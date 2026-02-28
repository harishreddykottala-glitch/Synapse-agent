"""Adaptor Engine for Synapse Agent.

Re-plans execution when steps fail, using LLM-based adaptive reasoning.
"""

import logging
from .planner import ExecutionPlan, Step
from .prompts import replan_prompt, json_safe

logger = logging.getLogger(__name__)


class AdaptorEngine:
    """Re-plans execution when steps fail or produce unexpected results."""

    def __init__(self, llm):
        self.llm = llm

    async def replan(
        self,
        goal: str,
        plan: ExecutionPlan,
        failed_step: Step,
        failure_reason: str,
        context: str,
    ) -> tuple[ExecutionPlan, int]:
        """Create a revised execution plan after a step fails.

        Args:
            goal: Original natural language goal.
            plan: The current execution plan.
            failed_step: The step that failed.
            failure_reason: Why it failed.
            context: Accumulated context from previous successful steps.

        Returns:
            Tuple of (revised ExecutionPlan, step_id to resume from).
        """
        logger.info(f"Adapting plan after step {failed_step.id} failed: {failure_reason[:80]}")

        plan_dict = plan.to_dict()
        step_dict = {
            "id": failed_step.id,
            "action": failed_step.action,
            "tool": failed_step.tool,
            "params": failed_step.params,
        }

        messages = replan_prompt(goal, plan_dict, step_dict, failure_reason, context)

        try:
            response = await self.llm.chat_json(messages, temperature=0.4)

            strategy = response.get("strategy", 1)
            explanation = response.get("explanation", "")
            revised_steps_raw = response.get("revised_steps", [])
            resume_from = response.get("resume_from_step", failed_step.id)

            logger.info(f"Adaptation strategy {strategy}: {explanation[:80]}")

            # Build revised steps
            revised_steps = []
            for s in revised_steps_raw:
                revised_steps.append(Step(
                    id=s.get("id", len(revised_steps) + 1),
                    action=s.get("action", ""),
                    tool=s.get("tool", "llm_reasoning"),
                    params=s.get("params", {}),
                    depends_on=s.get("depends_on", []),
                    expected_output=s.get("expected_output", ""),
                    verification_criteria=s.get("verification_criteria", ""),
                ))

            # Keep completed steps, replace remaining
            completed_steps = [s for s in plan.steps if s.id < failed_step.id]
            revised_plan = ExecutionPlan(
                title=plan.title + " (Revised)",
                estimated_duration=plan.estimated_duration,
                steps=completed_steps + revised_steps,
            )

            return revised_plan, resume_from

        except Exception as e:
            logger.error(f"Adaptation failed: {e}")
            # Simple retry: just return the same plan, resume from failed step
            return plan, failed_step.id
