"""Planner Engine for Synapse Agent.

Decomposes natural language goals into structured, multi-step execution plans
using LLM-based reasoning. Includes fallback templates for small models.
"""

import logging
from dataclasses import dataclass, field

from .prompts import plan_decomposition_prompt
from .tools import get_available_tools

logger = logging.getLogger(__name__)

MIN_STEPS = 5  # Minimum steps to generate a useful plan


@dataclass
class Step:
    """A single executable step in the plan."""
    id: int
    action: str
    tool: str
    params: dict = field(default_factory=dict)
    depends_on: list[int] = field(default_factory=list)
    expected_output: str = ""
    verification_criteria: str = ""


@dataclass
class ExecutionPlan:
    """A structured execution plan with ordered steps."""
    title: str = ""
    estimated_duration: str = ""
    steps: list[Step] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "ExecutionPlan":
        """Parse an ExecutionPlan from the LLM's JSON response."""
        steps = []
        for s in data.get("steps", []):
            steps.append(Step(
                id=s.get("id", len(steps) + 1),
                action=s.get("action", "Unknown action"),
                tool=s.get("tool", "llm_reasoning"),
                params=s.get("params", {}) or {},
                depends_on=s.get("depends_on", []),
                expected_output=s.get("expected_output", ""),
                verification_criteria=s.get("verification_criteria", ""),
            ))
        return cls(
            title=data.get("plan_title", "Execution Plan"),
            estimated_duration=data.get("estimated_duration", "Unknown"),
            steps=steps,
            raw=data,
        )

    def to_dict(self) -> dict:
        return {
            "plan_title": self.title,
            "estimated_duration": self.estimated_duration,
            "steps": [
                {
                    "id": s.id, "action": s.action, "tool": s.tool,
                    "params": s.params, "depends_on": s.depends_on,
                    "expected_output": s.expected_output,
                    "verification_criteria": s.verification_criteria,
                }
                for s in self.steps
            ],
        }


# ═══════════════════════════════════════
# Fallback plan templates for small models
# ═══════════════════════════════════════

PLAN_TEMPLATES = {
    "study_planning": {
        "plan_title": "Comprehensive Study Plan",
        "estimated_duration": "30 minutes",
        "steps": [
            {"id": 1, "action": "Research the exam syllabus, format, and marking scheme", "tool": "knowledge_base", "params": {"topic": "gate_exam"}, "depends_on": [], "expected_output": "Complete exam syllabus and details", "verification_criteria": "Syllabus covers all subjects"},
            {"id": 2, "action": "Identify key study techniques and learning strategies", "tool": "knowledge_base", "params": {"topic": "study_techniques"}, "depends_on": [], "expected_output": "List of effective study methods", "verification_criteria": "At least 3 study techniques identified"},
            {"id": 3, "action": "Create a month-by-month study schedule with specific daily targets", "tool": "llm_reasoning", "params": {}, "depends_on": [1, 2], "expected_output": "Detailed 3-month study schedule with weekly and daily breakdown", "verification_criteria": "Schedule covers all subjects with time allocation"},
            {"id": 4, "action": "Design a practice test and revision strategy for the final month", "tool": "llm_reasoning", "params": {}, "depends_on": [3], "expected_output": "Mock test schedule and revision plan", "verification_criteria": "Includes at least 10 mock tests"},
            {"id": 5, "action": "Create a list of recommended books, resources, and online courses for each subject", "tool": "llm_reasoning", "params": {}, "depends_on": [1], "expected_output": "Resource list organized by subject", "verification_criteria": "Resources for each subject area"},
            {"id": 6, "action": "Compile the complete study plan into a final actionable document", "tool": "llm_reasoning", "params": {}, "depends_on": [3, 4, 5], "expected_output": "Final comprehensive study plan document", "verification_criteria": "Complete plan is actionable and realistic"},
        ],
    },
    "health": {
        "plan_title": "Personalized Health & Fitness Plan",
        "estimated_duration": "25 minutes",
        "steps": [
            {"id": 1, "action": "Research fitness fundamentals and training principles", "tool": "knowledge_base", "params": {"topic": "fitness_basics"}, "depends_on": [], "expected_output": "Core fitness components and guidelines", "verification_criteria": "Covers cardio, strength, flexibility"},
            {"id": 2, "action": "Create a weekly workout schedule with specific exercises for each day", "tool": "llm_reasoning", "params": {}, "depends_on": [1], "expected_output": "7-day workout plan with exercises, sets, reps", "verification_criteria": "Each day has specific exercises"},
            {"id": 3, "action": "Design a nutrition plan with meal recommendations and macros", "tool": "llm_reasoning", "params": {}, "depends_on": [], "expected_output": "Daily meal plan with calories and macros", "verification_criteria": "Includes breakfast, lunch, dinner, snacks"},
            {"id": 4, "action": "Create progress tracking milestones and measurement criteria", "tool": "llm_reasoning", "params": {}, "depends_on": [2, 3], "expected_output": "Weekly milestones and tracking sheet", "verification_criteria": "Measurable metrics defined"},
            {"id": 5, "action": "Compile the complete fitness plan into a final actionable document", "tool": "llm_reasoning", "params": {}, "depends_on": [2, 3, 4], "expected_output": "Complete 30-day fitness and nutrition plan", "verification_criteria": "Plan is comprehensive and actionable"},
        ],
    },
    "default": {
        "plan_title": "Goal Execution Plan",
        "estimated_duration": "20 minutes",
        "steps": [
            {"id": 1, "action": "Research and gather all relevant information about the goal", "tool": "web_search", "params": {"query": ""}, "depends_on": [], "expected_output": "Comprehensive research findings", "verification_criteria": "Key information gathered"},
            {"id": 2, "action": "Analyze the gathered information and identify key factors", "tool": "llm_reasoning", "params": {}, "depends_on": [1], "expected_output": "Analysis of key factors and considerations", "verification_criteria": "Main factors identified"},
            {"id": 3, "action": "Create a detailed action plan with specific steps and timelines", "tool": "llm_reasoning", "params": {}, "depends_on": [2], "expected_output": "Detailed action plan", "verification_criteria": "Plan has specific actions and deadlines"},
            {"id": 4, "action": "Identify potential risks and create mitigation strategies", "tool": "llm_reasoning", "params": {}, "depends_on": [3], "expected_output": "Risk assessment and mitigation plan", "verification_criteria": "Risks identified with solutions"},
            {"id": 5, "action": "Compile everything into a final comprehensive deliverable", "tool": "llm_reasoning", "params": {}, "depends_on": [3, 4], "expected_output": "Final deliverable document", "verification_criteria": "Complete and actionable"},
        ],
    },
}


