"""Small IntentOS database smoke test."""

import tempfile
from pathlib import Path

from database import DatabaseManager


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        database = DatabaseManager(str(Path(directory) / "smoke.db"))
        profile_id = database.create_profile("Smoke Test")
        session_id = database.create_session(profile_id, "Smoke test")
        intent_id = database.create_intent(profile_id, "inspect_memory", "query", session_id=session_id)
        plan_id = database.create_plan(
            intent_id,
            "Read structured memory",
            [{"tool_name": "retrieve_memory", "arguments": {}}],
        )
        execution_id = database.record_execution(profile_id, "retrieve_memory", result={"records": []})
        database.record_verification(
            execution_id,
            "query_completed",
            {"status": "succeeded"},
            {"status": "succeeded"},
            True,
        )
        print(f"IntentOS smoke test passed: profile={profile_id}, plan={plan_id}")


if __name__ == "__main__":
    main()
