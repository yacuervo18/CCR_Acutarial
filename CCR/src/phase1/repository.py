"""Persistencia SQLite de estado por proceso-periodo."""
import sqlite3
from datetime import datetime
import json
from pathlib import Path
from .config import PROCESOS


class Repository:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(__file__).parents[2] / "data" / "ccr.db"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS phase1_periods (period TEXT PRIMARY KEY, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS phase1_tasks (period TEXT, process_code TEXT, task_id INTEGER, completed INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(period, process_code, task_id));
            CREATE TABLE IF NOT EXISTS phase1_schedule (period TEXT, process_code TEXT PRIMARY KEY, scheduled_at TEXT, recipients TEXT, channels TEXT);
            CREATE TABLE IF NOT EXISTS phase1_process_schedules (
                process_code TEXT PRIMARY KEY,
                start_date TEXT NOT NULL DEFAULT '',
                scheduled_time TEXT NOT NULL,
                months TEXT NOT NULL,
                interval_minutes INTEGER NOT NULL DEFAULT 1440,
                recipients TEXT NOT NULL,
                channel TEXT NOT NULL DEFAULT 'Teams',
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS phase1_process_schedule_overrides (
                period TEXT NOT NULL,
                process_code TEXT NOT NULL,
                start_date TEXT NOT NULL,
                scheduled_time TEXT NOT NULL,
                months TEXT NOT NULL,
                interval_minutes INTEGER NOT NULL DEFAULT 1440,
                recipients TEXT NOT NULL,
                channel TEXT NOT NULL DEFAULT 'Teams',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (period, process_code)
            );
            CREATE TABLE IF NOT EXISTS phase1_notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, period TEXT, process_code TEXT, payload TEXT, created_at TEXT NOT NULL);
            """)
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(phase1_process_schedules)")}
            if "start_date" not in columns:
                conn.execute("ALTER TABLE phase1_process_schedules ADD COLUMN start_date TEXT NOT NULL DEFAULT ''")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_period(self, period: str) -> None:
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO phase1_periods VALUES (?, ?)", (period, datetime.now().isoformat()))
            for process in PROCESOS:
                for task in process.tareas:
                    conn.execute("INSERT OR IGNORE INTO phase1_tasks(period, process_code, task_id) VALUES (?, ?, ?)", (period, process.codigo, task.id))

    def periods(self) -> list[str]:
        with self._connect() as conn:
            return [r["period"] for r in conn.execute("SELECT period FROM phase1_periods ORDER BY period DESC")]

    def completed(self, period: str, code: str) -> set[int]:
        with self._connect() as conn:
            return {r["task_id"] for r in conn.execute("SELECT task_id FROM phase1_tasks WHERE period=? AND process_code=? AND completed=1", (period, code))}

    def set_task(self, period: str, code: str, task_id: int, value: bool) -> None:
        self.ensure_period(period)
        with self._connect() as conn:
            conn.execute("UPDATE phase1_tasks SET completed=? WHERE period=? AND process_code=? AND task_id=?", (int(value), period, code, task_id))
            conn.commit()

    def reset_tasks(self, period: str) -> None:
        """Reinicia únicamente las actividades del periodo indicado."""
        self.ensure_period(period)
        with self._connect() as conn:
            conn.execute("UPDATE phase1_tasks SET completed=0 WHERE period=?", (period,))
            conn.commit()

    def save_schedule(self, period: str, code: str, scheduled_at: str, recipients: str, channels: str) -> None:
        with self._connect() as conn:
            conn.execute("INSERT OR REPLACE INTO phase1_schedule VALUES (?, ?, ?, ?, ?)", (period, code, scheduled_at, recipients, channels))
            conn.commit()

    def save_process_schedule(
        self,
        code: str,
        start_date: str,
        scheduled_time: str,
        months: list[int],
        interval_minutes: int,
        recipients: list[dict[str, str]],
        period: str | None = None,
    ) -> None:
        table = "phase1_process_schedule_overrides" if period else "phase1_process_schedules"
        params = (period, code, start_date, scheduled_time, json.dumps(months), interval_minutes, json.dumps(recipients, ensure_ascii=False), datetime.now().isoformat()) if period else (code, start_date, scheduled_time, json.dumps(months), interval_minutes, json.dumps(recipients, ensure_ascii=False), datetime.now().isoformat())
        with self._connect() as conn:
            conn.execute(
                f"""INSERT OR REPLACE INTO {table}
                ({'period, ' if period else ''}process_code, start_date, scheduled_time, months, interval_minutes, recipients, channel, updated_at)
                VALUES ({'?, ' if period else ''}?, ?, ?, ?, ?, ?, 'Teams', ?)""",
                params,
            )
            conn.commit()

    def process_schedule(self, code: str, period: str | None = None) -> sqlite3.Row | None:
        with self._connect() as conn:
            if period:
                override = conn.execute(
                    "SELECT * FROM phase1_process_schedule_overrides WHERE process_code=? AND period=?",
                    (code, period),
                ).fetchone()
                if override:
                    return override
            return conn.execute("SELECT * FROM phase1_process_schedules WHERE process_code=?", (code,)).fetchone()

    def reminder_due(self, code: str, period: str, now: datetime, interval_minutes: int) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT created_at FROM phase1_notifications WHERE period=? AND process_code=? AND payload LIKE '%recordatorio_pendiente%' ORDER BY id DESC LIMIT 1",
                (period, code),
            ).fetchone()
            if row is None:
                return True
            last_sent = datetime.fromisoformat(row["created_at"])
            return (now - last_sent).total_seconds() >= interval_minutes * 60

    def schedule(self, period: str, code: str) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute("SELECT * FROM phase1_schedule WHERE period=? AND process_code=?", (period, code)).fetchone()

    def add_notification(self, period: str, code: str, payload: str) -> None:
        with self._connect() as conn:
            conn.execute("INSERT INTO phase1_notifications(period, process_code, payload, created_at) VALUES (?, ?, ?, ?)", (period, code, payload, datetime.now().isoformat()))
            conn.commit()

    def notification_history(self, period: str, code: str) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute("SELECT * FROM phase1_notifications WHERE period=? AND process_code=? ORDER BY id DESC", (period, code)).fetchall()
