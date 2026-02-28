"""Verifier Agent — Step Verification.

Checks whether the most recent step completed successfully.
Acts as the quality gate in the Execute → Verify → Adapt loop.
"""

import logging
from .state import AgentState
from core.verifier import VerifierEngine
from core.planner import Step
from core.executor import StepResult
from llm.provider import LLMProvider

logger = logging.getLogger(__name__)


class VerifierAgent:
    """Verifies step outcomes against expected results."""

    def __init__(self, llm: LLMProvider = None):
        self.llm = llm or LLMProvider()
        self.verifier = VerifierEngine(self.llm)

    async def run(self, state: AgentState) -> dict:
        """Verify the most recently executed step.

        Args:
            state: Current state with step results and plan.

        Returns:
            State updates with verification status and logs.
        """
        plan = state["plan"]
        step_index = state["current_step_index"]
        steps = plan.get("steps", [])
        step_results = state.get("step_results", [])

        # If all steps are done
        if step_index >= len(steps):
            return {
                "verification_status": "passed",
                "verification_reason": "All steps completed",
                "current_step_index": step_index,
                "status": "all_verified",
                "logs": [{"agent": "Verifier", "event": "all_verified", "data": {}}],
            }

        step_data = steps[step_index]
        step = Step(
            id=step_data.get("id", step_index + 1),
            action=step_data.get("action", ""),
            tool=step_data.get("tool", "llm_reasoning"),
            expected_output=step_data.get("expected_output", ""),
            verification_criteria=step_data.get("verification_criteria", ""),
        )

        # Get the latest result
        latest_result = step_results[-1] if step_results else None
        if not latest_result:
            return {
                "verification_status": "failed",
                "verification_reason": "No result to verify",
                "status": "verification_failed",
                "logs": [{"agent": "Verifier", "event": "no_result", "data": {}}],
            }

        # Convert dict to StepResult if needed
        if isinstance(latest_result, dict):
            result_obj = StepResult(
                step_id=latest_result.get("step_id", step.id),
                status=latest_result.get("status", "failed"),
                output=latest_result.get("output", ""),
                artifacts=latest_result.get("artifacts", []),
                notes=latest_result.get("notes", ""),
                error=latest_result.get("error"),
            )
        else:
            result_obj = latest_result

        logger.info(f"🔍 Verifier: Checking step {step.id}")
        verification = await self.verifier.verify(step, result_obj)

        if verification.passed:
            return {
                "verification_status": "passed",
                "verification_reason": verification.reason,
                "verification_suggestions": [],
                "current_step_index": step_index + 1,  # Move to next step
                "status": "step_verified",
                "logs": [{
                    "agent": "Verifier",
                    "event": "step_passed",
                    "data": {"step_id": step.id, "score": verification.score, "reason": verification.reason},
                }],
            }
        else:
            return {
                "verification_status": "failed",
                "verification_reason": verification.reason,
                "verification_suggestions": verification.suggestions,
                "status": "step_verification_failed",
                "logs": [{
                    "agent": "Verifier",
                    "event": "step_failed",
                    "data": {"step_id": step.id, "score": verification.score, "reason": verification.reason},
                }],
            }
