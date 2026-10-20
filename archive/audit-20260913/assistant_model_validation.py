"""Validation shared by Creator model writes; discovery supplies org-scoped IDs."""
import json


def validate_model_metadata(metadata, capabilities):
    try:
        value = json.loads(metadata) if isinstance(metadata, str) else metadata
    except (ValueError, TypeError):
        value = None
    if not isinstance(value, dict):
        return "Select a model enabled for the assistant owner's organization."
    connector, model = value.get("connector"), value.get("llm")
    available = capabilities.get("connectors", {}).get(connector, {}).get("available_llms", [])
    if not model or model not in available:
        return ("The selected connector/model is not available for the assistant owner's "
                "organization. Select an enabled model before saving.")
    return None
