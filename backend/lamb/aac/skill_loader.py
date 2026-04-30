"""Skill loader: parse skill .md files, resolve includes, run startup actions.

Skills are Markdown files with YAML frontmatter. They define:
- Context requirements (assistant_id, language, etc.)
- Startup actions (liteshell commands to gather context)
- LLM instructions (the markdown body)
- Optional includes (other skill files, flattened at load time)

The loader:
1. Parses frontmatter + body
2. Resolves includes (with loop prevention)
3. Substitutes context variables ({assistant_id}, {language}, etc.)
4. Appends the language directive
5. Returns the composed prompt text
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from lamb.logging_config import get_logger

logger = get_logger(__name__, component="AAC")

SKILLS_DIR = Path(__file__).parent / "skills"

# Language directive appended to every skill prompt
LANGUAGE_DIRECTIVE = """
## Language

All instructions above are in English for clarity. However, you MUST \
communicate with the user in: **{language}**

Use {language} for all your responses, explanations, questions, and \
suggestions. Only use English for technical identifiers (model names, \
command syntax, parameter names).
"""


def list_skills() -> list[dict]:
    """List available skills with their metadata."""
    skills = []
    for md_file in sorted(SKILLS_DIR.glob("*.md")):
        meta, _ = _parse_skill_file(md_file)
        if meta.get("id"):
            skills.append({
                "id": meta["id"],
                "name": meta.get("name", meta["id"]),
                "description": meta.get("description", ""),
                "required_context": meta.get("required_context", []),
                "optional_context": meta.get("optional_context", []),
            })
    return skills


def load_skill(
    skill_id: str,
    context: dict[str, Any],
) -> dict:
    """Load a skill by ID, resolve includes, substitute context.

    Args:
        skill_id: Skill identifier (matches frontmatter 'id' or filename stem).
        context: Context variables (assistant_id, language, etc.)

    Returns:
        {
            "prompt": str,              # Composed prompt text for the LLM
            "startup_actions": [str],   # Liteshell commands to run on startup
            "metadata": dict,           # Skill frontmatter
        }

    Raises:
        ValueError: If skill not found or required context missing.
    """
    skill_file = _find_skill_file(skill_id)
    if not skill_file:
        raise ValueError(f"Skill '{skill_id}' not found in {SKILLS_DIR}")

    meta, body = _parse_skill_file(skill_file)

    # Validate required context
    required = meta.get("required_context", [])
    missing = [k for k in required if k not in context]
    if missing:
        raise ValueError(f"Skill '{skill_id}' requires context: {missing}")

    # Default language
    if "language" not in context:
        context["language"] = "English"

    # Resolve includes (with loop prevention)
    full_body = _resolve_includes(body, meta.get("includes", []), loaded=set())

    # Substitute context variables in body and startup actions
    prompt = _substitute(full_body, context)
    startup_actions = [_substitute(cmd, context) for cmd in meta.get("startup_actions", [])]

    # Append language directive
    language = context.get("language", "English")
    prompt += "\n" + LANGUAGE_DIRECTIVE.replace("{language}", language)

    return {
        "prompt": prompt,
        "startup_actions": startup_actions,
        "metadata": meta,
    }


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _find_skill_file(skill_id: str) -> Path | None:
    """Find a skill file by ID (checks frontmatter) or filename stem."""
    # First try exact filename match
    direct = SKILLS_DIR / f"{skill_id}.md"
    if direct.exists():
        return direct

    # Search by frontmatter id
    for md_file in SKILLS_DIR.glob("*.md"):
        meta, _ = _parse_skill_file(md_file)
        if meta.get("id") == skill_id:
            return md_file

    return None


def _parse_skill_file(path: Path) -> tuple[dict, str]:
    """Parse a skill .md file into (frontmatter_dict, body_text)."""
    text = path.read_text(encoding="utf-8")

    # Extract YAML frontmatter between --- markers
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        return {}, text

    frontmatter_text = match.group(1)
    body = text[match.end():]

    # Parse YAML manually (simple subset, avoids PyYAML dependency)
    # Supports: key: value, key: [inline, list], key:\n  - list\n  - items
    meta: dict[str, Any] = {}
    lines = frontmatter_text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        if ":" not in stripped:
            i += 1
            continue

        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()

        # Inline list: [item1, item2]
        if value.startswith("[") and value.endswith("]"):
            items = value[1:-1].split(",")
            meta[key] = [item.strip().strip("'\"") for item in items if item.strip()]
        # Empty value — check for multi-line list on next lines
        elif value == "":
            list_items = []
            while i + 1 < len(lines):
                next_line = lines[i + 1]
                # Multi-line list item: starts with whitespace + -
                item_match = re.match(r"^\s+-\s+(.+)", next_line)
                if item_match:
                    list_items.append(item_match.group(1).strip().strip("'\""))
                    i += 1
                else:
                    break
            meta[key] = list_items if list_items else ""
        # Boolean
        elif value.lower() in ("true", "false"):
            meta[key] = value.lower() == "true"
        # Quoted string
        elif (value.startswith('"') and value.endswith('"')) or \
             (value.startswith("'") and value.endswith("'")):
            meta[key] = value[1:-1]
        else:
            meta[key] = value

        i += 1

    return meta, body


def _resolve_includes(body: str, includes: list[str], loaded: set[str]) -> str:
    """Resolve skill includes, preventing loops via the loaded set."""
    if not includes:
        return body

    parts = [body]
    for include_id in includes:
        if include_id in loaded:
            logger.warning(f"Skipping already-loaded skill include: {include_id}")
            continue

        loaded.add(include_id)
        include_file = _find_skill_file(include_id)
        if not include_file:
            logger.warning(f"Skill include '{include_id}' not found, skipping")
            continue

        inc_meta, inc_body = _parse_skill_file(include_file)
        # Recursively resolve nested includes
        inc_body = _resolve_includes(inc_body, inc_meta.get("includes", []), loaded)
        parts.append(f"\n\n--- Included skill: {include_id} ---\n{inc_body}")

    return "\n".join(parts)


def _substitute(text: str, context: dict[str, Any]) -> str:
    """Substitute {key} placeholders with context values.

    Only substitutes keys that exist in context. Unknown placeholders
    are left as-is (they might be LAMB template placeholders like {context}).
    """
    for key, value in context.items():
        text = text.replace(f"{{{key}}}", str(value))
    return text
