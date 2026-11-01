"""Metadata edits shared by command entry points; server validation is authoritative."""
import copy
import json
import uuid


def apply_prompt_filter_options(metadata, *, definition=None, random_filter=None):
    if definition is not None and random_filter is not None:
        raise ValueError("Use either --prompt-filters or --random-filter/--no-random-filter.")
    if definition is not None:
        try:
            value = json.loads(definition)
        except (ValueError, TypeError) as exc:
            raise ValueError("--prompt-filters requires a JSON object or null.") from exc
        if value is not None and (not isinstance(value, dict) or value.get("version") != 1 or not isinstance(value.get("items"), list)):
            raise ValueError("--prompt-filters requires {\"version\":1,\"items\":[...]} or null.")
        metadata["prompt_filters"] = value
    elif random_filter is not None:
        value = copy.deepcopy(metadata.get("prompt_filters") or {"version": 1, "items": []})
        if not isinstance(value, dict) or value.get("version") != 1 or not isinstance(value.get("items"), list):
            raise ValueError("Cannot edit this filter version. Use --prompt-filters with a supported definition.")
        matches = [item for item in value["items"] if item.get("type") == "random"]
        if not matches and random_filter:
            matches = [{"id": "random-" + uuid.uuid4().hex, "type": "random", "enabled": True,
                        "target": "system_prompt", "run_on": "conversation_start", "options": {}}]
            value["items"].extend(matches)
        for item in matches:
            item["enabled"] = random_filter
        metadata["prompt_filters"] = value
    return metadata
