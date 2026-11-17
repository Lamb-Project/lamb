"""Completion-owned system prompts with durable and caller-held context adapters."""
import json
from dataclasses import dataclass
from fastapi import HTTPException
from .prompt_filters import run_filters, validated_items


@dataclass(frozen=True)
class Conversation:
    source: str
    id: str
    owner: str


def migrate(cursor, prefix="", *, owi=False):
    table = f"{prefix}prompt_filter_states"
    chats = "chat" if owi else f"{prefix}lamb_chats"
    cursor.execute(f"""CREATE TABLE IF NOT EXISTS {table} (
        chat_id TEXT NOT NULL, assistant_id INTEGER NOT NULL,
        owner TEXT NOT NULL, organization_id INTEGER NOT NULL,
        system_prompt TEXT NOT NULL, definition TEXT NOT NULL,
        PRIMARY KEY (chat_id, assistant_id))""")
    # OWI's connections need not enable foreign_keys. A trigger also handles bulk deletion.
    cursor.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_delete
        AFTER DELETE ON {chats} BEGIN
        DELETE FROM {table} WHERE chat_id = OLD.id; END""")
    if owi:
        cursor.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_fork
            AFTER INSERT ON chat WHEN json_valid(NEW.chat) BEGIN
            INSERT OR IGNORE INTO {table}
            SELECT NEW.id, assistant_id, CAST(NEW.user_id AS TEXT), organization_id, system_prompt, definition
            FROM {table} WHERE chat_id = json_extract(NEW.chat, '$.originalChatId')
                AND (owner = CAST(NEW.user_id AS TEXT) OR EXISTS (
                    SELECT 1 FROM chat original WHERE original.share_id = {table}.chat_id
                    AND {table}.owner = 'shared-' || original.id)); END""")
        cursor.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_share
            AFTER UPDATE OF share_id ON chat WHEN NEW.share_id IS NOT NULL BEGIN
            INSERT OR REPLACE INTO {table}
            SELECT NEW.share_id, assistant_id, 'shared-' || NEW.id, organization_id, system_prompt, definition
            FROM {table} WHERE chat_id = NEW.id AND owner = CAST(NEW.user_id AS TEXT)
                AND EXISTS (SELECT 1 FROM chat shared WHERE shared.id = NEW.share_id
                            AND shared.user_id = 'shared-' || NEW.id); END""")


def _chat(cursor, prefix, context, chat_id, assistant_id, *, ancestor=False):
    owi = context.source == "owi"
    table = "chat" if owi else f"{prefix}lamb_chats"
    columns = "user_id, chat" if owi else "user_id, chat, assistant_id"
    row = cursor.execute(f"SELECT {columns} FROM {table} WHERE id = ?", (chat_id,)).fetchone()
    shared = bool(owi and ancestor and row and cursor.execute(
        "SELECT 1 FROM chat WHERE share_id = ? AND ? = 'shared-' || id", (chat_id, row[0])).fetchone())
    if not row or (str(row[0]) != context.owner and not shared) or (not owi and row[2] != assistant_id):
        raise HTTPException(404, "Conversation not found for this user and assistant.")
    return json.loads(row[1])


def resolve(connection, prefix, context, assistant, config, request):
    """Check ownership and atomically read/initialize before any provider call."""
    table = f"{prefix}prompt_filter_states"
    org = assistant.organization_id
    if org is None:
        raise HTTPException(400, "The assistant must belong to an organization.")
    try:
        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.cursor()
        chat = _chat(cursor, prefix, context, context.id, assistant.id)
        row = cursor.execute(f"SELECT system_prompt, owner, organization_id, definition FROM {table} "
                             "WHERE chat_id = ? AND assistant_id = ?", (context.id, assistant.id)).fetchone()
        if row and row[1:3] != (context.owner, org):
            raise HTTPException(404, "Conversation scenario not found.")
        if row and row[3] != "null":
            result = row[0]
        else:
            history = chat.get("history", {}).get("messages", {})
            continuing = bool(row) or has_prior_answer(history.values()) or has_prior_answer(request.get("messages", []))
            # Native OWI forks carry an originalChatId. Only inherit a verified owner's scenario.
            parent = chat.get("originalChatId") if context.source == "owi" else None
            inherited = None
            seen = {context.id}
            while parent:
                if parent in seen or len(seen) > 32:
                    raise HTTPException(409, "Invalid conversation ancestry.")
                seen.add(parent)
                ancestor = _chat(cursor, prefix, context, parent, assistant.id, ancestor=True)
                continuing = continuing or has_prior_answer(ancestor.get("history", {}).get("messages", {}).values())
                inherited = cursor.execute(f"SELECT system_prompt, definition FROM {table} "
                    "WHERE chat_id = ? AND assistant_id = ? AND organization_id = ?",
                    (parent, assistant.id, org)).fetchone()
                if inherited:
                    break
                parent = ancestor.get("originalChatId")
            if inherited and inherited[1] != "null":
                result, definition = inherited
            else:
                items = validated_items(config, assistant.system_prompt)
                if (continuing or inherited) and any(item["enabled"] for item in items):
                    raise HTTPException(409, "This conversation has no retained system prompt. Start a new conversation.")
                # Pre-lifecycle chats retain their transcript and initialize the current
                # plain instructions once. Never invent a missing randomized scenario.
                result = run_filters(assistant.system_prompt or "", items)
                definition = json.dumps(config.get("prompt_filters") or {"version": 1, "items": []})
            if row:
                cursor.execute(f"UPDATE {table} SET system_prompt=?, definition=? WHERE chat_id=? AND assistant_id=?",
                               (result, definition, context.id, assistant.id))
            else:
                cursor.execute(f"INSERT INTO {table} VALUES (?, ?, ?, ?, ?, ?)",
                               (context.id, assistant.id, context.owner, org, result, definition))
        connection.commit()
        return assistant.model_copy(update={"system_prompt": result})
    except Exception:
        connection.rollback()
        raise


def has_prior_answer(messages):
    return any(m.get("role") == "assistant" and m.get("content") for m in messages)


@dataclass
class PromptContext:
    """Caller-owned ephemeral context. It grants no authentication or permissions."""
    system_prompt: str | None = None
    assistant_id: int | None = None
    organization_id: int | None = None

    @classmethod
    def from_payload(cls, payload):
        if (not isinstance(payload, dict) or set(payload) != {
                "version", "system_prompt", "assistant_id", "organization_id"}
                or type(payload["version"]) is not int or payload["version"] != 1
                or not isinstance(payload["system_prompt"], str)
                or len(payload["system_prompt"]) > 100_000
                or type(payload["assistant_id"]) is not int
                or type(payload["organization_id"]) is not int):
            raise HTTPException(400, "Invalid prompt_context. Use the context returned by this assistant.")
        return cls(payload["system_prompt"], payload["assistant_id"], payload["organization_id"])

    def export(self):
        return {"version": 1, "assistant_id": self.assistant_id,
                "organization_id": self.organization_id, "system_prompt": self.system_prompt}

    def prepare(self, assistant, config):
        if self.system_prompt is None:
            self.system_prompt = run_filters(assistant.system_prompt or "",
                                             validated_items(config, assistant.system_prompt))
            self.assistant_id, self.organization_id = assistant.id, assistant.organization_id
        elif (self.assistant_id, self.organization_id) != (assistant.id, assistant.organization_id):
            raise HTTPException(409, "Prompt context belongs to a different assistant or organization.")
        return assistant.model_copy(update={"system_prompt": self.system_prompt})


def prepare_assistant(assistant, config, request, context=None, *, prompt_context=None):
    # Input roles are not authority. Trusted API adapters pass authoritative base
    # instructions through PromptContext; plugins may add dynamic system content.
    if any(m.get("role") in {"system", "developer"} for m in request.get("messages", [])):
        raise HTTPException(400, "Pass authorized base instructions through prompt_context, not conversation messages.")
    if context is None:
        if prompt_context is None and has_prior_answer(request.get("messages", [])):
            raise HTTPException(409, "Continuation requires initialized prompt context or a saved conversation.")
        return (prompt_context or PromptContext()).prepare(assistant, config)
    if prompt_context is not None:
        raise HTTPException(400, "Do not combine prompt_context with a saved conversation.")
    if context.source == "owi":
        from lamb.owi_bridge.owi_database import OwiDatabaseManager
        manager = OwiDatabaseManager()
        prefix = "lamb_"
    elif context.source == "creator":
        from lamb.database_manager import LambDatabaseManager
        manager = LambDatabaseManager()
        prefix = manager.table_prefix
    else:
        raise HTTPException(400, "Unsupported conversation source.")
    connection = manager.get_connection()
    if connection is None:
        raise HTTPException(503, "Conversation state storage is unavailable.")
    try:
        if context.source == "owi":
            migrate(connection.cursor(), prefix, owi=True)
            connection.commit()
        return resolve(connection, prefix, context, assistant, config, request)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, "Could not persist the conversation system prompt. Please retry.") from exc
    finally:
        connection.close()
