"""Agent State definitions for the LangGraph workflow."""

from typing import TypedDict, Annotated
import operator


class AgentState(TypedDict):
    """State that flows through the LangGraph agent workflow.

    Each agent node reads from and writes to this shared state.
    """
    # Input
    goal: str                           # Original natural language goal
    goal_id: str                        # Unique ID for persistence

    # Thinker output
    interpretation: dict                # Structured understanding of the goal

    # Planner output
    plan: dict                          # Execution plan with steps
    plan_title: str                     # Human-readable plan title

    # Executor state
    current_step_index: int             # Which step we're executing (0-indexed)
    step_results: Annotated[list, operator.add]  # Accumulated step results

    # Verifier output
    verification_status: str            # "passed" | "failed"
    verification_reason: str            # Why it passed/failed
    verification_suggestions: list      # Suggestions for improvement

    # Adaptor state
    adaptation_count: int               # How many times we've re-planned
    max_adaptations: int                # Safety limit (default: 3)

    # Final output
    final_outcome: dict                 # The delivered result
    status: str                         # Current agent phase

    # Streaming
    logs: Annotated[list, operator.add] # Live log entries for frontend
