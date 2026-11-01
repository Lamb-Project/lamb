"""Small, ordered string transforms. Conversation storage belongs to the caller."""
import re
import secrets
from fastapi import HTTPException

MAX_TEXT = 100_000
MAX_MARKERS = 100
MAX_BOUND = 10**12
RANDOM = re.compile(r"\{\{RANDOM:\s*(-?\d{1,13})\s*-\s*(-?\d{1,13})\s*\}\}")


def validate_random(text):
    if len(text) > MAX_TEXT:
        raise ValueError("Filtered system prompts are limited to 100000 characters.")
    matches = list(RANDOM.finditer(text))
    if len(matches) > MAX_MARKERS:
        raise ValueError("A system prompt may contain at most 100 random markers.")
    if "{{RANDOM" in RANDOM.sub("", text):
        raise ValueError("Invalid random marker. Use {{RANDOM:minimum-maximum}} with integer bounds.")
    if any(abs(int(bound)) > MAX_BOUND for m in matches for bound in m.groups()):
        raise ValueError("Random bounds must be between -1000000000000 and 1000000000000.")


def random_integers(text, options):
    # Replacement core adapted from the contributed random_augment processor.
    validate_random(text)
    def replace(match):
        low, high = sorted(map(int, match.groups()))
        return str(low + secrets.randbelow(high - low + 1))
    return RANDOM.sub(replace, text)


REGISTRY = {"random": random_integers}
COMPATIBLE_PROCESSORS = {"simple_augment"}


def validate_definition(metadata, system_prompt):
    definition = metadata.get("prompt_filters")
    if definition is None:
        return []
    if not isinstance(definition, dict) or type(definition.get("version")) is not int or definition["version"] != 1:
        raise ValueError("Unsupported prompt_filters version; expected version 1.")
    items = definition.get("items")
    if not isinstance(items, list) or len(items) > 20:
        raise ValueError("prompt_filters.items must be a list of at most 20 filters.")
    ids = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Each prompt filter must be an object.")
        identity = item.get("id")
        if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", identity) or identity in ids:
            raise ValueError("Prompt filters require unique, stable IDs (1 to 64 letters, digits, underscores or hyphens).")
        ids.add(identity)
        if type(item.get("enabled")) is not bool or not isinstance(item.get("type"), str):
            raise ValueError("Each prompt filter requires a type and a boolean enabled flag.")
        if not isinstance(item.get("options"), dict):
            raise ValueError("Prompt filter options must be an object.")
        if not item["enabled"]:
            continue
        if item["type"] not in REGISTRY:
            raise ValueError(f"Unknown enabled prompt filter: {item['type']}")
        if item.get("target") != "system_prompt" or item.get("run_on") != "conversation_start":
            raise ValueError("Supported prompt filters target system_prompt and run on conversation_start.")
        if item["options"]:
            raise ValueError("Random integers does not accept options.")
        if metadata.get("prompt_processor", "simple_augment") not in COMPATIBLE_PROCESSORS:
            raise ValueError("This prompt processor does not declare support for system prompt filters.")
        if item["type"] == "random":
            validate_random(system_prompt or "")
    return items


def run_filters(text, items):
    for item in items:
        if item["enabled"]:
            text = REGISTRY[item["type"]](text, item["options"])
    return text


def validated_items(metadata, text):
    try:
        return validate_definition(metadata, text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
