"""Validated tools for IntentOS structured memory and execution."""

import json
from typing import Any, Optional

from livekit.agents import RunContext, function_tool

from database import db_manager


ALLOWED_PLAN_TOOLS = frozenset(
    {
        "create_profile",
        "get_schema_manifest",
        "create_conversation",
        "remember",
        "retrieve_memory",
        "create_intent",
        "create_plan",
        "record_tool_execution",
        "verify_action",
        "create_reminder",
        "list_tasks",
        "complete_task",
        "set_preference",
        "get_preference",
        "update_conversation_context",
        "get_conversation_context",
        "record_event",
    }
)


def _parse_json(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


SECRET_MARKERS = (
    "password",
    "passcode",
    "api_key",
    "apikey",
    "secret",
    "token",
    "private_key",
    "otp",
)


def _contains_secret_marker(entity_type: str, name: Optional[str], data: str) -> bool:
    searchable = " ".join((entity_type, name or "", data)).lower()
    return any(marker in searchable for marker in SECRET_MARKERS)


@function_tool
async def create_profile(
    ctx: RunContext,
    name: str,
    language: str = "hi",
    timezone: str = "Asia/Kolkata",
) -> str:
    """Create a local IntentOS profile for the user."""
    try:
        profile_id = db_manager.create_profile(name, language, timezone)
        return f"Profile {profile_id} created for {name}."
    except Exception as exc:
        return f"Profile create nahi ho paya: {exc}"


@function_tool
async def get_schema_manifest(ctx: RunContext) -> str:
    """Return the structured memory map used for schema-guided retrieval."""
    try:
        return json.dumps(db_manager.get_schema_manifest(), ensure_ascii=True)
    except Exception as exc:
        return f"Schema manifest nahi mil paya: {exc}"


@function_tool
async def create_conversation(
    ctx: RunContext,
    profile_id: int,
    title: Optional[str] = None,
) -> str:
    """Start a local conversation session that can retain active task context."""
    try:
        session_id = db_manager.create_session(profile_id, title)
        return f"Conversation session {session_id} created."
    except Exception as exc:
        return f"Conversation create nahi ho payi: {exc}"


@function_tool
async def update_conversation_context(
    ctx: RunContext,
    session_id: int,
    context: str,
) -> str:
    """Persist active entities and task state for unambiguous follow-ups."""
    try:
        parsed_context = json.loads(context)
        if not isinstance(parsed_context, dict):
            return "Conversation context JSON object hona chahiye."
        db_manager.update_session_context(session_id, parsed_context)
        return f"Conversation context for session {session_id} updated."
    except json.JSONDecodeError:
        return "Conversation context valid JSON object hona chahiye."
    except Exception as exc:
        return f"Conversation context update nahi ho paya: {exc}"


@function_tool
async def get_conversation_context(ctx: RunContext, session_id: int) -> str:
    """Retrieve active context for resolving references such as 'them' or 'those'."""
    try:
        return json.dumps(db_manager.get_session_context(session_id), ensure_ascii=True)
    except Exception as exc:
        return f"Conversation context nahi mil paya: {exc}"


@function_tool
async def remember(
    ctx: RunContext,
    profile_id: int,
    entity_type: str,
    name: Optional[str],
    data: str,
    memory_class: str = "context",
    confirmed: bool = False,
) -> str:
    """Store memory using risk-based consent instead of prompting for everything."""
    if memory_class not in {"context", "preference", "personal", "secret"}:
        return "Memory class context, preference, personal, ya secret hona chahiye."
    if _contains_secret_marker(entity_type, name, data) or memory_class == "secret":
        return (
            "Main passwords, API keys, tokens, OTPs, ya secrets ko normal memory mein save nahi karta. "
            "Inhe password manager ya dedicated encrypted secret store mein rakhiye."
        )
    if memory_class == "personal" and not confirmed:
        return (
            "Yeh personal information lagti hai. Kya aap chahte hain ki main ise "
            "local memory mein save karun? Confirm karne par dobara try kijiye."
        )
    try:
        payload = json.loads(data)
        with db_manager.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO entities
                    (profile_id, entity_type, name, data, memory_class, consent_status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    profile_id,
                    entity_type,
                    name,
                    json.dumps(payload, ensure_ascii=True),
                    memory_class,
                    "granted" if memory_class == "personal" else "not_required",
                ),
            )
            entity_id = int(cursor.lastrowid)
        db_manager.append_event(
            profile_id,
            "memory_created",
            {"memory_class": memory_class, "consent_status": "granted" if memory_class == "personal" else "not_required"},
            entity_type,
            entity_id,
        )
        notice = " automatically" if memory_class in {"context", "preference"} else " with consent"
        return f"Memory saved locally{notice} and verified. Entity id: {entity_id}."
    except json.JSONDecodeError:
        return "Memory data valid JSON hona chahiye."
    except Exception as exc:
        return f"Memory save nahi ho payi: {exc}"


