"""Knowledge base tool for Synapse Agent."""

from .base import BaseTool, ToolResult


class KnowledgeBaseTool(BaseTool):
    """Query a knowledge base for domain-specific information."""

    # In-memory knowledge for demo — in production this would be a vector store
    KNOWLEDGE = {
        "gate_exam": {
            "subjects": [
                "Engineering Mathematics", "Digital Logic", "Computer Organization",
                "Data Structures & Algorithms", "Theory of Computation",
                "Compiler Design", "Operating Systems", "Databases",
                "Computer Networks", "Software Engineering",
            ],
            "weightage": {
                "Engineering Mathematics": 13,
                "Aptitude": 15,
                "Core CS": 72,
            },
            "tips": [
                "Focus on previous year papers — 30% questions repeat patterns",
                "Engineering Mathematics carries 13% weight — don't skip it",
                "Practice Data Structures daily — highest weight in Core CS",
                "Take at least 20 full mock tests in the last month",
            ],
        },
        "study_techniques": {
            "methods": [
                {"name": "Pomodoro Technique", "desc": "25min study + 5min break, 4 cycles then 15min break"},
                {"name": "Active Recall", "desc": "Test yourself instead of re-reading"},
                {"name": "Spaced Repetition", "desc": "Review at increasing intervals: 1d, 3d, 7d, 14d, 30d"},
                {"name": "Feynman Method", "desc": "Explain concepts in simple terms to find gaps"},
            ],
        },
        "fitness_basics": {
            "components": ["Cardio", "Strength Training", "Flexibility", "Nutrition", "Rest"],
            "weekly_template": {
                "Mon": "Upper Body Strength", "Tue": "Cardio + Core",
                "Wed": "Lower Body Strength", "Thu": "Active Recovery/Yoga",
                "Fri": "Full Body HIIT", "Sat": "Cardio + Flexibility",
                "Sun": "Rest Day",
            },
        },
    }

    @property
    def name(self) -> str:
        return "knowledge_base"

    @property
    def description(self) -> str:
        return "Query the knowledge base for domain-specific information (exams, study methods, fitness, etc.)."

    async def execute(self, params: dict) -> ToolResult:
        topic = params.get("topic", "").lower().replace(" ", "_")
        query = params.get("query", "")

        # Direct topic lookup
        if topic in self.KNOWLEDGE:
            import json
            data = self.KNOWLEDGE[topic]
            output = json.dumps(data, indent=2)
            return ToolResult(success=True, output=output, data=data)

        # Search across all topics
        if query:
            results = {}
            query_lower = query.lower()
            for key, value in self.KNOWLEDGE.items():
                if query_lower in key or query_lower in str(value).lower():
                    results[key] = value
            if results:
                import json
                return ToolResult(success=True, output=json.dumps(results, indent=2), data=results)

        return ToolResult(
            success=True,
            output=f"No specific knowledge found for '{topic or query}'. Available topics: {', '.join(self.KNOWLEDGE.keys())}",
            data={"available_topics": list(self.KNOWLEDGE.keys())},
        )
