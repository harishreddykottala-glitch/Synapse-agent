"""Calendar/scheduling tool for Synapse Agent."""

from datetime import datetime, timedelta
from .base import BaseTool, ToolResult


class CalendarTool(BaseTool):
    """Generate date ranges, schedules, and time calculations."""

    @property
    def name(self) -> str:
        return "calendar"

    @property
    def description(self) -> str:
        return "Date calculations, schedule generation, and time-based planning."

    async def execute(self, params: dict) -> ToolResult:
        action = params.get("action", "today")

        if action == "today":
            now = datetime.now()
            return ToolResult(
                success=True,
                output=f"Today is {now.strftime('%A, %B %d, %Y')} ({now.strftime('%Y-%m-%d')})",
                data={"date": now.isoformat(), "day": now.strftime("%A")},
            )

        elif action == "date_range":
            start = params.get("start_date", datetime.now().strftime("%Y-%m-%d"))
            days = int(params.get("days", 7))
            start_dt = datetime.strptime(start, "%Y-%m-%d")
            dates = []
            for i in range(days):
                d = start_dt + timedelta(days=i)
                dates.append({
                    "date": d.strftime("%Y-%m-%d"),
                    "day": d.strftime("%A"),
                    "week": d.isocalendar()[1],
                })
            return ToolResult(
                success=True,
                output=f"Generated {days}-day range starting {start}",
                data={"dates": dates},
            )

        elif action == "days_until":
            target = params.get("target_date", "")
            if not target:
                return ToolResult(success=False, output="", error="No target_date provided")
            target_dt = datetime.strptime(target, "%Y-%m-%d")
            delta = (target_dt - datetime.now()).days
            return ToolResult(
                success=True,
                output=f"{delta} days until {target}",
                data={"days_remaining": delta, "target": target},
            )

        elif action == "weekly_schedule":
            weeks = int(params.get("weeks", 4))
            hours_per_day = float(params.get("hours_per_day", 2))
            start = params.get("start_date", datetime.now().strftime("%Y-%m-%d"))
            start_dt = datetime.strptime(start, "%Y-%m-%d")
            schedule = []
            for w in range(weeks):
                week_start = start_dt + timedelta(weeks=w)
                week_days = []
                for d in range(7):
                    day = week_start + timedelta(days=d)
                    week_days.append({
                        "date": day.strftime("%Y-%m-%d"),
                        "day": day.strftime("%A"),
                        "study_hours": hours_per_day if day.weekday() < 6 else hours_per_day * 1.5,
                    })
                schedule.append({"week": w + 1, "days": week_days})
            return ToolResult(
                success=True,
                output=f"Generated {weeks}-week schedule with {hours_per_day}h/day",
                data={"schedule": schedule},
            )

        return ToolResult(success=False, output="", error=f"Unknown calendar action: {action}")