@function_tool
async def retrieve_memory(
    ctx: RunContext,
    profile_id: int,
    entity_type: Optional[str] = None,
    name: Optional[str] = None,
) -> str:
    """Retrieve only the requested structured memory records."""
    try:
        clauses = ["profile_id = ?"]
        parameters: list[Any] = [profile_id]
        if entity_type:
            clauses.append("entity_type = ?")
            parameters.append(entity_type)
        if name:
            clauses.append("name = ?")
            parameters.append(name)
        query = f"SELECT id, entity_type, name, data, created_at, updated_at FROM entities WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC"
        with db_manager.get_connection() as conn:
            rows = conn.execute(query, parameters).fetchall()
        result = []
        for row in rows:
            result.append({**dict(row), "data": _parse_json(row["data"], {})})
        return json.dumps(result, ensure_ascii=True)
    except Exception as exc:
        return f"Memory retrieve nahi ho payi: {exc}"


@function_tool
async def create_intent(
    ctx: RunContext,
    profile_id: int,
    name: str,
    action: str,
    entities: str = "{}",
    constraints: str = "{}",
    session_id: Optional[int] = None,
) -> str:
    """Persist a controlled structured interpretation of a user goal."""
    try:
        intent_id = db_manager.create_intent(
            profile_id,
            name,
            action,
            _parse_json(entities, {}),
            _parse_json(constraints, {}),
            session_id,
        )
        return f"Intent {intent_id} identified."
    except Exception as exc:
        return f"Intent save nahi ho paya: {exc}"


@function_tool
async def create_plan(
    ctx: RunContext,
    intent_id: int,
    goal: str,
    steps: str,
) -> str:
    """Create a validated multi-step plan from tool names and JSON arguments."""
    try:
        parsed_steps = json.loads(steps)
        if not isinstance(parsed_steps, list) or not parsed_steps:
            return "Plan mein kam se kam ek step hona chahiye."
        if any("tool_name" not in step for step in parsed_steps):
            return "Har plan step mein tool_name required hai."
        invalid_tools = sorted(
            {
                step["tool_name"]
                for step in parsed_steps
                if not isinstance(step.get("tool_name"), str)
                or step["tool_name"] not in ALLOWED_PLAN_TOOLS
            }
        )
        if invalid_tools:
            return f"Plan mein unregistered tool allowed nahi hai: {', '.join(invalid_tools)}"
        plan_id = db_manager.create_plan(intent_id, goal, parsed_steps)
        return f"Plan {plan_id} created with {len(parsed_steps)} verified steps."
    except json.JSONDecodeError:
        return "Steps valid JSON array hona chahiye."
    except Exception as exc:
        return f"Plan create nahi ho paya: {exc}"


@function_tool
async def record_tool_execution(
    ctx: RunContext,
    profile_id: int,
    tool_name: str,
    arguments: str = "{}",
    result: str = "{}",
    status: str = "succeeded",
    plan_step_id: Optional[int] = None,
    error: Optional[str] = None,
) -> str:
    """Record a controlled tool call and its result for audit and recovery."""
    if status not in {"started", "succeeded", "failed"}:
        return "Status started, succeeded, ya failed hona chahiye."
    try:
        execution_id = db_manager.record_execution(
            profile_id,
            tool_name,
            _parse_json(arguments, {}),
            plan_step_id,
            _parse_json(result, result),
            status,
            error,
        )
        return f"Tool execution {execution_id} recorded as {status}."
    except Exception as exc:
        return f"Tool execution log nahi ho paya: {exc}"


