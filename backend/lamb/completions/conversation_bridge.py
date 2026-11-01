"""Use OWI's standard pipeline hook to carry authenticated chat identity."""
import base64
import hashlib
import hmac
import json
import time
from fastapi import HTTPException
from .filter_state import Conversation


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
