"""Explicit, field-level startup configuration policy (issue #566).

No database or network access. Build and validate the complete configuration before
the caller saves it. Environment values never appear in validation errors.
"""
import copy
import json
import os


GROUPS = (
    "ADMIN", "PROVIDER_CONNECTIONS", "MODELS", "KNOWLEDGE_CONNECTIONS",
    "FEATURES", "ASSISTANT_DEFAULTS", "LTI_CREDENTIALS",
)


def boolean(value):
    value = value.strip().lower()
    if value not in ("true", "false"):
        raise ValueError("expected true or false")
    return value == "true"


def model_list(value):
    return [item.strip() for item in value.split(",") if item.strip()]


def placeholders(value):
    result = json.loads(value)
    if not isinstance(result, list) or not all(isinstance(item, str) for item in result):
        raise ValueError("expected a JSON array of strings")
    return result


def merge_missing(target, defaults):
    for key, value in defaults.items():
        if key not in target:
            target[key] = copy.deepcopy(value)
        elif isinstance(target[key], dict) and isinstance(value, dict):
            merge_missing(target[key], value)


class StartupConfiguration:
    def __init__(self, environ=None):
        self.env = os.environ if environ is None else environ
        self.overrides = {}
        for group in GROUPS:
            name = "LAMB_STARTUP_OVERRIDE_" + group
            try:
                self.overrides[group] = boolean(self.env.get(name, "false"))
            except ValueError:
                raise ValueError(f"{name}: expected true or false") from None

    def organization_config(self, saved, assistant_defaults, provider_defaults=None):
        result = copy.deepcopy(saved)
        setup = result.setdefault("setups", {}).setdefault("default", {})

        def put(group, target, key, names, parser=str):
            if key in target and not self.overrides[group]:
                return
            if isinstance(names, str):
                names = (names,)
            name = next((name for name in names if name in self.env), None)
            if name is None:
                return
            try:
                target[key] = parser(self.env[name])
            except (ValueError, TypeError):
                raise ValueError(f"{name}: invalid startup value") from None

        providers = setup.setdefault("providers", {})
        connections = {
            "openai": {"api_key": "OPENAI_API_KEY", "base_url": "OPENAI_BASE_URL"},
            "ollama": {"base_url": "OLLAMA_BASE_URL"},
            "google": {"api_key": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
                       "project_id": ("GOOGLE_CLOUD_PROJECT", "VERTEX_PROJECT_ID"),
                       "location": ("GOOGLE_CLOUD_LOCATION", "VERTEX_LOCATION")},
        }
        models = {
            "openai": ("OPENAI_ENABLED", "OPENAI_MODELS", "OPENAI_MODEL"),
            "ollama": ("OLLAMA_ENABLED", "OLLAMA_MODEL", "OLLAMA_DEFAULT_MODEL"),
            "google": ("VERTEX_ENABLED", "GEMINI_MODELS", "GEMINI_DEFAULT_MODEL"),
            "llm": ("LLM_ENABLED", "LLM_MODELS", "LLM_DEFAULT_MODEL"),
        }
        for provider in dict.fromkeys([*connections, *models]):
            values = copy.deepcopy(providers.get(provider, {}))
            for field, names in connections.get(provider, {}).items():
                put("PROVIDER_CONNECTIONS", values, field, names)
            for field, name, parser in zip(
                    ("enabled", "models", "default_model"), models[provider],
                    (boolean, model_list, str)):
                put("MODELS", values, field, name, parser)
            if values or provider in providers:
                merge_missing(values, (provider_defaults or {}).get(provider, {}))
                # Required deployment defaults (e.g. OPENAI_MODEL) alone do not
                # make an unconfigured provider usable. Seed an enabled flag only
                # when absent; later key rotation never changes a saved disable.
                usable = {
                    "openai": bool(values.get("api_key") and values.get("base_url")),
                    "ollama": bool(values.get("base_url")),
                    "google": bool(values.get("api_key") or values.get("project_id")),
                    "llm": False,
                }
                values.setdefault("enabled", usable[provider])
                providers[provider] = values

        for field, prefix in (("global_default_model", "GLOBAL_DEFAULT_MODEL"),
                              ("small_fast_model", "SMALL_FAST_MODEL")):
            if field in setup and not self.overrides["MODELS"]:
                continue
            names = (prefix + "_PROVIDER", prefix + "_NAME")
            present = [name in self.env for name in names]
            if any(present):
                if not all(present):
                    raise ValueError(f"{prefix}: supply both provider and name")
                provider, model = (self.env[name].strip() for name in names)
                if bool(provider) != bool(model):
                    raise ValueError(f"{prefix}: supply both values or clear both")
                setup[field] = {**setup.get(field, {}), "provider": provider, "model": model}

        # The UI's current KB representation wins over legacy aliases, including
        # explicit empty values. Seed it from legacy data before consulting env.
        legacy = setup.get("knowledge_base", {})
        kb = result.setdefault("kb_server", {})
        for canonical, aliases in (("url", ("server_url", "url")),
                                   ("api_key", ("api_token", "api_key", "token"))):
            if canonical not in kb:
                source = next((key for key in aliases if key in kb), None)
                if source is not None:
                    kb[canonical] = kb[source]
                else:
                    source = next((key for key in aliases if key in legacy), None)
                    if source is not None:
                        kb[canonical] = legacy[source]
        put("KNOWLEDGE_CONNECTIONS", kb, "url", "LAMB_KB_SERVER")
        put("KNOWLEDGE_CONNECTIONS", kb, "api_key", "LAMB_KB_SERVER_TOKEN")
        # Keep legacy readers aligned only for explicitly overridden fields.
        for canonical, old, name in (("url", "server_url", "LAMB_KB_SERVER"),
                                     ("api_key", "api_token", "LAMB_KB_SERVER_TOKEN")):
            if self.overrides["KNOWLEDGE_CONNECTIONS"] and name in self.env:
                setup.setdefault("knowledge_base", {})[old] = kb[canonical]
        library = setup.setdefault("library", {})
        for key, alias in (("server_url", "url"), ("api_token", "token")):
            if key not in library and alias in library:
                library[key] = library[alias]
        put("KNOWLEDGE_CONNECTIONS", library, "server_url", "LAMB_LIBRARY_SERVER")
        put("KNOWLEDGE_CONNECTIONS", library, "api_token", "LAMB_LIBRARY_TOKEN")

        features = result.setdefault("features", {})
        for field, name in (("signup_enabled", "SIGNUP_ENABLED"),
                            ("api_access", "API_ACCESS_ENABLED"),
                            ("mcp_enabled", "MCP_ENABLED"),
                            ("lti_publishing", "LTI_PUBLISHING_ENABLED"),
                            ("rag_enabled", "RAG_ENABLED")):
            put("FEATURES", features, field, name, boolean)
        put("FEATURES", features, "signup_key", "SIGNUP_SECRET_KEY")
        merge_missing(features, {"signup_enabled": False, "api_access": False,
                                 "mcp_enabled": True, "lti_publishing": True,
                                 "rag_enabled": True})

        defaults = result.setdefault("assistant_defaults", {})
        for field in ("connector", "llm", "prompt_processor", "rag_processor",
                      "system_prompt", "prompt_template", "rag_placeholders",
                      "lamb_helper_assistant", "surfer_system_prompt", "surfer_prompt_template"):
            put("ASSISTANT_DEFAULTS", defaults, field,
                "LAMB_ASSISTANT_DEFAULT_" + field.upper(),
                placeholders if field == "rag_placeholders" else str)
        merge_missing(defaults, assistant_defaults)
        return result

    def lti_credentials(self, saved):
        if saved and not self.overrides["LTI_CREDENTIALS"]:
            return None
        key = self.env.get("LTI_GLOBAL_CONSUMER_KEY")
        secret = self.env.get("LTI_GLOBAL_SECRET")
        if self.overrides["LTI_CREDENTIALS"]:
            if key is None and secret is None:
                return None
            if not key or not secret:
                raise ValueError("LTI_CREDENTIALS: supply a nonempty global consumer key and secret together")
        else:
            # Capture the effective legacy defaults once. Later restarts preserve
            # the saved pair, even if the deployment environment changes.
            key = key or "lamb"
            secret = secret or self.env.get("LTI_SECRET")
        return (key, secret) if secret else None
