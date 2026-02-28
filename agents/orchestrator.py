"""Master Orchestrator — LangGraph Workflow Builder.

Builds and runs the multi-agent workflow using LangGraph StateGraph.
Equivalent to GPT-Researcher's ChiefEditorAgent.

Workflow: START → Thinker → Planner → Executor → Verifier → [Adaptor] → END
"""

import logging
from langgraph.graph import StateGraph, END

from .state import AgentState
from .thinker import ThinkerAgent
from .planner_agent import PlannerAgent
from .executor_agent import ExecutorAgent
from .verifier_agent import VerifierAgent
from .adaptor_agent import AdaptorAgent
from llm.provider import LLMProvider
from core.config import Config

logger = logging.getLogger(__name__)


class MasterOrchestrator:
    """Builds and runs the LangGraph multi-agent workflow.

    The workflow follows: Think → Plan → Execute → Verify → Adapt → Deliver
    with conditional routing based on verification outcomes.
    """

    def __init__(self, config: Config = None):
        self.config = config or Config()
        self.llm = LLMProvider(
            model=self.config.llm_model,
            api_key=self.config.google_api_key,
        )

    def _initialize_agents(self):
        """Create all agent instances."""
        return {
            "thinker": ThinkerAgent(self.llm),
            "planner": PlannerAgent(self.llm),
            "executor": ExecutorAgent(self.llm),
            "verifier": VerifierAgent(self.llm),
            "adaptor": AdaptorAgent(self.llm),
        }

    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph StateGraph with all agent nodes and edges."""
        agents = self._initialize_agents()
        workflow = StateGraph(AgentState)

        # ═══ Add nodes ═══
        workflow.add_node("thinker", agents["thinker"].run)
        workflow.add_node("planner", agents["planner"].run)
        workflow.add_node("executor", agents["executor"].run)
        workflow.add_node("verifier", agents["verifier"].run)
        workflow.add_node("adaptor", agents["adaptor"].run)

        # ═══ Add edges ═══
        workflow.set_entry_point("thinker")
        workflow.add_edge("thinker", "planner")
        workflow.add_edge("planner", "executor")
        workflow.add_edge("executor", "verifier")

        # Conditional routing after verification
        workflow.add_conditional_edges(
            "verifier",
            self._route_after_verification,
            {
                "next_step": "executor",      # More steps to execute
                "adapt": "adaptor",            # Step failed, retry
                "done": END,                   # All steps passed
                "force_done": END,             # Max adaptations reached
            },
        )

        # After adaptation, retry the executor
        workflow.add_edge("adaptor", "executor")

        return workflow

    def _route_after_verification(self, state: AgentState) -> str:
        """Determine the next node after verification.

        Returns:
            "next_step" — more steps to run
            "adapt" — step failed, within adaptation budget
            "done" — all steps verified successfully
            "force_done" — exceeded max adaptations, stop
        """
        verification_status = state.get("verification_status", "passed")
        step_index = state.get("current_step_index", 0)
        plan = state.get("plan", {})
        total_steps = len(plan.get("steps", []))
        adaptation_count = state.get("adaptation_count", 0)
        max_adaptations = state.get("max_adaptations", self.config.max_adaptations)

        if verification_status == "passed":
            if step_index >= total_steps:
                return "done"
            return "next_step"
        else:
            if adaptation_count >= max_adaptations:
                return "force_done"
            return "adapt"

    def compile(self):
        """Compile the workflow into a runnable chain."""
        workflow = self._build_workflow()
        return workflow.compile()

    async def run(self, goal: str, goal_id: str = "") -> dict:
        """Run the full multi-agent workflow for a goal.

        Args:
            goal: Natural language goal from the user.
            goal_id: Optional unique ID for persistence.

        Returns:
            Final AgentState dict with all results.
        """
        chain = self.compile()

        initial_state: AgentState = {
            "goal": goal,
            "goal_id": goal_id or "",
            "interpretation": {},
            "plan": {},
            "plan_title": "",
            "current_step_index": 0,
            "step_results": [],
            "verification_status": "pending",
            "verification_reason": "",
            "verification_suggestions": [],
            "adaptation_count": 0,
            "max_adaptations": self.config.max_adaptations,
            "final_outcome": {},
            "status": "started",
            "logs": [],
        }

        logger.info(f"🚀 Orchestrator: Starting workflow for: {goal[:80]}...")
        result = await chain.ainvoke(initial_state)
        logger.info(f"✅ Orchestrator: Workflow complete. Status: {result.get('status')}")

        return result
