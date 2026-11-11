"""Use OWI's standard pipeline hook to carry authenticated chat identity."""
import base64
import hashlib
import hmac
import json
import time
from fastapi import HTTPException
from .conversation_state import Conversation, PromptContext


def seal(user_id, chat_id, assistant_id, secret):
    payload = json.dumps([str(user_id), str(chat_id), int(assistant_id), int(time.time()) + 900], separators=(",", ":"))
    encoded = base64.urlsafe_b64encode(payload.encode()).decode()
    signature = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return encoded + "." + signature


def unseal(token, assistant_id, secret):
    try:
        if not isinstance(token, str) or len(token) > 2048:
            raise ValueError()
        encoded, signature = token.split(".")
        expected = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError()
        owner, chat_id, model_id, expires = json.loads(base64.urlsafe_b64decode(encoded))
        if model_id != int(assistant_id) or expires < time.time():
            raise ValueError()
        return Conversation("owi", chat_id, owner)
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(400, "Invalid or expired conversation reference. Retry from your chat.") from exc


def facade_conversation(identity, body, assistant_id, secret):
    if identity["kind"] == "creator":
        chat_id = body.get("conversation_id")
        if chat_id:
            if not isinstance(chat_id, str) or len(chat_id) > 128:
                raise HTTPException(400, "Invalid conversation_id.")
            return Conversation("creator", chat_id, str(identity["user_id"]))
    elif body.get("lamb_conversation"):
        return unseal(body["lamb_conversation"], assistant_id, secret)
    return None


def facade_prompt_context(body, assistant_id, conversation):
    """For already-authorized API callers only; never an end-user identity source.

    Creator-key callers are limited to their own published assistants by the
    facade. The service key authorizes its backend to supply context. Native OWI
    strips these options at its inlet and uses verified persistent state instead.
    """
    requested = body.get("return_prompt_context", False)
    if type(requested) is not bool:
        raise HTTPException(400, "return_prompt_context must be a boolean.")
    payload = body.get("prompt_context")
    if conversation is not None:
        if payload is not None or requested:
            raise HTTPException(400, "Do not combine prompt_context with a saved conversation.")
        return None, False, body["messages"]
    context = PromptContext.from_payload(payload) if payload is not None else None
    messages = body["messages"]
    # Preserve the standard full-context API pattern for authorized backends.
    # A leading system message is already initialized, so it is not filtered.
    if messages and messages[0].get("role") == "system":
        if context is not None:
            raise HTTPException(400, "Supply either prompt_context or a leading system message.")
        from .main import get_assistant_details
        selected = get_assistant_details(assistant_id)
        context = PromptContext.from_payload({"version": 1, "assistant_id": int(assistant_id),
            "organization_id": selected.organization_id, "system_prompt": messages[0].get("content")})
        messages = messages[1:]
    return context, requested, messages
