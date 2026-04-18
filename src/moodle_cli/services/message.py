"""Messaging service."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from moodle_cli.services.base import BaseService


class Message(BaseModel):
    id: int
    useridfrom: int = 0
    useridto: int = 0
    text: str = ""
    timecreated: int = 0


class Conversation(BaseModel):
    id: int
    name: str | None = None
    type: int = 1
    membercount: int = 0
    unreadcount: int = 0


class MessageService(BaseService):
    def send_message(self, to_user_id: int, text: str) -> int:
        data = self.call(
            "core_message_send_instant_messages",
            messages=[{"touserid": to_user_id, "text": text}],
        )
        return data[0]["msgid"]

    def get_messages(
        self,
        user_id: int,
        user_id_from: int = 0,
        message_type: str = "conversations",
    ) -> list[Message]:
        data = self.call(
            "core_message_get_messages",
            useridto=user_id,
            useridfrom=user_id_from,
            type=message_type,
            read=0,
            newestfirst=1,
        )
        return [Message(**m) for m in data.get("messages", [])]

    def get_conversations(self, user_id: int) -> list[Conversation]:
        data = self.call(
            "core_message_get_conversations",
            userid=user_id,
        )
        return [Conversation(**c) for c in data.get("conversations", [])]

    def get_conversation_messages(
        self, current_user_id: int, conversation_id: int
    ) -> list[dict[str, Any]]:
        data = self.call(
            "core_message_get_conversation_messages",
            currentuserid=current_user_id,
            convid=conversation_id,
        )
        return data.get("messages", [])
