"""Startup policy acceptance with real isolated LAMB and OWI SQLite stores."""
import copy
import json
import os
import sqlite3

import pytest

from lamb.startup_configuration import GROUPS, StartupConfiguration


def saved_config():
    return {
        "setups": {"default": {
            "providers": {"openai": {"api_key": "saved-key", "base_url": "http://saved",
                                      "models": ["saved-model"], "default_model": "saved-model",
                                      "enabled": False, "extra": 42},
                          "custom": {"opaque": "preserve"}},
            "global_default_model": {"provider": "openai", "model": "saved-model"},
            "small_fast_model": {"provider": "openai", "model": "saved-model"},
            "knowledge_base": {"server_url": "http://legacy", "api_token": "legacy-token"},
            "library": {"server_url": "http://saved-lib", "api_token": "saved-token",
                        "allowed_import_plugins": ["saved"]}},
            "other": {"providers": {"openai": {"api_key": "other-key"}}}},
        "kb_server": {"url": "http://saved-kb", "api_key": "saved-token",
                      "embedding_model": "saved-embedding", "collection_defaults": {"size": 9}},
        "features": {"signup_enabled": False, "signup_key": "saved-signup", "api_access": True,
                     "mcp_enabled": False, "lti_publishing": False, "rag_enabled": False,
                     "custom": True},
        "assistant_defaults": {"system_prompt": "Saved instructions", "rag_placeholders": []},
        "lti_access": {"locked_instances": ["saved-lms"]},
    }


def changed_env():
    return {"OPENAI_API_KEY": "changed-key", "OPENAI_BASE_URL": "http://changed",
            "OPENAI_MODELS": "new-a, new-b", "OPENAI_MODEL": "new-a", "OPENAI_ENABLED": "true",
            "GLOBAL_DEFAULT_MODEL_PROVIDER": "openai", "GLOBAL_DEFAULT_MODEL_NAME": "new-a",
            "LAMB_KB_SERVER": "http://changed-kb", "LAMB_KB_SERVER_TOKEN": "changed-kb-token",
            "LAMB_LIBRARY_SERVER": "http://changed-lib", "LAMB_LIBRARY_TOKEN": "changed-lib-token",
            "SIGNUP_ENABLED": "true", "SIGNUP_SECRET_KEY": "new-signup", "API_ACCESS_ENABLED": "false",
            "MCP_ENABLED": "true", "LTI_PUBLISHING_ENABLED": "true", "RAG_ENABLED": "true",
            "LAMB_ASSISTANT_DEFAULT_SYSTEM_PROMPT": "New instructions"}


def test_default_policy_preserves_every_saved_value():
    saved = saved_config()
    assert StartupConfiguration(changed_env()).organization_config(saved, {}) == saved


@pytest.mark.parametrize("group", GROUPS)
def test_each_group_changes_only_its_own_fields(group):
    saved = saved_config()
    env = changed_env() | {"LAMB_STARTUP_OVERRIDE_" + group: "true"}
    after = StartupConfiguration(env).organization_config(saved, {})
    expected = copy.deepcopy(saved)
    setup = expected["setups"]["default"]
    if group == "PROVIDER_CONNECTIONS":
        setup["providers"]["openai"].update(api_key="changed-key", base_url="http://changed")
    elif group == "MODELS":
        setup["providers"]["openai"].update(models=["new-a", "new-b"], default_model="new-a", enabled=True)
        setup["global_default_model"] = {"provider": "openai", "model": "new-a"}
    elif group == "KNOWLEDGE_CONNECTIONS":
        expected["kb_server"].update(url="http://changed-kb", api_key="changed-kb-token")
        setup["knowledge_base"].update(server_url="http://changed-kb", api_token="changed-kb-token")
        setup["library"].update(server_url="http://changed-lib", api_token="changed-lib-token")
    elif group == "FEATURES":
        expected["features"].update(signup_enabled=True, signup_key="new-signup", api_access=False,
                                    mcp_enabled=True, lti_publishing=True, rag_enabled=True)
    elif group == "ASSISTANT_DEFAULTS":
        expected["assistant_defaults"]["system_prompt"] = "New instructions"
    assert after == expected
    assert saved == saved_config(), "policy must not mutate its input"


