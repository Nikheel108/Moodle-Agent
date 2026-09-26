"""Local task database for tracking assignments, deadlines, and reminders.

Uses SQLite for persistent storage with a clean ORM-like interface.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Generator

from .config import DATA_DIR, DATABASE_PATH


class TaskStatus(str, Enum):
    """Assignment task status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    STUDY_NOTES_READY = "study_notes_ready"
    DRAFT_READY = "draft_ready"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    OVERDUE = "overdue"


class ReminderType(str, Enum):
    """Types of reminders."""

    DUE_SOON = "due_soon"
    OVERDUE = "overdue"
    REVIEW_NEEDED = "review_needed"
    STUDY_REMINDER = "study_reminder"


@dataclass
class TaskRecord:
    """A tracked assignment task."""

    id: int
    moodle_assignment_id: int
    course_name: str
    assignment_name: str
    description: str
    due_date: str | None
    status: TaskStatus
    study_notes_path: str | None
    draft_path: str | None
    upload_package_path: str | None
    created_at: str
    updated_at: str
    metadata_json: str | None = None

    @property
    def due_datetime(self) -> datetime | None:
        if self.due_date:
            return datetime.fromisoformat(self.due_date)
        return None

    @property
    def days_remaining(self) -> float | None:
        dt = self.due_datetime
        if dt is None:
            return None
        delta = dt - datetime.now(timezone.utc)
        return delta.total_seconds() / 86400

    @property
    def metadata(self) -> dict:
        if self.metadata_json:
            return json.loads(self.metadata_json)
        return {}


DB_PATH = DATABASE_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    moodle_assignment_id INTEGER UNIQUE NOT NULL,
    course_name TEXT NOT NULL,
    assignment_name TEXT NOT NULL,
    description TEXT DEFAULT '',
    due_date TEXT,
    status TEXT DEFAULT 'pending',
    study_notes_path TEXT,
    draft_path TEXT,
    upload_package_path TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    reminder_type TEXT NOT NULL,
    remind_at TEXT NOT NULL,
    message TEXT NOT NULL,
    sent INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER,
    action TEXT NOT NULL,
    details TEXT,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_reminders_remind_at ON reminders(remind_at);
