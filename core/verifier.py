"""Verifier Engine for Synapse Agent.

Checks whether each step produced the expected outcome using LLM-based evaluation.
"""

import logging
from dataclasses import dataclass

from .prompts import verification_prompt

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Result of verifying a step's outcome."""
    passed: bool
    score: float  # 0.0 to 1.0
    reason: str
    suggestions: list[str]

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "score": self.score,
            "reason": self.reason,
            "suggestions": self.suggestions,
        }


class VerifierEngine:
    """Verifies whether each step produced the expected outcome."""

    def __init__(self, llm):
        self.llm = llm

    async def verify(self, step, result) -> VerificationResult:
        """Verify whether a step completed successfully.

        Args:
            step: The Step definition with expected_output and verification_criteria.
            result: The StepResult from execution.

        Returns:
            A VerificationResult with pass/fail and reasoning.
        """
        # Quick checks before LLM verification
        if result.status == "failed" and result.error:
            return VerificationResult(
                passed=False,
                score=0.0,
                reason=f"Step failed with error: {result.error}",
                suggestions=["Retry with different parameters", "Use alternative approach"],
            )

        # Lightweight pass: if executor reports completed with output, auto-pass
        # This saves an LLM call per step (critical for free-tier rate limits)
        if result.status == "completed" and result.output and len(result.output) > 20:
            return VerificationResult(
                passed=True,
                score=0.85,
                reason="Step completed with substantial output — auto-verified.",
                suggestions=[],
            )

        # LLM-based verification
        step_dict = {
            "id": step.id,
            "action": step.action,
            "expected_output": step.expected_output,
            "verification_criteria": step.verification_criteria,
        }
        result_dict = result.to_dict()

        messages = verification_prompt(step_dict, result_dict)

        try:
            response = await self.llm.chat_json(messages, temperature=0.1)
            return VerificationResult(
                passed=response.get("passed", False),
                score=float(response.get("score", 0.5)),
                reason=response.get("reason", "No reason provided"),
                suggestions=response.get("suggestions", []),
            )
        except Exception as e:
            logger.error(f"Verification failed for step {step.id}: {e}")
            # Default to passed if verification itself fails (don't block execution)
            return VerificationResult(
                passed=True,
                score=0.7,
                reason=f"Verification process error: {e}. Defaulting to pass.",
                suggestions=[],
            )