def test_missing_values_are_seeded_and_explicit_clears_survive():
    env = {"OPENAI_API_KEY": "", "OPENAI_MODELS": "", "OPENAI_ENABLED": "false",
           "LAMB_ASSISTANT_DEFAULT_RAG_PLACEHOLDERS": "[]"}
    first = StartupConfiguration(env).organization_config({}, {"rag_placeholders": ["packaged"]})
    after = StartupConfiguration(changed_env()).organization_config(first, {})
    assert after["setups"]["default"]["providers"]["openai"]["api_key"] == ""
    assert after["setups"]["default"]["providers"]["openai"]["models"] == []
    assert after["setups"]["default"]["providers"]["openai"]["enabled"] is False
    assert after["assistant_defaults"]["rag_placeholders"] == []


def test_explicit_clear_and_absent_values_with_override():
    saved = saved_config()
    after = StartupConfiguration({"LAMB_STARTUP_OVERRIDE_PROVIDER_CONNECTIONS": "true",
                                  "OPENAI_API_KEY": ""}).organization_config(saved, {})
    assert after["setups"]["default"]["providers"]["openai"]["api_key"] == ""
    assert after["setups"]["default"]["providers"]["openai"]["base_url"] == "http://saved"


@pytest.mark.parametrize("env", [
    {"LAMB_STARTUP_OVERRIDE_ADMIN": "yes"},
    {"LAMB_STARTUP_OVERRIDE_MODELS": "true", "OPENAI_ENABLED": "secret-invalid-value"},
    {"GLOBAL_DEFAULT_MODEL_PROVIDER": "openai"},
    {"SMALL_FAST_MODEL_PROVIDER": "openai", "SMALL_FAST_MODEL_NAME": ""},
    {"LAMB_ASSISTANT_DEFAULT_RAG_PLACEHOLDERS": "{}"},
])
def test_invalid_inputs_rejected_without_values_in_errors(env):
    with pytest.raises(ValueError) as error:
        StartupConfiguration(env).organization_config({}, {})
    assert "secret-invalid-value" not in str(error.value)


def test_lti_credentials_preserve_seed_override_and_require_pair():
    saved = {"oauth_consumer_key": "saved", "oauth_consumer_secret": "saved-secret"}
    assert StartupConfiguration({"LTI_SECRET": "legacy"}).lti_credentials(None) == ("lamb", "legacy")
    assert StartupConfiguration({"LTI_GLOBAL_SECRET": "new"}).lti_credentials(saved) is None
    env = {"LAMB_STARTUP_OVERRIDE_LTI_CREDENTIALS": "true", "LTI_GLOBAL_SECRET": "new"}
    with pytest.raises(ValueError):
        StartupConfiguration(env).lti_credentials(saved)
    env["LTI_GLOBAL_CONSUMER_KEY"] = "new-key"
    assert StartupConfiguration(env).lti_credentials(saved) == ("new-key", "new")