CREATE INDEX IF NOT EXISTS idx_reminders_sent ON reminders(sent);
"""


class TaskDatabase:
    """SQLite-backed task and reminder database."""

    def __init__(self, db_path: Path | None = None):
        self._db_path = db_path or DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── Task CRUD ──────────────────────────────────────────────────────

    def upsert_task(
        self,
        moodle_assignment_id: int,
        course_name: str,
        assignment_name: str,
        description: str = "",
        due_date: datetime | None = None,
        status: TaskStatus = TaskStatus.PENDING,
        metadata: dict | None = None,
    ) -> int:
        """Insert or update a task. Returns the task ID."""
        now = self._now()
        due_str = due_date.isoformat() if due_date else None
        meta_json = json.dumps(metadata) if metadata else None

        with self._connect() as conn:
            # Check if exists
            row = conn.execute(
                "SELECT id, status FROM tasks WHERE moodle_assignment_id = ?",
                (moodle_assignment_id,),
            ).fetchone()

            if row:
                # Don't downgrade status on refresh
                existing_status = TaskStatus(row["status"])
                if existing_status in (
                    TaskStatus.APPROVED,
                    TaskStatus.SUBMITTED,
                ):
                    return row["id"]

                conn.execute(
                    """UPDATE tasks
                       SET course_name = ?, assignment_name = ?, description = ?,
                           due_date = ?, updated_at = ?,
                           metadata_json = COALESCE(?, metadata_json)
                       WHERE moodle_assignment_id = ?""",
                    (
                        course_name,
                        assignment_name,
                        description,
                        due_str,
                        now,
                        meta_json,
                        moodle_assignment_id,
                    ),
                )
                return row["id"]
            else:
                cursor = conn.execute(
                    """INSERT INTO tasks
                       (moodle_assignment_id, course_name, assignment_name,
                        description, due_date, status, created_at, updated_at,
                        metadata_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        moodle_assignment_id,
                        course_name,
                        assignment_name,
                        description,
                        due_str,
                        status.value,
                        now,
                        now,
                        meta_json,
                    ),
                )
                return cursor.lastrowid  # type: ignore[return-value]

    def get_task(self, task_id: int) -> TaskRecord | None:
        """Fetch a single task by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            return self._row_to_task(row) if row else None

    def get_task_by_moodle_id(
        self, moodle_assignment_id: int
    ) -> TaskRecord | None:
        """Fetch a task by its Moodle assignment ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE moodle_assignment_id = ?",
                (moodle_assignment_id,),
            ).fetchone()
            return self._row_to_task(row) if row else None

    def get_all_tasks(
        self, status: TaskStatus | None = None
    ) -> list[TaskRecord]:
        """Fetch all tasks, optionally filtered by status."""
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE status = ? ORDER BY due_date",
                    (status.value,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tasks ORDER BY due_date"
                ).fetchall()
            return [self._row_to_task(r) for r in rows]

    def get_pending_tasks(self) -> list[TaskRecord]:
        """Get tasks that still need work."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM tasks
                   WHERE status NOT IN (?, ?)
                   ORDER BY due_date""",
                (TaskStatus.SUBMITTED.value, TaskStatus.APPROVED.value),
            ).fetchall()
            return [self._row_to_task(r) for r in rows]

    def update_task_status(
        self, task_id: int, status: TaskStatus
    ) -> None:
        """Update the status of a task."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, self._now(), task_id),
            )
            self._log_activity(
                conn, task_id, "status_change", f"Status → {status.value}"
            )

    def update_task_paths(
        self,
        task_id: int,
        study_notes_path: str | None = None,
        draft_path: str | None = None,
        upload_package_path: str | None = None,
    ) -> None:
        """Update file paths for a task."""
        updates = []
        values = []
        if study_notes_path is not None:
            updates.append("study_notes_path = ?")
            values.append(study_notes_path)
        if draft_path is not None:
            updates.append("draft_path = ?")
            values.append(draft_path)
        if upload_package_path is not None:
            updates.append("upload_package_path = ?")
            values.append(upload_package_path)

        if not updates:
            return

        updates.append("updated_at = ?")
        values.append(self._now())
        values.append(task_id)

        with self._connect() as conn:
            conn.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?",
                values,
            )

    def delete_task(self, task_id: int) -> None:
        """Delete a task and its reminders."""
        with self._connect() as conn:
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

    # ── Reminders ──────────────────────────────────────────────────────

    def add_reminder(
        self,
        task_id: int,
        reminder_type: ReminderType,
        remind_at: datetime,
        message: str,
    ) -> int:
        """Schedule a reminder for a task."""
        with self._connect() as conn:
            cursor = conn.execute(
                """INSERT INTO reminders
                   (task_id, reminder_type, remind_at, message, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    task_id,
                    reminder_type.value,
                    remind_at.isoformat(),
                    message,
                    self._now(),
                ),
            )
            return cursor.lastrowid  # type: ignore[return-value]

    def get_due_reminders(self) -> list[dict]:
        """Get all unsent reminders that are now due."""
        now = self._now()
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT r.*, t.assignment_name, t.course_name
                   FROM reminders r
                   JOIN tasks t ON r.task_id = t.id
                   WHERE r.sent = 0 AND r.remind_at <= ?
                   ORDER BY r.remind_at""",
                (now,),
            ).fetchall()
            return [dict(r) for r in rows]

    def mark_reminder_sent(self, reminder_id: int) -> None:
        """Mark a reminder as sent."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE reminders SET sent = 1 WHERE id = ?",
                (reminder_id,),
            )

    # ── Activity log ───────────────────────────────────────────────────

    def log_activity(
        self, task_id: int | None, action: str, details: str = ""
    ) -> None:
        """Log an activity entry."""
        with self._connect() as conn:
            self._log_activity(conn, task_id, action, details)

    def _log_activity(
        self,
        conn: sqlite3.Connection,
        task_id: int | None,
        action: str,
        details: str,
    ) -> None:
        conn.execute(
            """INSERT INTO activity_log (task_id, action, details, timestamp)
               VALUES (?, ?, ?, ?)""",
            (task_id, action, details, self._now()),
        )

    def get_activity_log(
        self, task_id: int | None = None, limit: int = 50
    ) -> list[dict]:
        """Fetch activity log entries."""
        with self._connect() as conn:
            if task_id:
                rows = conn.execute(
                    """SELECT * FROM activity_log
                       WHERE task_id = ?
                       ORDER BY timestamp DESC LIMIT ?""",
                    (task_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM activity_log
                       ORDER BY timestamp DESC LIMIT ?""",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> TaskRecord:
        return TaskRecord(
            id=row["id"],
            moodle_assignment_id=row["moodle_assignment_id"],
            course_name=row["course_name"],
            assignment_name=row["assignment_name"],
            description=row["description"],
            due_date=row["due_date"],
            status=TaskStatus(row["status"]),
            study_notes_path=row["study_notes_path"],
            draft_path=row["draft_path"],
            upload_package_path=row["upload_package_path"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata_json=row["metadata_json"],
        )

    def get_stats(self) -> dict[str, int]:
        """Get summary statistics."""
        with self._connect() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM tasks"
            ).fetchone()[0]
            by_status = {}
            for s in TaskStatus:
                count = conn.execute(
                    "SELECT COUNT(*) FROM tasks WHERE status = ?",
                    (s.value,),
                ).fetchone()[0]
                by_status[s.value] = count

            return {"total": total, **by_status}
