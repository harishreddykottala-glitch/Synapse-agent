"""LLM Prompts for Synapse Agent system.

All prompts used by the autonomous agent lifecycle:
Think → Plan → Execute → Verify → Adapt
"""


def goal_interpretation_prompt(goal: str, history: list[dict] = None) -> list[dict]:
    """Prompt for the Thinker agent to interpret a natural language goal."""
    history_str = ""
    if history:
        history_str = "Prior Conversation Context:\n" + "\n".join(
            [f"{m.get('role', 'unknown').upper()}: {m.get('content', '')}" for m in history]
        ) + "\n\n"

    return [
        {
            "role": "system",
            "content": (
                "You are an expert goal analyst. Your job is to interpret a user's natural language goal "
                "and produce a structured understanding of what they want to achieve.\n\n"
                "You must return a JSON object with these fields:\n"
                '- "domain": The category (e.g., "study_planning", "finance", "health", "task_management", "general")\n'
                '- "objective": A clear, one-sentence restatement of the goal\n'
                '- "constraints": A list of constraints or requirements mentioned\n'
                '- "success_criteria": A list of measurable criteria that define success\n'
                '- "context_needed": A list of information types the agent needs to gather\n'
                '- "complexity": "low" | "medium" | "high"\n\n'
                "Return ONLY valid JSON, no markdown."
            ),
        },
        {
            "role": "user",
            "content": f"{history_str}Interpret this new goal/follow-up:\n\n{goal}",
        },
    ]

def plan_decomposition_prompt(
    goal: str, interpretation: dict, available_tools: list[str], history: list[dict] = None
) -> list[dict]:
    """Prompt for the Planner agent to decompose a goal into executable steps."""
    tools_str = ", ".join(available_tools) if available_tools else "web_search, calculator, calendar, knowledge_base"
    
    history_str = ""
    if history:
        history_str = "Prior Conversation Context / Previous Plans:\n" + "\n".join(
            [f"{m.get('role', 'unknown').upper()}: {m.get('content', '')}" for m in history[-5:]] # Keep last 5 for context limit
        ) + "\n\n"

    return [
        {
            "role": "system",
            "content": (
                "You are an expert task planner. Given a goal, decompose it into executable steps.\n"
                "If the user is asking for a modification or follow-up to a previous plan, you MUST refer to the prior context below "
                "and adapt/modify elements accordingly instead of starting from scratch.\n\n"
                f"Available tools: {tools_str}\n\n"
                "IMPORTANT RULES for tool params:\n"
                '- web_search: ALWAYS include {"query": "search terms"} in params\n'
                '- knowledge_base: ALWAYS include {"topic": "gate_exam"} or {"topic": "study_techniques"} or {"topic": "fitness_basics"}\n'
                '- calculator: ALWAYS include {"expression": "math expression"}\n'
                '- calendar: ALWAYS include {"operation": "schedule", "description": "text"}\n'
                '- llm_reasoning: Use for creating content, plans, schedules, or analysis\n\n'
                "Use llm_reasoning for most content-creation steps. Use tools only for data gathering.\n"
                "Create 5-8 focused steps maximum.\n\n"
                "Return JSON with:\n"
                '{"plan_title": "...", "estimated_duration": "...", "steps": [{"id": 1, "action": "...", "tool": "...", "params": {...}, "depends_on": [], "expected_output": "...", "verification_criteria": "..."}]}\n\n'
                "Return ONLY valid JSON."
            ),
        },
        {
            "role": "user",
            "content": (
                f"{history_str}"
                f"Goal: {goal}\n\n"
                f"Interpretation: {json_safe(interpretation)}\n\n"
                "Create or modify the execution plan based on the above."
            ),
        },
    ]


def step_execution_prompt(step: dict, context: str) -> list[dict]:
    """Prompt for the Executor agent to carry out a single step."""
    context_instruction = ""
    if context and context != "No previous context.":
        context_instruction = (
            "\n\nIMPORTANT: You MUST use the context from previous steps below to inform your output. "
            "If there are web search results, BASE your output on those real facts. "
            "Do NOT ignore the context and make up generic content.\n"
        )

    return [
        {
            "role": "system",
            "content": (
                "You are an autonomous execution agent. Carry out the given step "
                "and produce REAL, DETAILED, ACTIONABLE content.\n\n"
                "CRITICAL RULES:\n"
                "1. If context from previous steps contains web search results or data, USE THAT DATA in your output\n"
                "2. NEVER write generic placeholder content — be specific with real facts, names, dates, and details\n"
                "3. Your output should be LONG and DETAILED — at least 300 words\n"
                "4. Use markdown formatting (## headers, bullet points, **bold**) for readability\n"
                "5. If the task asks for a report, write a REAL report with specific findings\n"
                "6. If the task asks for a plan, create SPECIFIC actionable items with dates\n"
                + context_instruction +
                "\nReturn JSON: {\"status\": \"completed\", \"output\": \"detailed content here\", \"artifacts\": [], \"notes\": \"\"}\n"
                "Return ONLY valid JSON."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Execute this step:\n{json_safe(step)}\n\n"
                f"Context from previous steps:\n{context or 'No previous context — this is the first step.'}"
            ),
        },
    ]


def verification_prompt(step: dict, result: dict) -> list[dict]:
    """Prompt for the Verifier agent to check if a step succeeded."""
    return [
        {
            "role": "system",
            "content": (
                "You are a quality verifier. Check whether a task step was completed successfully.\n"
                "Evaluate the result against expected output and verification criteria.\n\n"
                "Return JSON: {\"passed\": true/false, \"score\": 0.0-1.0, \"reason\": \"...\", \"suggestions\": []}\n"
                "Return ONLY valid JSON, no markdown."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Step definition:\n{json_safe(step)}\n\n"
                f"Step result:\n{json_safe(result)}\n\n"
                "Did this step complete successfully?"
            ),
        },
    ]


def replan_prompt(
    goal: str, plan: dict, failed_step: dict, failure_reason: str, context: str
) -> list[dict]:
    """Prompt for the Adaptor agent to create a revised plan after failure."""
    return [
        {
            "role": "system",
            "content": (
                "You are an adaptive planning agent. A step failed. Create a revised plan.\n\n"
                "Options: 1) Retry with modified params, 2) Replace with alternative, "
                "3) Skip if not critical, 4) Add prerequisite steps\n\n"
                "Return JSON: {\"strategy\": 1-4, \"explanation\": \"...\", \"revised_steps\": [...], \"resume_from_step\": N}\n"
                "Return ONLY valid JSON, no markdown."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Goal: {goal}\n\n"
                f"Plan: {json_safe(plan)}\n\n"
                f"Failed step: {json_safe(failed_step)}\n\n"
                f"Failure: {failure_reason}\n\n"
                f"Context: {context}\n\n"
                "Create a revised plan."
            ),
        },
    ]


def json_safe(obj) -> str:
    """Convert an object to a JSON-safe string."""
    import json
    try:
        return json.dumps(obj, indent=2, default=str)
    except (TypeError, ValueError):
        return str(obj)
