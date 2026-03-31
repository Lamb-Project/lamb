"""Assistant test scenarios, test runner, and evaluation service.

Provides CRUD for test scenarios, execution through the real completion
pipeline, and evaluation recording.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from typing import Any, Optional

from lamb.database_manager import LambDatabaseManager
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="TEST")


class TestService:
    """Manage test scenarios, runs, and evaluations."""

    def __init__(self):
        self.db = LambDatabaseManager()
        self._prefix = self.db.table_prefix

    # ------------------------------------------------------------------
    # Scenarios
    # ------------------------------------------------------------------

    def create_scenario(
        self,
        assistant_id: int,
        title: str,
        messages: list[dict],
        created_by: str,
        description: str = "",
        scenario_type: str = "single_turn",
        expected_behavior: str = "",
        tags: list[str] | None = None,
    ) -> dict:
        scenario_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"""INSERT INTO {self._prefix}assistant_test_scenarios
                (id, assistant_id, title, description, scenario_type, messages,
                 expected_behavior, tags, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (scenario_id, assistant_id, title, description, scenario_type,
                 json.dumps(messages, ensure_ascii=False),
                 expected_behavior,
                 json.dumps(tags or [], ensure_ascii=False),
                 created_by, now, now),
            )
            conn.commit()
        finally:
            conn.close()
        return {"id": scenario_id, "title": title, "assistant_id": assistant_id}

    def list_scenarios(self, assistant_id: int) -> list[dict]:
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"""SELECT id, assistant_id, title, description, scenario_type,
                    messages, expected_behavior, tags, created_by, created_at, updated_at
                    FROM {self._prefix}assistant_test_scenarios
                    WHERE assistant_id = ? ORDER BY created_at""",
                (assistant_id,),
            )
            columns = [d[0] for d in cursor.description]
            rows = []
            for row in cursor.fetchall():
                d = dict(zip(columns, row))
                d["messages"] = json.loads(d.get("messages", "[]"))
                d["tags"] = json.loads(d.get("tags", "[]"))
                rows.append(d)
            return rows
        finally:
            conn.close()

    def get_scenario(self, scenario_id: str) -> Optional[dict]:
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT * FROM {self._prefix}assistant_test_scenarios WHERE id = ?",
                (scenario_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            columns = [d[0] for d in cursor.description]
            d = dict(zip(columns, row))
            d["messages"] = json.loads(d.get("messages", "[]"))
            d["tags"] = json.loads(d.get("tags", "[]"))
            return d
        finally:
            conn.close()

    def update_scenario(self, scenario_id: str, updates: dict) -> bool:
        allowed = {"title", "description", "scenario_type", "messages",
                   "expected_behavior", "tags"}
        fields = {k: v for k, v in updates.items() if k in allowed}
        if not fields:
            return False
        if "messages" in fields:
            fields["messages"] = json.dumps(fields["messages"], ensure_ascii=False)
        if "tags" in fields:
            fields["tags"] = json.dumps(fields["tags"], ensure_ascii=False)
        fields["updated_at"] = datetime.utcnow().isoformat()

        set_clause = ", ".join(f"{k} = ?" for k in fields)
        params = list(fields.values()) + [scenario_id]

        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE {self._prefix}assistant_test_scenarios SET {set_clause} WHERE id = ?",
                params,
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_scenario(self, scenario_id: str) -> bool:
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"DELETE FROM {self._prefix}assistant_test_scenarios WHERE id = ?",
                (scenario_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Test runner
    # ------------------------------------------------------------------

    async def run_scenario(
        self,
        assistant_id: int,
        scenario_id: str | None,
        messages: list[dict],
        user_email: str,
    ) -> dict:
        """Run a test completion through the real pipeline.

        Calls the completion endpoint internally with stream=False.
        Returns the test run record with response and token usage.
        """
        from lamb.services.assistant_service import AssistantService

        svc = AssistantService()
        assistant = svc.get_assistant_by_id(assistant_id)
        if not assistant:
            raise ValueError(f"Assistant {assistant_id} not found")

        # Build completion request (same format as production)
        request_body = {
            "model": f"lamb_assistant.{assistant_id}",
            "messages": messages,
            "stream": False,
        }

        # Call the internal completion pipeline
        from lamb.completions.main import (
            get_assistant_details, parse_plugin_config,
            load_and_validate_plugins, get_rag_context,
            process_completion_request, load_plugins,
        )

        start_time = time.monotonic()
        try:
            assistant_details = get_assistant_details(assistant_id)
            plugin_config = parse_plugin_config(assistant_details)

            pps, connectors, rag_processors = load_and_validate_plugins(plugin_config)
            rag_context = await get_rag_context(
                request_body, rag_processors,
                plugin_config["rag_processor"], assistant_details,
            )
            processed_messages = process_completion_request(
                request_body, assistant_details, plugin_config, rag_context, pps,
            )

            result = await connectors[plugin_config["connector"]](
                processed_messages,
                stream=False,
                body=request_body,
                llm=plugin_config["llm"],
                assistant_owner=assistant_details.owner,
            )
            elapsed_ms = (time.monotonic() - start_time) * 1000
        except Exception as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            logger.error(f"Test run failed for assistant {assistant_id}: {e}")
            raise ValueError(f"Completion failed: {e}")

        # Extract response and usage
        if isinstance(result, dict):
            output = result
            token_usage = result.get("usage", {})
            model_used = result.get("model", plugin_config.get("llm", ""))
        else:
            output = {"raw": str(result)}
            token_usage = {}
            model_used = plugin_config.get("llm", "")

        # Build assistant snapshot
        snapshot = {
            "system_prompt": assistant.system_prompt[:500] if assistant.system_prompt else "",
            "llm": plugin_config.get("llm", ""),
            "connector": plugin_config.get("connector", ""),
            "rag_processor": plugin_config.get("rag_processor", ""),
            "prompt_processor": plugin_config.get("prompt_processor", ""),
        }

        # Save test run
        run_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"""INSERT INTO {self._prefix}assistant_test_runs
                (id, assistant_id, scenario_id, input_messages, output,
                 token_usage, assistant_snapshot, model_used, elapsed_ms, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, assistant_id, scenario_id,
                 json.dumps(messages, ensure_ascii=False),
                 json.dumps(output, default=str, ensure_ascii=False),
                 json.dumps(token_usage, ensure_ascii=False),
                 json.dumps(snapshot, ensure_ascii=False),
                 model_used, round(elapsed_ms, 1), now),
            )
            conn.commit()
        finally:
            conn.close()

        # Extract assistant response text
        response_text = ""
        if isinstance(output, dict):
            choices = output.get("choices", [])
            if choices:
                response_text = choices[0].get("message", {}).get("content", "")

        return {
            "id": run_id,
            "assistant_id": assistant_id,
            "scenario_id": scenario_id,
            "input_messages": messages,
            "response": response_text,
            "token_usage": token_usage,
            "model_used": model_used,
            "elapsed_ms": round(elapsed_ms, 1),
            "created_at": now,
        }

    async def run_all_scenarios(self, assistant_id: int, user_email: str) -> list[dict]:
        """Run all scenarios for an assistant."""
        scenarios = self.list_scenarios(assistant_id)
        results = []
        for s in scenarios:
            try:
                result = await self.run_scenario(
                    assistant_id=assistant_id,
                    scenario_id=s["id"],
                    messages=s["messages"],
                    user_email=user_email,
                )
                results.append(result)
            except Exception as e:
                results.append({
                    "scenario_id": s["id"],
                    "title": s["title"],
                    "error": str(e),
                })
        return results

    # ------------------------------------------------------------------
    # Test runs
    # ------------------------------------------------------------------

    def list_runs(self, assistant_id: int, limit: int = 50) -> list[dict]:
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"""SELECT id, assistant_id, scenario_id, input_messages, output,
                    token_usage, model_used, elapsed_ms, created_at
                    FROM {self._prefix}assistant_test_runs
                    WHERE assistant_id = ? ORDER BY created_at DESC LIMIT ?""",
                (assistant_id, limit),
            )
            columns = [d[0] for d in cursor.description]
            rows = []
            for row in cursor.fetchall():
                d = dict(zip(columns, row))
                d["input_messages"] = json.loads(d.get("input_messages", "[]"))
                d["token_usage"] = json.loads(d.get("token_usage", "{}"))
                # Extract response text for display
                output = json.loads(d.get("output", "{}"))
                choices = output.get("choices", [])
                d["response"] = choices[0].get("message", {}).get("content", "") if choices else ""
                del d["output"]  # Don't send raw output in list view
                rows.append(d)
            return rows
        finally:
            conn.close()

    def get_run(self, run_id: str) -> Optional[dict]:
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT * FROM {self._prefix}assistant_test_runs WHERE id = ?",
                (run_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            columns = [d[0] for d in cursor.description]
            d = dict(zip(columns, row))
            d["input_messages"] = json.loads(d.get("input_messages", "[]"))
            d["output"] = json.loads(d.get("output", "{}"))
            d["token_usage"] = json.loads(d.get("token_usage", "{}"))
            d["assistant_snapshot"] = json.loads(d.get("assistant_snapshot", "{}"))
            return d
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Evaluations
    # ------------------------------------------------------------------

    def create_evaluation(
        self,
        test_run_id: str,
        evaluator: str,
        verdict: str,
        notes: str = "",
        dimensions: dict | None = None,
    ) -> dict:
        eval_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"""INSERT INTO {self._prefix}assistant_test_evaluations
                (id, test_run_id, evaluator, verdict, notes, dimensions, confirmed_by_user, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (eval_id, test_run_id, evaluator, verdict, notes,
                 json.dumps(dimensions, ensure_ascii=False) if dimensions else None,
                 True if evaluator == "user" else None,
                 now),
            )
            conn.commit()
        finally:
            conn.close()
        return {"id": eval_id, "test_run_id": test_run_id, "verdict": verdict}

    def list_evaluations(self, assistant_id: int) -> list[dict]:
        """List evaluations for all test runs of an assistant."""
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"""SELECT e.id, e.test_run_id, e.evaluator, e.verdict, e.notes,
                    e.confirmed_by_user, e.created_at, r.scenario_id, r.model_used
                    FROM {self._prefix}assistant_test_evaluations e
                    JOIN {self._prefix}assistant_test_runs r ON e.test_run_id = r.id
                    WHERE r.assistant_id = ?
                    ORDER BY e.created_at DESC""",
                (assistant_id,),
            )
            columns = [d[0] for d in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            conn.close()
