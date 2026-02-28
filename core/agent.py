"""Main Autonomous Agent orchestrator for Synapse.

This is the central agent class that manages the full lifecycle:
Think → Plan → Execute → Verify → Adapt → Deliver
"""

import logging
import json
from typing import Callable, Awaitable

from .config import Config
from .memory import MemoryStore
from .planner import PlannerEngine, ExecutionPlan
from .executor import ExecutorEngine, StepResult
from .verifier import VerifierEngine
from .adaptor import AdaptorEngine
from .prompts import goal_interpretation_prompt, json_safe
from llm.provider import LLMProvider

logger = logging.getLogger(__name__)


class AutonomousAgent:
    """Main autonomous agent that accepts NL goals and delivers outcomes.

    Orchestrates the full Think → Plan → Execute → Verify → Adapt cycle.
    """

    def __init__(
        self,
        goal: str,
        config: Config = None,
        on_status: Callable[[str, dict], Awaitable[None]] | None = None,
        history: list[dict] = None,
    ):
        self.goal = goal
        self.history = history or []
        self.config = config or Config()
        self.on_status = on_status  # Callback for live status updates

        # Initialize LLM
        self.llm = LLMProvider(
            model=self.config.llm_model,
            api_key=self.config.google_api_key,
        )

        # Initialize engines
        self.planner = PlannerEngine(self.llm)
        self.executor = ExecutorEngine(self.llm)
        self.verifier = VerifierEngine(self.llm)
        self.adaptor = AdaptorEngine(self.llm)
        self.memory = MemoryStore(self.config.database_path)

        # State
        self.interpretation: dict = {}
        self.plan: ExecutionPlan | None = None
        self.step_results: list[StepResult] = []
        self.adaptation_count: int = 0
        self.status: str = "idle"
        self.goal_id: str = ""
        self.logs: list[dict] = []

    async def _emit(self, event: str, data: dict = None):
        """Emit a status update to the callback and log it."""
        self.status = event
        log_entry = {"event": event, "data": data or {}}
        self.logs.append(log_entry)
        logger.info(f"[{event}] {json.dumps(data or {}, default=str)[:200]}")

        if self.goal_id:
            await self.memory.add_log(self.goal_id, "AutonomousAgent", event, str(data)[:500], data)

        if self.on_status:
            try:
                await self.on_status(event, data or {})
            except Exception as e:
                logger.warning(f"Status callback error: {e}")

    async def run(self) -> dict:
        """Execute the full autonomous agent lifecycle.

        Returns:
            A dict with the final outcome including plan, results, and status.
        """
        # Create goal record
        goal_record = await self.memory.create_goal(self.goal)
        self.goal_id = goal_record.id
        await self._emit("started", {"goal": self.goal, "goal_id": self.goal_id})

        try:
            # ═══════════════════════════════════════
            # Phase 1: THINK — Interpret the goal
            # ═══════════════════════════════════════
            await self._emit("thinking", {"goal": self.goal})
            self.interpretation = await self._think()
            await self.memory.update_goal(self.goal_id, interpretation=self.interpretation, status="planning")
            await self._emit("thought_complete", {"interpretation": self.interpretation})

            # ═══════════════════════════════════════
            # Phase 2: PLAN — Decompose into steps
            # ═══════════════════════════════════════
            await self._emit("planning", {"interpretation": self.interpretation})
            self.plan = await self.planner.decompose(self.goal, self.interpretation, self.history)
            await self.memory.update_goal(self.goal_id, plan=self.plan.to_dict(), status="executing")
            await self._emit("plan_complete", {
                "plan_title": self.plan.title,
                "total_steps": len(self.plan.steps),
                "steps": [{"id": s.id, "action": s.action, "tool": s.tool} for s in self.plan.steps],
            })

            # ═══════════════════════════════════════
            # Phase 3: EXECUTE → VERIFY → ADAPT loop
            # ═══════════════════════════════════════
            await self._execute_plan()

            # ═══════════════════════════════════════
            # Phase 4: DELIVER — Compile final outcome
            # ═══════════════════════════════════════
            outcome = await self._deliver()
            await self.memory.update_goal(
                self.goal_id,
                status="completed",
                step_results=[r.to_dict() for r in self.step_results],
                final_outcome=outcome,
            )
            await self._emit("completed", outcome)
            return outcome

        except Exception as e:
            logger.error(f"Agent run failed: {e}", exc_info=True)
            await self.memory.update_goal(self.goal_id, status="failed")
            await self._emit("failed", {"error": str(e)})
            return {"status": "failed", "error": str(e), "goal_id": self.goal_id}

    async def _think(self) -> dict:
        """Phase 1: Interpret the natural language goal."""
        messages = goal_interpretation_prompt(self.goal, self.history)
        return await self.llm.chat_json(messages, temperature=0.2)

    async def _execute_plan(self):
        """Phase 3: Execute all steps with verification and adaptation."""
        context_parts = []
        step_index = 0

        while step_index < len(self.plan.steps):
            step = self.plan.steps[step_index]
            await self._emit("executing_step", {
                "step_id": step.id,
                "action": step.action,
                "tool": step.tool,
                "progress": f"{step_index + 1}/{len(self.plan.steps)}",
            })

            # Execute the step
            context = "\n\n".join(context_parts[-3:])  # Last 3 results for context
            result = await self.executor.execute(step, context)
            self.step_results.append(result)

            # Verify the step
            await self._emit("verifying_step", {"step_id": step.id, "status": result.status})
            verification = await self.verifier.verify(step, result)

            if verification.passed:
                await self._emit("step_passed", {
                    "step_id": step.id,
                    "score": verification.score,
                    "reason": verification.reason,
                })
                # Pass substantial context to downstream steps (2000 chars)
                context_parts.append(f"Step {step.id} ({step.action}):\n{str(result.output)[:2000]}")
                step_index += 1
            else:
                # Step failed — try to adapt
                await self._emit("step_failed", {
                    "step_id": step.id,
                    "reason": verification.reason,
                    "suggestions": verification.suggestions,
                })

                if self.adaptation_count >= self.config.max_adaptations:
                    await self._emit("max_adaptations_reached", {
                        "step_id": step.id,
                        "count": self.adaptation_count,
                    })
                    # Skip this step and continue
                    context_parts.append(f"Step {step.id} ({step.action}): SKIPPED - {verification.reason}")
                    step_index += 1
                    continue

                # Adapt
                self.adaptation_count += 1
                await self._emit("adapting", {
                    "step_id": step.id,
                    "adaptation_number": self.adaptation_count,
                })

                context = "\n".join(context_parts)
                self.plan, resume_from = await self.adaptor.replan(
                    self.goal, self.plan, step, verification.reason, context
                )
                await self.memory.update_goal(
                    self.goal_id,
                    plan=self.plan.to_dict(),
                    adaptation_count=self.adaptation_count,
                )
                await self._emit("plan_revised", {
                    "new_total_steps": len(self.plan.steps),
                    "resume_from": resume_from,
                })

                # Find the new step index to resume from
                step_index = next(
                    (i for i, s in enumerate(self.plan.steps) if s.id >= resume_from),
                    step_index + 1,
                )

    async def _deliver(self) -> dict:
        """Phase 4: Compile the final outcome."""
        successful = [r for r in self.step_results if r.status == "completed"]
        failed = [r for r in self.step_results if r.status != "completed"]

        # Compile all step outputs with generous truncation
        step_outputs = "\n\n".join(
            f"### Step {r.step_id} Result:\n{str(r.output)[:1500]}"
            for r in successful
        )

        # Use LLM to synthesize a final report
        summary_prompt = [
            {
                "role": "system",
                "content": (
                    "You are a report compiler. Create a polished, comprehensive final deliverable "
                    "by synthesizing ALL the step results below.\n\n"
                    "RULES:\n"
                    "1. USE the actual data and facts from the step results — do NOT make up new content\n"
                    "2. Organize with markdown headers (##), bullet points, and bold text\n"
                    "3. Include ALL specific details, facts, names, and data from the steps\n"
                    "4. Make it feel like a professional report, not a generic summary\n"
                    "5. The report should be at least 500 words"
                )
            },
            {
                "role": "user",
                "content": (
                    f"Original goal: {self.goal}\n\n"
                    f"All execution results:\n{step_outputs}\n\n"
                    "Now synthesize these results into one comprehensive, well-organized final deliverable."
                ),
            },
        ]
        final_report = await self.llm.chat(summary_prompt, temperature=0.3)

        return {
            "status": "completed",
            "goal_id": self.goal_id,
            "goal": self.goal,
            "plan_title": self.plan.title if self.plan else "",
            "total_steps": len(self.plan.steps) if self.plan else 0,
            "steps_completed": len(successful),
            "steps_failed": len(failed),
            "adaptations": self.adaptation_count,
            "final_report": final_report,
            "step_results": [r.to_dict() for r in self.step_results],
        }
