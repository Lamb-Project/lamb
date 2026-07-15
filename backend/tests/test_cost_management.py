"""Tests for cost management — cache-aware token costs & model breakdown."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_BACKEND_ROOT = Path(__file__).parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Create a temporary SQLite DB and run all migrations.

    LambDatabaseManager.__init__ reads config.LAMB_DB_PATH and takes no args,
    so we monkeypatch the config module before instantiation.
    database_manager.py imports config as a top-level module (not lamb.config).
    
    We also patch initialize_system_organization() to avoid OWI dependency in CI.
    """
    import config
    monkeypatch.setattr(config, "LAMB_DB_PATH", str(tmp_path))
    monkeypatch.setattr(config, "LAMB_DB_PREFIX", "")
    from lamb.database_manager import LambDatabaseManager
    monkeypatch.setattr(LambDatabaseManager, "initialize_system_organization", lambda self: None)
    dm = LambDatabaseManager()
    yield dm, str(tmp_path / "lamb_v4.db")


class TestMigration18:
    def test_model_pricing_has_cached_input_column(self, fresh_db):
        dm, _ = fresh_db
        conn = dm.get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(model_pricing)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()
        assert "cached_input_per_1m" in columns

    def test_assistant_usage_totals_has_cache_columns(self, fresh_db):
        dm, _ = fresh_db
        conn = dm.get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(assistant_usage_totals)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()
        assert "cached_prompt_tokens_total" in columns
        assert "non_cached_prompt_tokens_total" in columns

    def test_model_pricing_seed_includes_cached_rates(self, fresh_db):
        dm, _ = fresh_db
        conn = dm.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT model_name, cached_input_per_1m FROM model_pricing WHERE provider = 'openai' AND model_name = 'gpt-4o'"
        )
        row = cursor.fetchone()
        conn.close()
        assert row is not None
        assert row[1] is not None
        assert row[1] > 0


