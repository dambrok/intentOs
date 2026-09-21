"""Create a small IntentOS sample database for local demonstrations."""

import json
import os
import sqlite3

from database import DatabaseManager


def create_sample_database(path: str = "intentOS-demo.db") -> str:
    """Seed generic IntentOS memory without any shop-specific tables."""
    if os.path.exists(path):
        os.remove(path)

    database = DatabaseManager(path)
    profile_id = database.create_profile("Demo User", language="hi", timezone="Asia/Kolkata")
    session_id = database.create_session(profile_id, "IntentOS demonstration")
    database.add_message(session_id, "user", "Remind me tomorrow to review my sales report.")
    intent_id = database.create_intent(
        profile_id,
        "create_reminder",
        "write",
        entities={"title": "Review sales report", "date": "tomorrow"},
        session_id=session_id,
    )
    database.create_plan(
        intent_id,
        "Create a reminder using the user's default reminder time.",
        [{"tool_name": "create_reminder", "arguments": {"title": "Review sales report"}}],
    )
    database.create_task(profile_id, "Review sales report", "tomorrow", source_intent_id=intent_id)
    database.upsert_preference(profile_id, "default_reminder_time", "09:00", "time")
    execution_id = database.record_execution(
        profile_id,
        "create_reminder",
        {"title": "Review sales report"},
        result={"task_id": 1, "status": "created"},
    )
    database.record_verification(
        execution_id,
        "task_created",
        {"status": "created"},
        {"status": "created"},
        True,
    )
    database.append_event(
        profile_id,
        "demo_seeded",
        {"intent_id": intent_id, "execution_id": execution_id},
    )
    return path


if __name__ == "__main__":
    output_path = create_sample_database()
    connection = sqlite3.connect(output_path)
    table_names = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        )
    ]
    connection.close()
    print(json.dumps({"database": output_path, "tables": table_names}, indent=2))