@pytest.fixture
def installation(tmp_path, monkeypatch):
    import config
    from lamb.database_manager import LambDatabaseManager
    for name in list(os.environ):
        if name.startswith("LAMB_STARTUP_") or name.startswith("LAMB_ASSISTANT_DEFAULT_"):
            monkeypatch.delenv(name)
    for name in ("GLOBAL_DEFAULT_MODEL_PROVIDER", "GLOBAL_DEFAULT_MODEL_NAME",
                 "SMALL_FAST_MODEL_PROVIDER", "SMALL_FAST_MODEL_NAME"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(config, "LAMB_DB_PATH", str(tmp_path / "lamb"))
    monkeypatch.setattr(config, "OWI_ADMIN_EMAIL", "startup-admin@example.test")
    monkeypatch.setattr(config, "OWI_ADMIN_NAME", "Initial Administrator")
    monkeypatch.setattr(config, "OWI_ADMIN_PASSWORD", "initial-test-password")
    monkeypatch.setenv("OWI_PATH", str(tmp_path))
    with sqlite3.connect(tmp_path / "webui.db") as connection:
        connection.executescript('''
            CREATE TABLE user (id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL, profile_image_url TEXT NOT NULL, api_key TEXT,
                created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL, last_active_at INTEGER NOT NULL,
                settings TEXT, info TEXT, oauth_sub TEXT);
            CREATE TABLE auth (id TEXT PRIMARY KEY, email TEXT NOT NULL, password TEXT NOT NULL, active INTEGER NOT NULL);
        ''')
    def restart():
        LambDatabaseManager._system_org_initialized = False
        LambDatabaseManager._ready_databases.clear()
        return LambDatabaseManager()
    yield restart, tmp_path / "webui.db"
    LambDatabaseManager._system_org_initialized = False
    LambDatabaseManager._ready_databases.clear()


def test_real_restart_preserves_orgs_and_reapplies_only_enabled_group(installation, monkeypatch):
    restart, _ = installation
    db = restart()
    org = db.get_organization_by_slug("lamb")
    cfg = saved_config()
    db.update_organization_config(org["id"], cfg)
    other_id = db.create_organization("independent", "Independent", config=copy.deepcopy(cfg))
    other = db.get_organization_by_id(other_id)["config"]
    for key, value in changed_env().items():
        monkeypatch.setenv(key, value)
    db = restart()
    after = db.get_organization_by_slug("lamb")["config"]
    assert after["setups"] == cfg["setups"]
    monkeypatch.setenv("LAMB_STARTUP_OVERRIDE_PROVIDER_CONNECTIONS", "true")
    db = restart()
    after = db.get_organization_by_slug("lamb")["config"]
    assert after["setups"]["default"]["providers"]["openai"]["api_key"] == "changed-key"
    assert after["setups"]["default"]["providers"]["openai"]["models"] == ["saved-model"]
    monkeypatch.setenv("OPENAI_API_KEY", "next-key")
    assert restart().get_organization_by_slug("lamb")["config"]["setups"]["default"]["providers"]["openai"]["api_key"] == "next-key"
    monkeypatch.setenv("LAMB_STARTUP_OVERRIDE_PROVIDER_CONNECTIONS", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "ignored-key")
    db = restart()
    assert db.get_organization_by_slug("lamb")["config"]["setups"]["default"]["providers"]["openai"]["api_key"] == "next-key"
    assert db.get_organization_by_id(other_id)["config"] == other


@pytest.mark.parametrize("missing", [None, "lamb", "owi", "auth"])
def test_admin_recovery_real_password_verification_in_both_stores(installation, monkeypatch, missing):
    import config
    from lamb.auth import verify_password
    from lamb.owi_bridge.owi_users import OwiUserManager
    from lamb.services.creator_user_service import CreatorUserService
    restart, owi_path = installation
    db = restart()
    admin = db.get_creator_user_by_email(config.OWI_ADMIN_EMAIL)
    with db.get_connection() as c:
        c.execute(f"UPDATE {db.table_prefix}Creator_users SET enabled=0, role='user', user_name='Saved Name' WHERE id=?", (admin['id'],))
        if missing == "lamb":
            c.execute(f"DELETE FROM {db.table_prefix}Creator_users WHERE id=?", (admin['id'],))
    with sqlite3.connect(owi_path) as c:
        c.execute("UPDATE auth SET active=0")
        c.execute("UPDATE user SET role='user'")
        if missing in ("owi", "auth"):
            c.execute("DELETE FROM auth")
        if missing == "owi":
            c.execute("DELETE FROM user")
    monkeypatch.setattr(config, "OWI_ADMIN_PASSWORD", "recovered-test-password")
    monkeypatch.setenv("LAMB_STARTUP_OVERRIDE_ADMIN", "true")
    db = restart()
    recovered = db.get_creator_user_by_email(config.OWI_ADMIN_EMAIL)
    assert recovered['enabled'] and recovered['role'] == 'admin'
    assert verify_password("recovered-test-password", recovered['password_hash'])
    assert not verify_password("initial-test-password", recovered['password_hash'])
    if missing != "lamb":
        assert recovered['name'] == 'Saved Name'
    native = CreatorUserService()
    assert native.verify_user(config.OWI_ADMIN_EMAIL, "recovered-test-password")['role'] == 'admin'
    assert native.verify_user(config.OWI_ADMIN_EMAIL, "initial-test-password") is None
    mirror = OwiUserManager()
    assert mirror.verify_user(config.OWI_ADMIN_EMAIL, "recovered-test-password")['role'] == 'admin'
    assert mirror.verify_user(config.OWI_ADMIN_EMAIL, "initial-test-password") is None


def test_default_restart_preserves_existing_admin_and_new_target_keeps_old(installation, monkeypatch):
    import config
    from lamb.auth import verify_password
    restart, _ = installation
    db = restart()
    old = db.get_creator_user_by_email(config.OWI_ADMIN_EMAIL)
    with db.get_connection() as c:
        c.execute(f"UPDATE {db.table_prefix}Creator_users SET enabled=0, role='user' WHERE id=?", (old['id'],))
    monkeypatch.setattr(config, "OWI_ADMIN_PASSWORD", "changed-password")
    db = restart()
    after = db.get_creator_user_by_email(old['email'])
    assert not after['enabled'] and after['role'] == 'user'
    assert verify_password('initial-test-password', after['password_hash'])
    monkeypatch.setattr(config, "OWI_ADMIN_EMAIL", "new-recovery@example.test")
    monkeypatch.setenv("LAMB_STARTUP_OVERRIDE_ADMIN", "true")
    db = restart()
    assert db.get_creator_user_by_email(config.OWI_ADMIN_EMAIL)['role'] == 'admin'
    assert db.get_creator_user_by_email(old['email']) == after


def test_failed_recovery_rolls_back_both_passwords(installation, monkeypatch):
    import config
    restart, owi_path = installation
    db = restart()
    before = db.get_creator_user_by_email(config.OWI_ADMIN_EMAIL)
    with sqlite3.connect(owi_path) as c:
        old_hash = c.execute("SELECT password FROM auth").fetchone()[0]
        c.execute("CREATE TRIGGER refuse_recovery BEFORE UPDATE ON auth BEGIN SELECT RAISE(ABORT, 'test'); END")
    monkeypatch.setattr(config, "OWI_ADMIN_PASSWORD", "changed-password")
    monkeypatch.setenv("LAMB_STARTUP_OVERRIDE_ADMIN", "true")
    with pytest.raises(RuntimeError, match="rolled back"):
        restart()
    assert db.get_creator_user_by_email(config.OWI_ADMIN_EMAIL)['password_hash'] == before['password_hash']
    with sqlite3.connect(owi_path) as c:
        assert c.execute("SELECT password FROM auth").fetchone()[0] == old_hash


def test_resolver_prefers_current_kb_and_explicit_empty_values(monkeypatch):
    from lamb.completions.org_config_resolver import OrganizationConfigResolver
    resolver = OrganizationConfigResolver.__new__(OrganizationConfigResolver)
    resolver._org = {"is_system": True, "config": saved_config()}
    resolver._config_cache = {}
    resolver.setup_name = 'default'
    resolver.assistant_owner = 'owner@example.test'
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")
    cfg = resolver._org['config']
    cfg['kb_server'].update(url='', api_key='')
    cfg['setups']['default']['providers']['openai'] = {}
    cfg['setups']['default']['global_default_model'] = {'provider': '', 'model': ''}
    monkeypatch.setenv('GLOBAL_DEFAULT_MODEL_PROVIDER', 'openai')
    monkeypatch.setenv('GLOBAL_DEFAULT_MODEL_NAME', 'must-not-be-used')
    assert resolver.get_knowledge_base_config()['server_url'] == ''
    assert resolver.get_knowledge_base_config()['api_token'] == ''
    assert resolver.get_provider_config('openai') == {}
    assert resolver.get_global_default_model_config() == {'provider': '', 'model': ''}


@pytest.mark.asyncio
@pytest.mark.parametrize("connector", ["openai", "ollama"])
@pytest.mark.parametrize("owner", [None, "teacher@example.test"])
async def test_connector_never_uses_environment_after_saved_clear(monkeypatch, connector, owner):
    import importlib
    from types import SimpleNamespace
    module = importlib.import_module("lamb.completions.connectors." + connector)
    monkeypatch.setenv("OPENAI_API_KEY", "environment-must-not-be-used")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://environment-must-not-be-used")
    resolver = SimpleNamespace(organization={"name": "Synthetic"},
                               get_provider_config=lambda _: {"api_key": "", "base_url": "", "enabled": True})
    monkeypatch.setattr(module, "OrganizationConfigResolver", lambda _: resolver)
    with pytest.raises(ValueError, match="organization configuration"):
        await module.llm_connect([{"role": "user", "content": "test"}], assistant_owner=owner)


def test_knowledge_clients_reject_saved_clear_without_environment_fallback(monkeypatch):
    from types import SimpleNamespace
    from creator_interface.kb_server_manager import KBServerManager
    from creator_interface import library_manager_client as library
    from lamb.completions import org_config_resolver
    resolver = SimpleNamespace(get_knowledge_base_config=lambda: {"server_url": "", "api_token": ""},
                               get_library_config=lambda: {"server_url": "", "api_token": ""})
    monkeypatch.setattr(org_config_resolver, 'OrganizationConfigResolver', lambda _: resolver)
    monkeypatch.setattr(library, 'OrganizationConfigResolver', lambda _: resolver)
    monkeypatch.setattr(library, 'LAMB_LIBRARY_SERVER_ENABLE', 'ENABLE')
    with pytest.raises(ValueError, match="this organization"):
        KBServerManager()._get_kb_config_for_user({'email': 'teacher@example.test'})
    with pytest.raises(ValueError, match="this organization"):
        library.LibraryManagerClient()._get_library_config({'email': 'teacher@example.test'})


def test_recovery_preserves_existing_membership_and_name(installation, monkeypatch):
    import config
    restart, _ = installation
    db = restart()
    organization_id = db.create_organization("teaching", "Teaching")
    admin = db.get_creator_user_by_email(config.OWI_ADMIN_EMAIL)
    db.update_user_organization(admin['id'], organization_id)
    monkeypatch.setattr(config, 'OWI_ADMIN_NAME', 'Must not replace saved name')
    monkeypatch.setenv('LAMB_STARTUP_OVERRIDE_ADMIN', 'true')
    db = restart()
    recovered = db.get_creator_user_by_email(config.OWI_ADMIN_EMAIL)
    assert recovered['organization_id'] == organization_id
    assert recovered['name'] == 'Initial Administrator'
    assert db.get_user_organization_role(recovered['id'], organization_id) == 'admin'


def test_google_defaults_seed_once_without_replacing_model_selection():
    env = {'GOOGLE_API_KEY': 'synthetic'}
    defaults = {'google': {'models': ['image-a'], 'default_model': 'image-a'}}
    first = StartupConfiguration(env).organization_config({}, {}, defaults)
    assert first['setups']['default']['providers']['google']['models'] == ['image-a']
    changed = {'google': {'models': ['image-b'], 'default_model': 'image-b'}}
    assert StartupConfiguration(env).organization_config(first, {}, changed) == first


@pytest.mark.asyncio
async def test_signup_cannot_use_environment_key_after_saved_disable(monkeypatch):
    from types import SimpleNamespace
    from creator_interface import main
    monkeypatch.setattr(main, 'db_manager', SimpleNamespace(get_organization_by_signup_key=lambda _: None))
    monkeypatch.setattr(main, 'SIGNUP_ENABLED', True)
    monkeypatch.setattr(main, 'SIGNUP_SECRET_KEY', 'environment-key')
    result = await main.signup(None, email='nobody@example.test', name='Nobody',
                               password='synthetic-password', secret_key='environment-key')
    assert result['success'] is False


def test_google_model_discovery_and_metadata_use_saved_catalog(monkeypatch):
    from types import SimpleNamespace
    from lamb.completions.connectors import banana_img
    settings = {'models': ['saved-image-model'], 'default_model': 'saved-image-model', 'enabled': True}
    monkeypatch.setattr(banana_img, 'OrganizationConfigResolver', lambda _: SimpleNamespace(get_provider_config=lambda _: settings))
    assert banana_img.get_available_llms('teacher@example.test') == ['saved-image-model']
    assert [model['id'] for model in banana_img.get_available_llms_with_metadata('teacher@example.test')] == ['saved-image-model']
    settings['enabled'] = False
    assert banana_img.get_available_llms('teacher@example.test') == []
    assert banana_img.get_available_llms_with_metadata('teacher@example.test') == []



def test_required_model_defaults_do_not_enable_a_provider_without_credentials():
    env = {'OPENAI_BASE_URL': 'http://synthetic', 'OPENAI_MODEL': 'synthetic-model'}
    seeded = StartupConfiguration(env).organization_config({}, {})
    provider = seeded['setups']['default']['providers']['openai']
    assert provider['enabled'] is False
    # Once saved, a credential override does not implicitly change model policy.
    env.update(OPENAI_API_KEY='new-key', LAMB_STARTUP_OVERRIDE_PROVIDER_CONNECTIONS='true')
    after = StartupConfiguration(env).organization_config(seeded, {})
    assert after['setups']['default']['providers']['openai']['api_key'] == 'new-key'
    assert after['setups']['default']['providers']['openai']['enabled'] is False