@function_tool
async def verify_action(
    ctx: RunContext,
    execution_id: int,
    check_name: str,
    expected: str,
    observed: str,
    passed: bool,
    notes: Optional[str] = None,
) -> str:
    """Record observed state after an action and make verification explicit."""
    try:
        verification_id = db_manager.record_verification(
            execution_id,
            check_name,
            _parse_json(expected, {}),
            _parse_json(observed, {}),
            passed,
            notes,
        )
        status = "passed" if passed else "failed"
        return f"Verification {verification_id}: {status}."
    except Exception as exc:
        return f"Verification save nahi ho payi: {exc}"


@function_tool
async def create_reminder(
    ctx: RunContext,
    profile_id: int,
    title: str,
    due_at: Optional[str] = None,
    description: Optional[str] = None,
    source_intent_id: Optional[int] = None,
) -> str:
    """Create a future task in local IntentOS memory."""
    try:
        task_id = db_manager.create_task(profile_id, title, due_at, description, source_intent_id)
        db_manager.append_event(profile_id, "task_created", {"title": title, "due_at": due_at}, "tasks", task_id)
        return f"Reminder {task_id} created for {due_at or 'the requested time'}."
    except Exception as exc:
        return f"Reminder create nahi ho paya: {exc}"


@function_tool
async def list_tasks(
    ctx: RunContext,
    profile_id: int,
    status: str = "pending",
) -> str:
    """List local tasks by status for retrieval and verification."""
    if status not in {"pending", "completed", "cancelled"}:
        return "Status pending, completed, ya cancelled hona chahiye."
    try:
        return json.dumps(db_manager.list_tasks(profile_id, status), ensure_ascii=True)
    except Exception as exc:
        return f"Tasks retrieve nahi ho paye: {exc}"


@function_tool
async def complete_task(ctx: RunContext, profile_id: int, task_id: int) -> str:
    """Mark one pending task complete and report whether state changed."""
    try:
        completed = db_manager.complete_task(profile_id, task_id)
        if not completed:
            return f"Task {task_id} pending nahi hai ya profile se match nahi karta."
        db_manager.append_event(profile_id, "task_completed", {}, "tasks", task_id)
        return f"Task {task_id} completed and verified."
    except Exception as exc:
        return f"Task complete nahi ho paya: {exc}"


@function_tool
async def set_preference(
    ctx: RunContext,
    profile_id: int,
    key: str,
    value: str,
    value_type: str = "text",
) -> str:
    """Store a persistent local preference such as default reminder time."""
    if _contains_secret_marker(key, None, value):
        return "Secrets ko preference memory mein save nahi karta. Dedicated encrypted secret storage use kijiye."
    try:
        parsed_value = _parse_json(value, value)
        db_manager.upsert_preference(profile_id, key, parsed_value, value_type)
        return f"Preference '{key}' saved locally and verified."
    except Exception as exc:
        return f"Preference save nahi ho payi: {exc}"


@function_tool
async def get_preference(ctx: RunContext, profile_id: int, key: str) -> str:
    """Retrieve one persistent preference for personalization."""
    try:
        preference = db_manager.get_preference(profile_id, key)
        if preference is None:
            return f"Preference '{key}' set nahi hai."
        return json.dumps(preference, ensure_ascii=True)
    except Exception as exc:
        return f"Preference retrieve nahi ho payi: {exc}"


@function_tool
async def record_event(
    ctx: RunContext,
    profile_id: int,
    event_type: str,
    payload: str = "{}",
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
) -> str:
    """Append an operational event to local history."""
    try:
        event_id = db_manager.append_event(profile_id, event_type, _parse_json(payload, {}), entity_type, entity_id)
        return f"Event {event_id} recorded."
    except Exception as exc:
        return f"Event record nahi ho paya: {exc}"


ALL_TOOLS = [
    create_profile,
    get_schema_manifest,
    create_conversation,
    update_conversation_context,
    get_conversation_context,
    remember,
    retrieve_memory,
    create_intent,
    create_plan,
    record_tool_execution,
    verify_action,
    create_reminder,
    list_tasks,
    complete_task,
    set_preference,
    get_preference,
    record_event,
]
