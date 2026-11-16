"""Regression checks for direct generators with reasoning and local models."""

import json
import unittest
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, Mock, patch

import httpx
from openai import OpenAI

from lamb.completions.generation_options import generation_options
from lamb.evaluaitor.ai_generator import AIRubricGenerator
from creator_interface.openai_connect import OpenAIConnector


RUBRIC = {
    "title": "Evidence", "description": "Evaluate use of evidence",
    "metadata": {"createdAt": "2026-11-16T00:00:00Z", "modifiedAt": "2026-11-16T00:00:00Z"},
    "scoringType": "points", "maxScore": 2,
    "criteria": [{"id": "c1", "name": "Evidence", "description": "Support claims",
                  "weight": 100, "levels": [
                      {"id": "l1", "score": 2, "label": "Supported", "description": "Relevant evidence"},
                      {"id": "l2", "score": 1, "label": "Unsupported", "description": "No evidence"}]}],
}


class GenerationOptionsTests(unittest.TestCase):
    def test_reasoning_variants_omit_sampling(self):
        for model in ("gpt-6-luna", "gpt-6.1-terra", "gpt-5", "gpt-5-mini",
                      "gpt-5.1", "gpt-5.6-sol", "o1", "o3-mini", "o4-mini-2025-04-16",
                      "ft:gpt-5-mini:org:custom:id"):
            with self.subTest(model=model):
                self.assertEqual(generation_options(model, max_tokens=4000, temperature=.7),
                                 {"max_completion_tokens": 4000})

    def test_legacy_openai_and_local_contracts(self):
        self.assertEqual(generation_options("gpt-4o", max_tokens=4000, temperature=.7),
                         {"max_completion_tokens": 4000, "temperature": .7})
        self.assertEqual(generation_options("qwen3.8", base_url="http://local:8001/v1",
                                            max_tokens=4000, temperature=.3),
                         {"max_tokens": 4000, "temperature": .3})
        self.assertEqual(generation_options("utility", base_url="http://local/v1", temperature=0),
                         {"temperature": 0})

    def test_rubric_recovery_sends_accepted_wire_parameters(self):
        # Exercise the real SDK serialization, parser, strict retry and validator.
        for model, base, field, temp in (
            ("gpt-6-luna", "https://api.openai.com/v1", "max_completion_tokens", None),
            ("gpt-6.1-terra", "https://api.openai.com/v1", "max_completion_tokens", None),
            ("gpt-4o", "https://api.openai.com/v1", "max_completion_tokens", .7),
            ("qwen3.8", "http://local:8001/v1", "max_tokens", .7),
        ):
            with self.subTest(model=model):
                requests = []

                def respond(request):
                    body = json.loads(request.content)
                    requests.append(body)
                    self.assertEqual(body["model"], model)
                    self.assertEqual(body[field], 4000)
                    self.assertNotIn("max_tokens" if field == "max_completion_tokens" else "max_completion_tokens", body)
                    if temp is None:
                        self.assertNotIn("temperature", body)
                    else:
                        self.assertEqual(body["temperature"], .7 if len(requests) == 1 else .3)
                    content = "invalid JSON" if len(requests) == 1 else json.dumps({"rubric": RUBRIC})
                    return httpx.Response(200, json={"id": "test", "object": "chat.completion",
                        "created": 0, "model": model, "choices": [{"index": 0, "finish_reason": "stop",
                        "message": {"role": "assistant", "content": content}}]})

                with OpenAI(api_key="test", base_url=base, max_retries=0,
                            http_client=httpx.Client(transport=httpx.MockTransport(respond))) as client:
                    generator = AIRubricGenerator.__new__(AIRubricGenerator)
                    generator.client, generator.base_url, generator.default_model = client, base, model
                    result = generator.generate_rubric("Assess evidence in an essay", "en")
                self.assertTrue(result["success"], result)
                self.assertIn("Evidence", result["markdown"])
                self.assertEqual(len(requests), 2)


class DescriptionOptionsTests(unittest.IsolatedAsyncioTestCase):
    async def test_description_uses_reasoning_options(self):
        connector = OpenAIConnector.__new__(OpenAIConnector)
        connector.model = "gpt-6-luna"
        create = AsyncMock(return_value=N(choices=[N(message=N(content="A writing tutor."))]))
        connector.client = N(base_url="https://api.openai.com/v1", chat=N(completions=N(create=create)))
        self.assertEqual(await connector.generate_assistant_description({"name": "Tutor"}), "A writing tutor.")
        body = create.call_args.kwargs
        self.assertNotIn("max_tokens", body)
        self.assertNotIn("temperature", body)
        self.assertEqual(body["max_completion_tokens"], 4000)

    async def test_translation_keeps_selected_reasoning_model(self):
        from lamb.aac.translation import translate
        settings = {"utility_provider": "openai", "utility_model": "gpt-6.1-terra"}
        resolver = N(organization={"config": {}}, get_provider_config=Mock(return_value={"api_key": "test"}))
        client = AsyncMock()
        client.chat.completions.create.return_value = N(choices=[N(message=N(content="evidence"))])
        knowledge = {"state": {}}
        with patch("lamb.aac.translation.translation_request", return_value=("evidencia", "English", {})), \
             patch("lamb.aac.translation.OrganizationConfigResolver", return_value=resolver), \
             patch("lamb.aac.translation.validate_settings", return_value=settings), \
             patch("lamb.aac.translation.AsyncOpenAI") as factory:
            factory.return_value.__aenter__.return_value = client
            result = await translate(knowledge, "synthetic@example.test", "evidencia", {})
        self.assertEqual(result["translation"], "evidence")
        self.assertEqual(client.chat.completions.create.call_args.kwargs["model"], "gpt-6.1-terra")
        self.assertNotIn("temperature", client.chat.completions.create.call_args.kwargs)