def _get_fallback_plan(goal: str, interpretation: dict) -> ExecutionPlan:
    """Generate a fallback plan from templates when the LLM under-generates."""
    domain = interpretation.get("domain", "general") if isinstance(interpretation, dict) else "general"

    # Match domain to template
    if "study" in domain or "exam" in domain or "education" in domain:
        template = PLAN_TEMPLATES["study_planning"]
    elif "health" in domain or "fitness" in domain:
        template = PLAN_TEMPLATES["health"]
    else:
        template = PLAN_TEMPLATES["default"]

    # Customize the template with the actual goal
    import copy
    plan_data = copy.deepcopy(template)

    # Set web_search query for default template
    for step in plan_data["steps"]:
        if step["tool"] == "web_search" and not step["params"].get("query"):
            step["params"]["query"] = goal

    plan = ExecutionPlan.from_dict(plan_data)
    plan.title = f"{plan.title} — {goal[:50]}"
    logger.info(f"Using fallback template: {plan.title} ({len(plan.steps)} steps)")
    return plan


class PlannerEngine:
    """Decomposes natural language goals into multi-step execution plans."""

    def __init__(self, llm):
        self.llm = llm

    async def decompose(self, goal: str, interpretation: dict, history: list[dict] = None) -> ExecutionPlan:
        """LLM call: break goal into ordered steps with dependencies."""
        tool_names = get_available_tools()

        # Build prompt
        messages = plan_decomposition_prompt(goal, interpretation, tool_names, history)

        logger.info(f"Generating execution plan for: {goal[:80]}...")
        response = await self.llm.chat_json(messages, temperature=0.3)

        plan = ExecutionPlan.from_dict(response)

        # If the LLM generated too few steps, use fallback template
        if len(plan.steps) < MIN_STEPS:
            logger.warning(
                f"LLM generated only {len(plan.steps)} steps (min: {MIN_STEPS}). "
                f"Using fallback template."
            )
            plan = _get_fallback_plan(goal, interpretation)

        logger.info(f"Plan generated: {plan.title} ({len(plan.steps)} steps)")
        return plan
