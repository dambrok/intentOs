"""Local structured memory and execution state for the IntentOS runtime."""

import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional


class DatabaseManager:
    """Transactional SQLite store for IntentOS memory, plans, and verification."""

    def __init__(self, db_path: str = "intentOS.db") -> None:
        self.db_path = db_path
        self.init_database()

    @contextmanager
    def get_connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA busy_timeout = 30000")
            conn.execute("PRAGMA journal_mode = WAL")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value if value is not None else {}, ensure_ascii=True)

    @staticmethod
    def _decode(value: Optional[str], default: Any) -> Any:
        if value is None:
            return default
        return json.loads(value)

    def init_database(self) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executescript(
                """
                CREATE TABLE IF NOT EXISTS profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    language TEXT NOT NULL DEFAULT 'hi',
                    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS entities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id INTEGER NOT NULL,
                    entity_type TEXT NOT NULL,
                    name TEXT,
                    data TEXT NOT NULL DEFAULT '{}',
                    memory_class TEXT NOT NULL DEFAULT 'context'
                        CHECK(memory_class IN ('context', 'preference', 'personal', 'secret')),
                    consent_status TEXT NOT NULL DEFAULT 'not_required'
                        CHECK(consent_status IN ('not_required', 'pending', 'granted', 'rejected')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    due_at TEXT,
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK(status IN ('pending', 'completed', 'cancelled')),
                    source_intent_id INTEGER,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT,
                    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
                    FOREIGN KEY (source_intent_id) REFERENCES intents(id) ON DELETE SET NULL
                );
                CREATE TABLE IF NOT EXISTS preferences (
                    profile_id INTEGER NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    value_type TEXT NOT NULL DEFAULT 'text',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (profile_id, key),
                    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS conversation_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id INTEGER NOT NULL,
                    title TEXT,
                    active_context TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'active'
                        CHECK(status IN ('active', 'completed', 'archived')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system', 'tool')),
                    content TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES conversation_sessions(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS intents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    profile_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    action TEXT NOT NULL CHECK(action IN ('query', 'write', 'plan')),
                    entities TEXT NOT NULL DEFAULT '{}',
                    constraints_data TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'identified'
                        CHECK(status IN ('identified', 'planned', 'executing', 'completed', 'failed', 'cancelled')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES conversation_sessions(id) ON DELETE SET NULL,
                    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    intent_id INTEGER NOT NULL,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'planned'
                        CHECK(status IN ('planned', 'executing', 'completed', 'failed', 'cancelled')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT,
                    FOREIGN KEY (intent_id) REFERENCES intents(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS plan_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id INTEGER NOT NULL,
                    step_order INTEGER NOT NULL,
                    tool_name TEXT NOT NULL,
                    arguments TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK(status IN ('pending', 'executing', 'completed', 'failed', 'skipped')),
                    FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE,
                    UNIQUE(plan_id, step_order)
                );
                CREATE TABLE IF NOT EXISTS tool_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_step_id INTEGER,
                    profile_id INTEGER NOT NULL,
                    tool_name TEXT NOT NULL,
                    arguments TEXT NOT NULL DEFAULT '{}',
                    result TEXT,
                    status TEXT NOT NULL DEFAULT 'started'
                        CHECK(status IN ('started', 'succeeded', 'failed')),
                    error TEXT,
                    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT,
                    FOREIGN KEY (plan_step_id) REFERENCES plan_steps(id) ON DELETE SET NULL,
                    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS verifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    execution_id INTEGER NOT NULL,
                    check_name TEXT NOT NULL,
                    expected TEXT NOT NULL DEFAULT '{}',
                    observed TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL CHECK(status IN ('passed', 'failed')),
                    notes TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (execution_id) REFERENCES tool_executions(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    entity_type TEXT,
                    entity_id INTEGER,
                    payload TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS offline_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id INTEGER NOT NULL,
                    action_type TEXT NOT NULL,
                    action_data TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK(status IN ('pending', 'processing', 'completed', 'failed')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    processed_at TEXT,
                    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS schema_manifest (
                    entity_name TEXT PRIMARY KEY,
                    purpose TEXT NOT NULL,
                    fields TEXT NOT NULL DEFAULT '[]',
                    relationships TEXT NOT NULL DEFAULT '[]',
                    retrieval_hints TEXT NOT NULL DEFAULT '[]',
                    allowed_operations TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_entities_lookup
                    ON entities(profile_id, entity_type, name);
                CREATE INDEX IF NOT EXISTS idx_tasks_pending
                    ON tasks(profile_id, status, due_at);
                CREATE INDEX IF NOT EXISTS idx_sessions_profile
                    ON conversation_sessions(profile_id, status, updated_at);
                CREATE INDEX IF NOT EXISTS idx_messages_session
                    ON conversation_messages(session_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_intents_status
                    ON intents(profile_id, status, created_at);
                CREATE INDEX IF NOT EXISTS idx_plan_steps_status
                    ON plan_steps(plan_id, status, step_order);
                CREATE INDEX IF NOT EXISTS idx_executions_status
                    ON tool_executions(profile_id, status, started_at);
                CREATE INDEX IF NOT EXISTS idx_events_time
                    ON events(profile_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_queue_status
                    ON offline_queue(profile_id, status, created_at);
                """
            )
            entity_columns = {
                row["name"] for row in cursor.execute("PRAGMA table_info(entities)").fetchall()
            }
            if "memory_class" not in entity_columns:
                cursor.execute(
                    "ALTER TABLE entities ADD COLUMN memory_class TEXT NOT NULL DEFAULT 'context'"
                )
            if "consent_status" not in entity_columns:
                cursor.execute(
                    "ALTER TABLE entities ADD COLUMN consent_status TEXT NOT NULL DEFAULT 'not_required'"
                )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_entities_memory_policy ON entities(profile_id, memory_class, consent_status)"
            )
            manifest_entries = [
                ("profiles", "Local user/runtime profile", ["id", "name", "language", "timezone"], [], ["active user", "language", "timezone"], ["read", "update"]),
                ("entities", "Generic structured personal memory with risk-aware consent", ["id", "entity_type", "name", "data", "memory_class", "consent_status", "created_at", "updated_at"], ["entities.profile_id -> profiles.id"], ["entity lookup", "structured memory", "preferences", "consent status"], ["create", "read", "update"]),
                ("tasks", "Future actions and reminders", ["id", "title", "description", "due_at", "status", "source_intent_id"], ["tasks.source_intent_id -> intents.id"], ["pending actions", "reminders", "due tasks"], ["create", "read", "complete", "cancel"]),
                ("preferences", "Persistent user defaults", ["profile_id", "key", "value", "value_type"], ["preferences.profile_id -> profiles.id"], ["default reminder time", "user preference"], ["read", "upsert"]),
                ("conversation_sessions", "Active conversational context", ["id", "profile_id", "title", "active_context", "status"], ["conversation_sessions.profile_id -> profiles.id"], ["current task", "follow-up reference", "conversation context"], ["create", "read", "update"]),
                ("intents", "Structured interpretation of user goals", ["id", "name", "action", "entities", "constraints_data", "status"], ["intents.session_id -> conversation_sessions.id", "intents.profile_id -> profiles.id"], ["intent classification", "entities", "constraints"], ["create", "read", "update"]),
                ("plans", "Executable multi-step action plans", ["id", "intent_id", "goal", "status"], ["plans.intent_id -> intents.id", "plans -> plan_steps"], ["execution plan", "multi-step goal"], ["create", "read", "execute", "cancel"]),
                ("tool_executions", "Controlled tool calls and results", ["id", "plan_step_id", "tool_name", "arguments", "result", "status", "error"], ["tool_executions.plan_step_id -> plan_steps.id"], ["tool result", "failure recovery", "action audit"], ["start", "complete", "fail", "read"]),
                ("verifications", "Observed-state checks after actions", ["id", "execution_id", "check_name", "expected", "observed", "status", "notes"], ["verifications.execution_id -> tool_executions.id"], ["state verification", "post-action check"], ["create", "read"]),
                ("events", "Append-only history of important runtime events", ["id", "event_type", "entity_type", "entity_id", "payload", "created_at"], ["events.profile_id -> profiles.id"], ["activity history", "audit context"], ["append", "read"]),
            ]
            cursor.executemany(
                """
                INSERT OR IGNORE INTO schema_manifest
                    (entity_name, purpose, fields, relationships, retrieval_hints, allowed_operations)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [(name, purpose, self._json(fields), self._json(relationships), self._json(hints), self._json(operations)) for name, purpose, fields, relationships, hints, operations in manifest_entries],
            )

    def create_profile(self, name: str, language: str = "hi", timezone: str = "Asia/Kolkata") -> int:
        with self.get_connection() as conn:
            cursor = conn.execute("INSERT INTO profiles (name, language, timezone) VALUES (?, ?, ?)", (name, language, timezone))
            return int(cursor.lastrowid)

    def get_schema_manifest(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM schema_manifest ORDER BY entity_name").fetchall()
            return [{**dict(row), "fields": self._decode(row["fields"], []), "relationships": self._decode(row["relationships"], []), "retrieval_hints": self._decode(row["retrieval_hints"], []), "allowed_operations": self._decode(row["allowed_operations"], [])} for row in rows]

    def create_session(self, profile_id: int, title: Optional[str] = None) -> int:
        with self.get_connection() as conn:
            cursor = conn.execute("INSERT INTO conversation_sessions (profile_id, title) VALUES (?, ?)", (profile_id, title))
            return int(cursor.lastrowid)

    def update_session_context(self, session_id: int, context: Dict[str, Any]) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE conversation_sessions
                SET active_context = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (self._json(context), session_id),
            )

    def get_session_context(self, session_id: int) -> Dict[str, Any]:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT active_context FROM conversation_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"Conversation session {session_id} does not exist")
        return self._decode(row["active_context"], {})

    def add_message(self, session_id: int, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> int:
        with self.get_connection() as conn:
            cursor = conn.execute("INSERT INTO conversation_messages (session_id, role, content, metadata) VALUES (?, ?, ?, ?)", (session_id, role, content, self._json(metadata)))
            conn.execute("UPDATE conversation_sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (session_id,))
            return int(cursor.lastrowid)

    def create_intent(self, profile_id: int, name: str, action: str, entities: Optional[Dict[str, Any]] = None, constraints: Optional[Dict[str, Any]] = None, session_id: Optional[int] = None) -> int:
        with self.get_connection() as conn:
            cursor = conn.execute("INSERT INTO intents (session_id, profile_id, name, action, entities, constraints_data) VALUES (?, ?, ?, ?, ?, ?)", (session_id, profile_id, name, action, self._json(entities), self._json(constraints)))
            return int(cursor.lastrowid)

    def create_plan(self, intent_id: int, goal: str, steps: List[Dict[str, Any]]) -> int:
        with self.get_connection() as conn:
            cursor = conn.execute("INSERT INTO plans (intent_id, goal) VALUES (?, ?)", (intent_id, goal))
            plan_id = int(cursor.lastrowid)
            conn.executemany("INSERT INTO plan_steps (plan_id, step_order, tool_name, arguments) VALUES (?, ?, ?, ?)", [(plan_id, index, step["tool_name"], self._json(step.get("arguments"))) for index, step in enumerate(steps, 1)])
            conn.execute("UPDATE intents SET status = 'planned', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (intent_id,))
            return plan_id

    def record_execution(self, profile_id: int, tool_name: str, arguments: Optional[Dict[str, Any]] = None, plan_step_id: Optional[int] = None, result: Optional[Any] = None, status: str = "succeeded", error: Optional[str] = None) -> int:
        with self.get_connection() as conn:
            cursor = conn.execute("INSERT INTO tool_executions (plan_step_id, profile_id, tool_name, arguments, result, status, error, completed_at) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", (plan_step_id, profile_id, tool_name, self._json(arguments), self._json(result), status, error))
            if plan_step_id:
                step_status = "completed" if status == "succeeded" else "failed"
                conn.execute("UPDATE plan_steps SET status = ? WHERE id = ?", (step_status, plan_step_id))
            return int(cursor.lastrowid)

    def record_verification(self, execution_id: int, check_name: str, expected: Dict[str, Any], observed: Dict[str, Any], passed: bool, notes: Optional[str] = None) -> int:
        with self.get_connection() as conn:
            cursor = conn.execute("INSERT INTO verifications (execution_id, check_name, expected, observed, status, notes) VALUES (?, ?, ?, ?, ?, ?)", (execution_id, check_name, self._json(expected), self._json(observed), "passed" if passed else "failed", notes))
            return int(cursor.lastrowid)

    def upsert_preference(self, profile_id: int, key: str, value: Any, value_type: str = "text") -> None:
        with self.get_connection() as conn:
            conn.execute("INSERT INTO preferences (profile_id, key, value, value_type) VALUES (?, ?, ?, ?) ON CONFLICT(profile_id, key) DO UPDATE SET value = excluded.value, value_type = excluded.value_type, updated_at = CURRENT_TIMESTAMP", (profile_id, key, json.dumps(value, ensure_ascii=True), value_type))

    def get_preference(self, profile_id: int, key: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT key, value, value_type, updated_at FROM preferences WHERE profile_id = ? AND key = ?",
                (profile_id, key),
            ).fetchone()
        if row is None:
            return None
        return {
            "key": row["key"],
            "value": self._decode(row["value"], row["value"]),
            "value_type": row["value_type"],
            "updated_at": row["updated_at"],
        }

    def create_task(self, profile_id: int, title: str, due_at: Optional[str] = None, description: Optional[str] = None, source_intent_id: Optional[int] = None) -> int:
        with self.get_connection() as conn:
            cursor = conn.execute("INSERT INTO tasks (profile_id, title, description, due_at, source_intent_id) VALUES (?, ?, ?, ?, ?)", (profile_id, title, description, due_at, source_intent_id))
            return int(cursor.lastrowid)

    def list_tasks(self, profile_id: int, status: str = "pending") -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, title, description, due_at, status, source_intent_id, created_at, completed_at
                FROM tasks
                WHERE profile_id = ? AND status = ?
                ORDER BY due_at IS NULL, due_at, created_at
                """,
                (profile_id, status),
            ).fetchall()
        return [dict(row) for row in rows]

    def complete_task(self, profile_id: int, task_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE tasks
                SET status = 'completed', completed_at = CURRENT_TIMESTAMP
                WHERE id = ? AND profile_id = ? AND status = 'pending'
                """,
                (task_id, profile_id),
            )
            return cursor.rowcount == 1

    def append_event(self, profile_id: int, event_type: str, payload: Optional[Dict[str, Any]] = None, entity_type: Optional[str] = None, entity_id: Optional[int] = None) -> int:
        with self.get_connection() as conn:
            cursor = conn.execute("INSERT INTO events (profile_id, event_type, entity_type, entity_id, payload) VALUES (?, ?, ?, ?, ?)", (profile_id, event_type, entity_type, entity_id, self._json(payload)))
            return int(cursor.lastrowid)


db_manager = DatabaseManager()
