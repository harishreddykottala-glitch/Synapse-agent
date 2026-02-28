"""Executor Engine for Synapse Agent.

Executes plan steps using the tool registry and LLM reasoning.
Includes smart parameter extraction from step actions.
"""

import logging
from dataclasses import dataclass, field

from .prompts import step_execution_prompt, json_safe
from .tools import get_tool
from .tools.base import ToolResult

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    """Result of executing a single step."""
    step_id: int
    status: str  # completed | failed | partial
    output: str = ""
    artifacts: list = field(default_factory=list)
    notes: str = ""
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "status": self.status,
            "output": str(self.output),
            "artifacts": self.artifacts,
            "notes": self.notes,
            "error": self.error,
        }


class ExecutorEngine:
    """Executes plan steps using registered tools and LLM reasoning."""

    def __init__(self, llm):
        self.llm = llm

    def _enrich_params(self, step) -> dict:
        """Smart parameter extraction — infer missing tool params from step action.

        Many LLMs generate steps with empty params but descriptive actions.
        This method backfills common params from the step action text.
        """
        params = dict(step.params) if step.params else {}

        # For web_search: extract query from action or params
        if step.tool == "web_search" and not params.get("query"):
            params["query"] = step.action

        # For knowledge_base: extract topic from action or params
        if step.tool == "knowledge_base":
            if not params.get("topic") and not params.get("query"):
                # Try to infer topic from common keywords in the action
                action_lower = step.action.lower()
                for keyword in ["gate", "exam", "study", "fitness", "exercise"]:
                    if keyword in action_lower:
                        if "gate" in action_lower or "exam" in action_lower:
                            params["topic"] = "gate_exam"
                        elif "study" in action_lower:
                            params["topic"] = "study_techniques"
                        elif "fitness" in action_lower or "exercise" in action_lower:
                            params["topic"] = "fitness_basics"
                        break
                if not params.get("topic"):
                    params["query"] = step.action

        # For calculator: extract expression
        if step.tool == "calculator" and not params.get("expression"):
            params["expression"] = step.action

        # For calendar_tool: extract operation
        if step.tool == "calendar_tool" and not params.get("operation"):
            params["operation"] = "schedule"
            if not params.get("description"):
                params["description"] = step.action

        return params

    async def execute(self, step, context: str = "") -> StepResult:
        """Execute a single plan step."""
        logger.info(f"Executing step {step.id}: {step.action}")

        # Try tool execution first with enriched params
        if step.tool and step.tool != "llm_reasoning":
            tool = get_tool(step.tool)
            if tool:
                try:
                    enriched_params = self._enrich_params(step)
                    tool_result = await tool.execute(enriched_params)
                    if tool_result.success:
                        return StepResult(
                            step_id=step.id,
                            status="completed",
                            output=tool_result.output,
                            artifacts=[],
                            notes=f"Executed via {step.tool} tool",
                        )
                    else:
                        logger.warning(f"Tool {step.tool} failed: {tool_result.error}")
                        # Fall through to LLM reasoning
                except Exception as e:
                    logger.error(f"Tool execution error: {e}")
                    # Fall through to LLM reasoning

        # Use LLM reasoning (primary tool or fallback after tool failure)
        # The LLM should PRODUCE actual content, not just describe what it would do
        try:
            step_dict = {
                "id": step.id,
                "action": step.action,
                "tool": step.tool,
                "params": step.params,
                "expected_output": step.expected_output,
            }
            messages = step_execution_prompt(step_dict, context)
            response = await self.llm.chat_json(messages, temperature=0.4)

            output = response.get("output", "")
            # Ensure output is a string
            if not isinstance(output, str):
                import json
                output = json.dumps(output, indent=2) if output else ""

            return StepResult(
                step_id=step.id,
                status=response.get("status", "completed"),
                output=output,
                artifacts=response.get("artifacts", []),
                notes=response.get("notes", ""),
            )
        except Exception as e:
            logger.error(f"Step {step.id} execution failed: {e}")
            return StepResult(
                step_id=step.id,
                status="failed",
                output="",
                error=str(e),
                notes="Both tool and LLM execution failed",
            )