class TestLogTokenUsageCacheAware:
    def test_cost_with_cached_tokens(self, fresh_db):
        dm, _ = fresh_db
        conn = dm.get_connection()
        conn.execute("INSERT INTO organizations (id, name, slug, status, config, created_at, updated_at) VALUES (1, 'TestOrg', 'test-org', 'active', '{}', 1700000000, 1700000000)")
        conn.execute(
            "INSERT INTO assistants (id, name, owner, organization_id, api_callback, created_at, updated_at) VALUES (1, 'Bot', 'a@b.com', 1, '{}', 1700000000, 1700000000)"
        )
        conn.commit()
        conn.close()

        usage_data = {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500,
            "prompt_tokens_details": {"cached_tokens": 800},
        }
        dm.log_token_usage(
            assistant_id=1, org_id=1, model_name="gpt-4o",
            provider="openai", usage_data=usage_data
        )

        conn = dm.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT cache_read_tokens_total, cache_write_tokens_total, non_cached_prompt_tokens_total, prompt_tokens_total, cost_usd_total FROM assistant_usage_totals WHERE assistant_id = 1")
        row = cursor.fetchone()
        conn.close()

        assert row[0] == 800   # cache_read
        assert row[1] == 0     # cache_write (OpenAI auto-cache)
        assert row[2] == 200   # non_cached
        assert row[3] == 1000  # total prompt
        # cost = (200 * 2.50/1e6) + (800 * 1.25/1e6) + (500 * 10.0/1e6)
        expected_cost = (200 * 2.50 / 1e6) + (800 * 1.25 / 1e6) + (500 * 10.0 / 1e6)
        assert abs(row[4] - expected_cost) < 1e-9

    def test_cost_without_cached_tokens_falls_back(self, fresh_db):
        dm, _ = fresh_db
        conn = dm.get_connection()
        conn.execute("INSERT INTO organizations (id, name, slug, status, config, created_at, updated_at) VALUES (1, 'TestOrg', 'test-org', 'active', '{}', 1700000000, 1700000000)")
        conn.execute(
            "INSERT INTO assistants (id, name, owner, organization_id, api_callback, created_at, updated_at) VALUES (2, 'Bot2', 'a@b.com', 1, '{}', 1700000000, 1700000000)"
        )
        conn.commit()
        conn.close()

        usage_data = {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500,
        }
        dm.log_token_usage(
            assistant_id=2, org_id=1, model_name="gpt-4o",
            provider="openai", usage_data=usage_data
        )

        conn = dm.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT cache_read_tokens_total, cache_write_tokens_total, non_cached_prompt_tokens_total, prompt_tokens_total, cost_usd_total FROM assistant_usage_totals WHERE assistant_id = 2")
        row = cursor.fetchone()
        conn.close()

        assert row[0] == 0     # no cache_read
        assert row[1] == 0     # no cache_write
        assert row[2] == 1000  # all non-cached
        assert row[3] == 1000
        expected_cost = (1000 * 2.50 / 1e6) + (500 * 10.0 / 1e6)
        assert abs(row[4] - expected_cost) < 1e-9

    def test_cost_no_pricing_row_returns_zero(self, fresh_db):
        dm, _ = fresh_db
        conn = dm.get_connection()
        conn.execute("INSERT INTO organizations (id, name, slug, status, config, created_at, updated_at) VALUES (1, 'TestOrg', 'test-org', 'active', '{}', 1700000000, 1700000000)")
        conn.execute(
            "INSERT INTO assistants (id, name, owner, organization_id, api_callback, created_at, updated_at) VALUES (3, 'Bot3', 'a@b.com', 1, '{}', 1700000000, 1700000000)"
        )
        conn.commit()
        conn.close()

        usage_data = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
        dm.log_token_usage(
            assistant_id=3, org_id=1, model_name="unknown-model",
            provider="openai", usage_data=usage_data
        )

        conn = dm.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT cost_usd_total FROM assistant_usage_totals WHERE assistant_id = 3")
        row = cursor.fetchone()
        conn.close()
        assert row[0] == 0.0

    def test_usage_logs_stores_full_json(self, fresh_db):
        dm, _ = fresh_db
        conn = dm.get_connection()
        conn.execute("INSERT INTO organizations (id, name, slug, status, config, created_at, updated_at) VALUES (1, 'TestOrg', 'test-org', 'active', '{}', 1700000000, 1700000000)")
        conn.execute(
            "INSERT INTO assistants (id, name, owner, organization_id, api_callback, created_at, updated_at) VALUES (4, 'Bot4', 'a@b.com', 1, '{}', 1700000000, 1700000000)"
        )
        conn.commit()
        conn.close()

        usage_data = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "prompt_tokens_details": {"cached_tokens": 80},
            "extra_field": "preserved",
        }
        dm.log_token_usage(
            assistant_id=4, org_id=1, model_name="gpt-4o",
            provider="openai", usage_data=usage_data
        )

        import json
        conn = dm.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT usage_data FROM usage_logs WHERE assistant_id = 4")
        row = cursor.fetchone()
        conn.close()
        stored = json.loads(row[0])
        assert stored["prompt_tokens_details"]["cached_tokens"] == 80
        assert stored["extra_field"] == "preserved"

    def test_logging_failure_does_not_raise(self, fresh_db):
        dm, _ = fresh_db
        # Should not raise even with invalid assistant_id (FK might not be enforced in SQLite by default)
        dm.log_token_usage(
            assistant_id=99999, org_id=1, model_name="x",
            provider="x", usage_data={}
        )


