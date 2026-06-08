import pytest
from lamb.completions.rag._query_rewriting_helper import get_last_user_message_text


class TestGetLastUserMessageText:
    def test_empty_messages_returns_empty_string(self):
        assert get_last_user_message_text([]) == ""

    def test_no_user_messages_returns_empty_string(self):
        messages = [
            {"role": "assistant", "content": "Hello"},
            {"role": "system", "content": "System prompt"},
        ]
        assert get_last_user_message_text(messages) == ""

    def test_extracts_last_user_message(self):
        messages = [
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First answer"},
            {"role": "user", "content": "Second question"},
        ]
        assert get_last_user_message_text(messages) == "Second question"

    def test_handles_multimodal_content(self):
        messages = [
            {"role": "user", "content": [
                {"type": "text", "text": "Describe this"},
                {"type": "image_url", "image_url": {"url": "http://example.com/img.png"}},
            ]},
        ]
        assert get_last_user_message_text(messages) == "Describe this"

    def test_handles_multimodal_with_multiple_text_parts(self):
        messages = [
            {"role": "user", "content": [
                {"type": "text", "text": "Part one"},
                {"type": "text", "text": "Part two"},
            ]},
        ]
        assert get_last_user_message_text(messages) == "Part one Part two"

    def test_handles_empty_content(self):
        messages = [{"role": "user", "content": ""}]
        assert get_last_user_message_text(messages) == ""

    def test_handles_none_messages(self):
        assert get_last_user_message_text(None) == ""
