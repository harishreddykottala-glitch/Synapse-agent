"""SQLite-based persistent memory for Synapse Agent.

Stores goals, execution plans, step results, and agent logs
for context management across the agent lifecycle.
"""

import json
import os
import time
import uuid
from dataclasses import dataclass, field

import aiosqlite


@dataclass
class GoalRecord:
    """A stored goal and its execution state."""
    id: str
    goal_text: str
    interpretation: dict | None = None
    plan: dict | None = None
    status: str = "pending"  # pending | planning | executing | completed | failed
    step_results: list[dict] = field(default_factory=list)
    adaptation_count: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    final_outcome: dict | None = None


class MemoryStore:
    """SQLite-backed persistent memory for agent state."""

    def __init__(self, db_path: str = "./data/synapse.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._initialized = False

    async def _ensure_tables(self):
        """Create tables if they don't exist."""
        if self._initialized:
            return
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS goals (
                    id TEXT PRIMARY KEY,
                    goal_text TEXT NOT NULL,
                    interpretation TEXT,
                    plan TEXT,
                    status TEXT DEFAULT 'pending',
                    step_results TEXT DEFAULT '[]',
                    adaptation_count INTEGER DEFAULT 0,
                    created_at REAL,
                    updated_at REAL,
                    final_outcome TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal_id TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    message TEXT,
                    data TEXT,
                    timestamp REAL,
                    FOREIGN KEY (goal_id) REFERENCES goals (id)
                )
            """)
            await db.commit()
        self._initialized = True

    async def create_goal(self, goal_text: str) -> GoalRecord:
        """Create a new goal record."""
        await self._ensure_tables()
        record = GoalRecord(
            id=str(uuid.uuid4())[:8],
            goal_text=goal_text,
        )
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO goals (id, goal_text, status, step_results, adaptation_count, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (record.id, record.goal_text, record.status, "[]", 0, record.created_at, record.updated_at),
            )
            await db.commit()
        return record

    async def update_goal(self, goal_id: str, **updates) -> GoalRecord | None:
        """Update a goal record with the given fields."""
        await self._ensure_tables()
        updates["updated_at"] = time.time()

        # Serialize dict/list fields to JSON
        for key in ("interpretation", "plan", "step_results", "final_outcome"):
            if key in updates and not isinstance(updates[key], str):
                updates[key] = json.dumps(updates[key], default=str)

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [goal_id]

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"UPDATE goals SET {set_clause} WHERE id = ?", values)
            await db.commit()
        return await self.get_goal(goal_id)

    async def get_goal(self, goal_id: str) -> GoalRecord | None:
        """Retrieve a goal record by ID."""
        await self._ensure_tables()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM goals WHERE id = ?", (goal_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            return GoalRecord(
                id=row["id"],
                goal_text=row["goal_text"],
                interpretation=_parse_json(row["interpretation"]),
                plan=_parse_json(row["plan"]),
                status=row["status"],
                step_results=_parse_json(row["step_results"]) or [],
                adaptation_count=row["adaptation_count"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                final_outcome=_parse_json(row["final_outcome"]),
            )

    async def list_goals(self, limit: int = 50) -> list[GoalRecord]:
        """List all goals, most recent first."""
        await self._ensure_tables()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM goals ORDER BY created_at DESC LIMIT ?", (limit,)
            )
            rows = await cursor.fetchall()
            return [
                GoalRecord(
                    id=row["id"],
                    goal_text=row["goal_text"],
                    interpretation=_parse_json(row["interpretation"]),
                    plan=_parse_json(row["plan"]),
                    status=row["status"],
                    step_results=_parse_json(row["step_results"]) or [],
                    adaptation_count=row["adaptation_count"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    final_outcome=_parse_json(row["final_outcome"]),
                )
                for row in rows
            ]

    async def add_log(self, goal_id: str, agent_name: str, event_type: str, message: str, data: dict | None = None):
        """Add a log entry for an agent action."""
        await self._ensure_tables()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO logs (goal_id, agent_name, event_type, message, data, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (goal_id, agent_name, event_type, message, json.dumps(data, default=str) if data else None, time.time()),
            )
            await db.commit()

    async def get_logs(self, goal_id: str) -> list[dict]:
        """Get all logs for a goal."""
        await self._ensure_tables()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM logs WHERE goal_id = ? ORDER BY timestamp ASC", (goal_id,)
            )
            rows = await cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "agent_name": row["agent_name"],
                    "event_type": row["event_type"],
                    "message": row["message"],
                    "data": _parse_json(row["data"]),
                    "timestamp": row["timestamp"],
                }
                for row in rows
            ]


def _parse_json(value):
    """Safely parse a JSON string."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value