# Shared fixture for admin API tests — patches security + verify_admin_access
@pytest.fixture
def admin_client(monkeypatch):
    """TestClient with admin auth bypassed for organization_router endpoints.

    Routes use dependencies=[Depends(security)] + manual verify_admin_access(request),
    NOT get_auth_context. We must patch both.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from creator_interface.organization_router import router
    from creator_interface import organization_router as org_router

    async def _noop_verify(request):
        return "test-token"

    monkeypatch.setattr(org_router, "verify_admin_access", _noop_verify)

    app = FastAPI()
    app.include_router(router, prefix="/admin")
    app.dependency_overrides[org_router.security] = lambda: {"credentials": "test-token"}

    return TestClient(app)


class TestCostOverviewAPI:
    def test_cost_overview_includes_summary(self, admin_client, monkeypatch):
        from creator_interface import organization_router as org_router

        mock_rows = [
            {
                "id": 1, "name": "Bot", "owner": "a@b.com",
                "organization_name": "TestOrg", "organization_id": 1,
                "api_callback": '{"llm": "gpt-4o", "connector": "openai"}',
                "prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500,
                "cost_usd": 0.01, "thresholds_config": None,
                "cache_read_tokens": 800, "cache_write_tokens": 0, "non_cached_prompt_tokens": 200,
            }
        ]
        mock_db = MagicMock()
        mock_db.get_all_assistants_with_usage.return_value = mock_rows
        monkeypatch.setattr(org_router, "db_manager", mock_db)

        resp = admin_client.get("/admin/cost-overview", headers={"Authorization": "Bearer test-token"})
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "assistants" in data
        assert data["assistants"][0]["organization_id"] == 1
        assert data["assistants"][0]["cache_read_tokens"] == 800
        assert data["assistants"][0]["cache_write_tokens"] == 0
        assert data["assistants"][0]["non_cached_prompt_tokens"] == 200
        assert "cache_hit_percentage" in data["assistants"][0]
        assert data["summary"]["total_cost_usd"] == 0.01
        assert data["summary"]["cache_read_tokens"] == 800
        assert data["summary"]["cache_write_tokens"] == 0


class TestUsageByModelAPI:
    def test_usage_by_model_returns_breakdown(self, admin_client, monkeypatch):
        from creator_interface import organization_router as org_router

        mock_db = MagicMock()
        mock_db.get_assistant_usage_by_model.return_value = [
            {
                "provider": "openai",
                "model_name": "gpt-4o",
                "prompt_tokens": 12000,
                "non_cached_prompt_tokens": 3000,
                "cache_read_tokens": 9000,
                "cache_write_tokens": 0,
                "completion_tokens": 8000,
                "total_tokens": 20000,
                "cost_usd": 0.42,
                "request_count": 85,
                "pricing": {
                    "input_per_1m": 2.50,
                    "cache_read_per_1m": 1.25,
                    "cache_write_per_1m": None,
                    "output_per_1m": 10.0,
                    "requires_explicit_cache": False,
                },
            }
        ]
        mock_db.get_assistant_by_id.return_value = MagicMock()
        monkeypatch.setattr(org_router, "db_manager", mock_db)

        resp = admin_client.get("/admin/assistant/10/usage-by-model", headers={"Authorization": "Bearer test-token"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["assistant_id"] == 10
        assert len(data["breakdown"]) == 1
        assert data["breakdown"][0]["model_name"] == "gpt-4o"
        assert data["breakdown"][0]["pricing"]["cache_read_per_1m"] == 1.25
        assert data["breakdown"][0]["cache_read_tokens"] == 9000
        assert data["breakdown"][0]["cache_write_tokens"] == 0


class TestExplicitCache:
    def test_apply_markers_single_message(self):
        from lamb.completions.explicit_cache import apply_cache_markers
        messages = [{"role": "user", "content": "Hello"}]
        result = apply_cache_markers(messages)
        assert len(result) == 1
        content = result[0]["content"]
        assert isinstance(content, list)
        assert any(block.get("cache_control") == {"type": "ephemeral"} for block in content)

    def test_apply_markers_multi_turn(self):
        from lamb.completions.explicit_cache import apply_cache_markers
        messages = [
            {"role": "system", "content": "You are a tutor"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
            {"role": "user", "content": "Question?"},
        ]
        result = apply_cache_markers(messages)
        assert len(result) == 4
        marker_idx = len(messages) - 2
        marked_content = result[marker_idx]["content"]
        assert isinstance(marked_content, list)
        assert any(block.get("cache_control") == {"type": "ephemeral"} for block in marked_content)

    def test_does_not_mutate_original(self):
        from lamb.completions.explicit_cache import apply_cache_markers
        import copy
        messages = [{"role": "user", "content": "Hello"}]
        original = copy.deepcopy(messages)
        apply_cache_markers(messages)
        assert messages == original

    def test_empty_messages(self):
        from lamb.completions.explicit_cache import apply_cache_markers
        result = apply_cache_markers([])
        assert result == []


class TestOrgSearchAPI:
    def test_org_search_returns_matches(self, admin_client, monkeypatch):
        from creator_interface import organization_router as org_router
        mock_db = MagicMock()
        mock_db.search_organizations.return_value = [
            {"id": 3, "name": "PEPESITO", "slug": "pepesito"}
        ]
        monkeypatch.setattr(org_router, "db_manager", mock_db)

        resp = admin_client.get("/admin/organizations/search?name=pepe", headers={"Authorization": "Bearer test-token"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["organizations"]) == 1
        assert data["organizations"][0]["name"] == "PEPESITO"

    def test_org_summary_scoped_to_org(self, admin_client, monkeypatch):
        from creator_interface import organization_router as org_router
        mock_db = MagicMock()
        mock_db.get_org_scoped_summary.return_value = {
            "total_cost_usd": 0.5,
            "total_tokens": 1000,
            "prompt_tokens": 600,
            "completion_tokens": 400,
            "cache_read_tokens": 300,
            "cache_write_tokens": 50,
            "assistant_count": 2,
            "quota_exceeded_count": 0,
        }
        monkeypatch.setattr(org_router, "db_manager", mock_db)

        resp = admin_client.get("/admin/cost-overview/summary?organization_id=3", headers={"Authorization": "Bearer test-token"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total_cost_usd"] == 0.5
        assert data["summary"]["assistant_count"] == 2


class TestModelPricingCRUD:
    def test_list_pricing(self, admin_client, monkeypatch):
        from creator_interface import organization_router as org_router
        mock_db = MagicMock()
        mock_db.list_model_pricing.return_value = [
            {"id": 1, "provider": "openai", "model_name": "gpt-4o",
             "input_per_1m": 2.5, "cache_read_per_1m": 1.25, "cache_write_per_1m": None,
             "output_per_1m": 10.0, "requires_explicit_cache": False, "updated_at": 1000}
        ]
        monkeypatch.setattr(org_router, "db_manager", mock_db)

        resp = admin_client.get("/admin/model-pricing", headers={"Authorization": "Bearer test-token"})
        assert resp.status_code == 200
        assert len(resp.json()["pricing"]) == 1

    def test_create_pricing(self, admin_client, monkeypatch):
        from creator_interface import organization_router as org_router
        mock_db = MagicMock()
        mock_db.create_model_pricing.return_value = {
            "id": 10, "provider": "openai", "model_name": "gpt-5",
            "input_per_1m": 5.0, "cache_read_per_1m": 2.5, "cache_write_per_1m": None,
            "output_per_1m": 20.0, "requires_explicit_cache": False, "updated_at": 2000
        }
        monkeypatch.setattr(org_router, "db_manager", mock_db)

        resp = admin_client.post("/admin/model-pricing", json={
            "provider": "openai", "model_name": "gpt-5",
            "input_per_1m": 5.0, "cache_read_per_1m": 2.5, "output_per_1m": 20.0
        }, headers={"Authorization": "Bearer test-token"})
        assert resp.status_code == 200
        assert resp.json()["model_name"] == "gpt-5"

    def test_update_pricing(self, admin_client, monkeypatch):
        from creator_interface import organization_router as org_router
        mock_db = MagicMock()
        mock_db.update_model_pricing.return_value = {
            "id": 1, "provider": "openai", "model_name": "gpt-4o",
            "input_per_1m": 3.0, "cache_read_per_1m": 1.5, "cache_write_per_1m": None,
            "output_per_1m": 12.0, "requires_explicit_cache": False, "updated_at": 3000
        }
        monkeypatch.setattr(org_router, "db_manager", mock_db)

        resp = admin_client.put("/admin/model-pricing/1", json={
            "input_per_1m": 3.0, "cached_input_per_1m": 1.5, "output_per_1m": 12.0
        }, headers={"Authorization": "Bearer test-token"})
        assert resp.status_code == 200
        assert resp.json()["input_per_1m"] == 3.0

    def test_delete_pricing(self, admin_client, monkeypatch):
        from creator_interface import organization_router as org_router
        mock_db = MagicMock()
        mock_db.delete_model_pricing.return_value = True
        monkeypatch.setattr(org_router, "db_manager", mock_db)

        resp = admin_client.delete("/admin/model-pricing/1", headers={"Authorization": "Bearer test-token"})
        assert resp.status_code == 200


class TestMigration19:
    def test_model_pricing_has_cache_write_column(self, fresh_db):
        dm, _ = fresh_db
        conn = dm.get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(model_pricing)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()
        assert "cache_write_per_1m" in columns

    def test_model_pricing_has_requires_explicit_cache_column(self, fresh_db):
        dm, _ = fresh_db
        conn = dm.get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(model_pricing)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()
        assert "requires_explicit_cache" in columns

    def test_model_pricing_has_cache_read_per_1m_column(self, fresh_db):
        dm, _ = fresh_db
        conn = dm.get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(model_pricing)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()
        assert "cache_read_per_1m" in columns

    def test_assistant_usage_totals_has_cache_write_column(self, fresh_db):
        dm, _ = fresh_db
        conn = dm.get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(assistant_usage_totals)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()
        assert "cache_write_tokens_total" in columns

    def test_assistant_usage_totals_has_cache_read_column(self, fresh_db):
        dm, _ = fresh_db
        conn = dm.get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(assistant_usage_totals)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()
        assert "cache_read_tokens_total" in columns

    def test_usage_logs_has_cost_usd_column(self, fresh_db):
        dm, _ = fresh_db
        conn = dm.get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(usage_logs)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()
        assert "cost_usd" in columns

    def test_qwen_seed_row_exists(self, fresh_db):
        dm, _ = fresh_db
        conn = dm.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT model_name, requires_explicit_cache, cache_read_per_1m, cache_write_per_1m "
            "FROM model_pricing WHERE provider = 'openai' AND model_name = 'qwen3.6-plus'"
        )
        row = cursor.fetchone()
        conn.close()
        assert row is not None
        assert row[1] == 1  # requires_explicit_cache
        assert row[2] is not None and row[2] > 0  # cache_read_per_1m
        assert row[3] is not None and row[3] > 0  # cache_write_per_1m

    def test_qwen_seed_has_notes(self, fresh_db):
        dm, _ = fresh_db
        conn = dm.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT notes FROM model_pricing WHERE provider = 'openai' AND model_name = 'qwen3.6-plus'"
        )
        row = cursor.fetchone()
        conn.close()
        assert row is not None
        assert "Alibaba" in (row[0] or "")


class TestMigration13Fix:
    def test_startup_does_not_recalculate_cost(self, fresh_db):
        """After logging usage at pricing v1, restarting (re-init) must not change cost_usd_total."""
        dm, db_path = fresh_db
        conn = dm.get_connection()
        conn.execute("INSERT INTO organizations (id, name, slug, status, config, created_at, updated_at) VALUES (1, 'TestOrg', 'test-org', 'active', '{}', 1700000000, 1700000000)")
        conn.execute(
            "INSERT INTO assistants (id, name, owner, organization_id, api_callback, created_at, updated_at) VALUES (1, 'Bot', 'a@b.com', 1, '{}', 1700000000, 1700000000)"
        )
        conn.commit()
        conn.close()

        usage_data = {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500,
            "prompt_tokens_details": {"cached_tokens": 800},
        }
        dm.log_token_usage(assistant_id=1, org_id=1, model_name="gpt-4o", provider="openai", usage_data=usage_data)

        conn = dm.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT cost_usd_total FROM assistant_usage_totals WHERE assistant_id = 1")
        cost_before = cursor.fetchone()[0]
        conn.close()

        # Change pricing to v2
        conn = dm.get_connection()
        conn.execute("UPDATE model_pricing SET input_per_1m = 99.0, output_per_1m = 99.0 WHERE provider = 'openai' AND model_name = 'gpt-4o'")
        conn.commit()
        conn.close()

        # Simulate backend restart by re-running migrations
        import config
        from lamb.database_manager import LambDatabaseManager
        dm2 = LambDatabaseManager()

        conn = dm2.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT cost_usd_total FROM assistant_usage_totals WHERE assistant_id = 1")
        cost_after = cursor.fetchone()[0]
        conn.close()

        assert abs(cost_before - cost_after) < 1e-9, f"Cost changed from {cost_before} to {cost_after} after restart"


class TestTokenRepartition:
    def test_openai_auto_cache(self):
        from lamb.completions.token_repartition import extract_token_buckets
        usage_data = {
            "prompt_tokens": 10000,
            "completion_tokens": 2000,
            "prompt_tokens_details": {"cached_tokens": 7000},
        }
        result = extract_token_buckets(usage_data)
        assert result["cache_read"] == 7000
        assert result["cache_write"] == 0
        assert result["non_cached"] == 3000
        assert result["prompt_tokens"] == 10000
        assert result["completion_tokens"] == 2000

    def test_alibaba_explicit_cache(self):
        from lamb.completions.token_repartition import extract_token_buckets
        usage_data = {
            "prompt_tokens": 19156,
            "completion_tokens": 957,
            "prompt_tokens_details": {
                "cached_tokens": 0,
                "cache_creation_input_tokens": 18198,
                "cache_creation": {"ephemeral_5m_input_tokens": 18198},
            },
        }
        result = extract_token_buckets(usage_data)
        assert result["cache_read"] == 0
        assert result["cache_write"] == 18198
        assert result["non_cached"] == 958
        assert result["prompt_tokens"] == 19156

    def test_no_cache_details(self):
        from lamb.completions.token_repartition import extract_token_buckets
        usage_data = {"prompt_tokens": 500, "completion_tokens": 100}
        result = extract_token_buckets(usage_data)
        assert result["cache_read"] == 0
        assert result["cache_write"] == 0
        assert result["non_cached"] == 500

    def test_identity_always_holds(self):
        from lamb.completions.token_repartition import extract_token_buckets
        usage_data = {
            "prompt_tokens": 17629,
            "completion_tokens": 800,
            "prompt_tokens_details": {
                "cached_tokens": 16432,
                "cache_creation_input_tokens": 0,
            },
        }
        result = extract_token_buckets(usage_data)
        assert result["prompt_tokens"] == result["non_cached"] + result["cache_read"] + result["cache_write"]

    def test_clamp_cache_exceeds_prompt(self):
        from lamb.completions.token_repartition import extract_token_buckets
        usage_data = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "prompt_tokens_details": {
                "cached_tokens": 80,
                "cache_creation_input_tokens": 50,
            },
        }
        result = extract_token_buckets(usage_data)
        assert result["non_cached"] >= 0
        assert result["prompt_tokens"] == result["non_cached"] + result["cache_read"] + result["cache_write"]

    def test_dedup_nested_cache_creation(self):
        """When flat and nested have same value, count once (prefer flat)."""
        from lamb.completions.token_repartition import extract_token_buckets
        usage_data = {
            "prompt_tokens": 1000,
            "completion_tokens": 200,
            "prompt_tokens_details": {
                "cached_tokens": 0,
                "cache_creation_input_tokens": 500,
                "cache_creation": {"ephemeral_5m_input_tokens": 500},
            },
        }
        result = extract_token_buckets(usage_data)
        assert result["cache_write"] == 500  # not 1000


class TestCostFormula:
    def test_auto_cache_cost(self):
        from lamb.completions.cost_formula import compute_cost_usd
        pricing = {
            "input_per_1m": 2.50,
            "cache_read_per_1m": 1.25,
            "cache_write_per_1m": None,
            "output_per_1m": 10.0,
            "requires_explicit_cache": False,
        }
        buckets = {"non_cached": 200, "cache_read": 800, "cache_write": 0, "completion_tokens": 500}
        cost = compute_cost_usd(pricing, buckets)
        expected = (200 * 2.50 / 1e6) + (800 * 1.25 / 1e6) + (500 * 10.0 / 1e6)
        assert abs(cost - expected) < 1e-9

    def test_explicit_cache_cost(self):
        from lamb.completions.cost_formula import compute_cost_usd
        pricing = {
            "input_per_1m": 0.80,
            "cache_read_per_1m": 0.16,
            "cache_write_per_1m": 1.00,
            "output_per_1m": 2.00,
            "requires_explicit_cache": True,
        }
        buckets = {"non_cached": 958, "cache_read": 0, "cache_write": 18198, "completion_tokens": 957}
        cost = compute_cost_usd(pricing, buckets)
        expected = (958 * 0.80 / 1e6) + (0 * 0.16 / 1e6) + (18198 * 1.00 / 1e6) + (957 * 2.00 / 1e6)
        assert abs(cost - expected) < 1e-9

    def test_no_pricing_returns_zero(self):
        from lamb.completions.cost_formula import compute_cost_usd
        cost = compute_cost_usd(None, {"non_cached": 100, "cache_read": 0, "cache_write": 0, "completion_tokens": 50})
        assert cost == 0.0

    def test_cache_write_fallback_to_input_rate(self):
        from lamb.completions.cost_formula import compute_cost_usd
        pricing = {
            "input_per_1m": 0.80,
            "cache_read_per_1m": 0.16,
            "cache_write_per_1m": None,
            "output_per_1m": 2.00,
            "requires_explicit_cache": True,
        }
        buckets = {"non_cached": 100, "cache_read": 0, "cache_write": 500, "completion_tokens": 200}
        cost = compute_cost_usd(pricing, buckets)
        expected = (100 * 0.80 / 1e6) + (500 * 0.80 / 1e6) + (200 * 2.00 / 1e6)
        assert abs(cost - expected) < 1e-9

    def test_cache_read_fallback_to_input_rate(self):
        from lamb.completions.cost_formula import compute_cost_usd
        pricing = {
            "input_per_1m": 2.50,
            "cache_read_per_1m": None,
            "cache_write_per_1m": None,
            "output_per_1m": 10.0,
            "requires_explicit_cache": False,
        }
        buckets = {"non_cached": 200, "cache_read": 800, "cache_write": 0, "completion_tokens": 500}
        cost = compute_cost_usd(pricing, buckets)
        expected = (200 * 2.50 / 1e6) + (800 * 2.50 / 1e6) + (500 * 10.0 / 1e6)
        assert abs(cost - expected) < 1e-9


class TestLogTokenUsageImmutable:
    def test_cost_usd_stored_in_usage_logs(self, fresh_db):
        dm, _ = fresh_db
        conn = dm.get_connection()
        conn.execute("INSERT INTO organizations (id, name, slug, status, config, created_at, updated_at) VALUES (1, 'TestOrg', 'test-org', 'active', '{}', 1700000000, 1700000000)")
        conn.execute(
            "INSERT INTO assistants (id, name, owner, organization_id, api_callback, created_at, updated_at) VALUES (1, 'Bot', 'a@b.com', 1, '{}', 1700000000, 1700000000)"
        )
        conn.commit()
        conn.close()

        usage_data = {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500,
            "prompt_tokens_details": {"cached_tokens": 800},
        }
        dm.log_token_usage(assistant_id=1, org_id=1, model_name="gpt-4o", provider="openai", usage_data=usage_data)

        conn = dm.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT cost_usd FROM usage_logs WHERE assistant_id = 1")
        row = cursor.fetchone()
        conn.close()
        assert row is not None
        assert row[0] is not None
        assert row[0] > 0

    def test_cost_immutable_after_pricing_change(self, fresh_db):
        dm, _ = fresh_db
        conn = dm.get_connection()
        conn.execute("INSERT INTO organizations (id, name, slug, status, config, created_at, updated_at) VALUES (1, 'TestOrg', 'test-org', 'active', '{}', 1700000000, 1700000000)")
        conn.execute(
            "INSERT INTO assistants (id, name, owner, organization_id, api_callback, created_at, updated_at) VALUES (1, 'Bot', 'a@b.com', 1, '{}', 1700000000, 1700000000)"
        )
        conn.commit()
        conn.close()

        usage_data = {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500,
            "prompt_tokens_details": {"cached_tokens": 800},
        }
        dm.log_token_usage(assistant_id=1, org_id=1, model_name="gpt-4o", provider="openai", usage_data=usage_data)

        conn = dm.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT cost_usd_total FROM assistant_usage_totals WHERE assistant_id = 1")
        total_v1 = cursor.fetchone()[0]
        conn.close()

        conn = dm.get_connection()
        conn.execute("UPDATE model_pricing SET input_per_1m = 99.0, output_per_1m = 99.0 WHERE provider = 'openai' AND model_name = 'gpt-4o'")
        conn.commit()
        conn.close()

        conn = dm.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT cost_usd_total FROM assistant_usage_totals WHERE assistant_id = 1")
        total_after_price_change = cursor.fetchone()[0]
        conn.close()

        assert abs(total_v1 - total_after_price_change) < 1e-9

    def test_three_bucket_totals_stored(self, fresh_db):
        dm, _ = fresh_db
        conn = dm.get_connection()
        conn.execute("INSERT INTO organizations (id, name, slug, status, config, created_at, updated_at) VALUES (1, 'TestOrg', 'test-org', 'active', '{}', 1700000000, 1700000000)")
        conn.execute(
            "INSERT INTO assistants (id, name, owner, organization_id, api_callback, created_at, updated_at) VALUES (1, 'Bot', 'a@b.com', 1, '{}', 1700000000, 1700000000)"
        )
        conn.commit()
        conn.close()

        usage_data = {
            "prompt_tokens": 19156,
            "completion_tokens": 957,
            "total_tokens": 20113,
            "prompt_tokens_details": {
                "cached_tokens": 0,
                "cache_creation_input_tokens": 18198,
            },
        }
        dm.log_token_usage(assistant_id=1, org_id=1, model_name="qwen3.6-plus", provider="openai", usage_data=usage_data)

        conn = dm.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT cache_read_tokens_total, cache_write_tokens_total, non_cached_prompt_tokens_total, prompt_tokens_total "
            "FROM assistant_usage_totals WHERE assistant_id = 1"
        )
        row = cursor.fetchone()
        conn.close()
        assert row[0] == 0       # cache_read
        assert row[1] == 18198   # cache_write
        assert row[2] == 958     # non_cached
        assert row[3] == 19156   # prompt total


class TestGetAssistantCostUsd:
    def test_returns_frozen_total_not_recalculated(self, fresh_db):
        dm, _ = fresh_db
        conn = dm.get_connection()
        conn.execute("INSERT INTO organizations (id, name, slug, status, config, created_at, updated_at) VALUES (1, 'TestOrg', 'test-org', 'active', '{}', 1700000000, 1700000000)")
        conn.execute(
            "INSERT INTO assistants (id, name, owner, organization_id, api_callback, created_at, updated_at) VALUES (1, 'Bot', 'a@b.com', 1, '{}', 1700000000, 1700000000)"
        )
        conn.commit()
        conn.close()

        usage_data = {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500,
            "prompt_tokens_details": {"cached_tokens": 800},
        }
        dm.log_token_usage(assistant_id=1, org_id=1, model_name="gpt-4o", provider="openai", usage_data=usage_data)

        cost_before = dm.get_assistant_cost_usd(1)

        conn = dm.get_connection()
        conn.execute("UPDATE model_pricing SET input_per_1m = 99.0, output_per_1m = 99.0 WHERE provider = 'openai' AND model_name = 'gpt-4o'")
        conn.commit()
        conn.close()

        cost_after = dm.get_assistant_cost_usd(1)
        assert abs(cost_before - cost_after) < 1e-9, f"Cost changed from {cost_before} to {cost_after}"

    def test_returns_zero_for_unknown_assistant(self, fresh_db):
        dm, _ = fresh_db
        assert dm.get_assistant_cost_usd(99999) == 0.0


class TestMigration19Backfill:
    def test_backfill_legacy_rows(self, fresh_db):
        """Legacy usage_logs rows inserted without cost_usd get backfilled by Migration 19."""
        import json
        dm, _ = fresh_db
        conn = dm.get_connection()
        conn.execute("INSERT INTO organizations (id, name, slug, status, config, created_at, updated_at) VALUES (1, 'TestOrg', 'test-org', 'active', '{}', 1700000000, 1700000000)")
        conn.execute(
            "INSERT INTO assistants (id, name, owner, organization_id, api_callback, created_at, updated_at) VALUES (1, 'Bot', 'a@b.com', 1, '{}', 1700000000, 1700000000)"
        )
        usage_data = {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500, "prompt_tokens_details": {"cached_tokens": 800}}
        conn.execute(
            "INSERT INTO usage_logs (organization_id, assistant_id, usage_data, model_name, provider, cost_usd, created_at) VALUES (1, 1, ?, 'gpt-4o', 'openai', NULL, 1700000000)",
            (json.dumps(usage_data),)
        )
        conn.commit()
        conn.close()

        # Re-run migrations to trigger backfill
        dm.run_migrations()

        conn = dm.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT cost_usd FROM usage_logs WHERE assistant_id = 1 AND cost_usd IS NOT NULL")
        rows = cursor.fetchall()
        conn.close()
        assert len(rows) >= 1
        assert rows[0][0] > 0


class TestUsageByModelBreakdown:
    def test_breakdown_returns_three_buckets(self, fresh_db):
        dm, _ = fresh_db
        conn = dm.get_connection()
        conn.execute("INSERT INTO organizations (id, name, slug, status, config, created_at, updated_at) VALUES (1, 'TestOrg', 'test-org', 'active', '{}', 1700000000, 1700000000)")
        conn.execute(
            "INSERT INTO assistants (id, name, owner, organization_id, api_callback, created_at, updated_at) VALUES (1, 'Bot', 'a@b.com', 1, '{}', 1700000000, 1700000000)"
        )
        conn.commit()
        conn.close()

        usage_data = {
            "prompt_tokens": 19156,
            "completion_tokens": 957,
            "total_tokens": 20113,
            "prompt_tokens_details": {
                "cached_tokens": 0,
                "cache_creation_input_tokens": 18198,
            },
        }
        dm.log_token_usage(assistant_id=1, org_id=1, model_name="qwen3.6-plus", provider="openai", usage_data=usage_data)

        rows = dm.get_assistant_usage_by_model(1)
        assert len(rows) == 1
        r = rows[0]
        assert r["cache_read_tokens"] == 0
        assert r["cache_write_tokens"] == 18198
        assert r["non_cached_prompt_tokens"] == 958
        assert r["prompt_tokens"] == 19156
        assert "cost_usd" in r
        assert r["cost_usd"] > 0

    def test_breakdown_cost_uses_stored_values(self, fresh_db):
        """Breakdown cost must be SUM(usage_logs.cost_usd), not recalculated."""
        dm, _ = fresh_db
        conn = dm.get_connection()
        conn.execute("INSERT INTO organizations (id, name, slug, status, config, created_at, updated_at) VALUES (1, 'TestOrg', 'test-org', 'active', '{}', 1700000000, 1700000000)")
        conn.execute(
            "INSERT INTO assistants (id, name, owner, organization_id, api_callback, created_at, updated_at) VALUES (1, 'Bot', 'a@b.com', 1, '{}', 1700000000, 1700000000)"
        )
        conn.commit()
        conn.close()

        usage_data = {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500,
            "prompt_tokens_details": {"cached_tokens": 800},
        }
        dm.log_token_usage(assistant_id=1, org_id=1, model_name="gpt-4o", provider="openai", usage_data=usage_data)

        rows_before = dm.get_assistant_usage_by_model(1)
        cost_before = rows_before[0]["cost_usd"]

        conn = dm.get_connection()
        conn.execute("UPDATE model_pricing SET input_per_1m = 99.0, output_per_1m = 99.0 WHERE provider = 'openai' AND model_name = 'gpt-4o'")
        conn.commit()
        conn.close()

        rows_after = dm.get_assistant_usage_by_model(1)
        cost_after = rows_after[0]["cost_usd"]

        assert abs(cost_before - cost_after) < 1e-9
