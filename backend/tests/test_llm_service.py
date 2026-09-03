"""Offline tests for the Groq client wrapper."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.core.config import settings
from app.services import llm_service


class FakeCompletions:
    def __init__(self, content: str = '{"answer":"ok","source_ids":["S1"]}') -> None:
        self.content = content
        self.calls: list[dict[str, object]] = []

    def create(self, **options):
        self.calls.append(options)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


class FakeGroqClient:
    def __init__(self, content: str = '{"answer":"ok","source_ids":["S1"]}') -> None:
        self.completions = FakeCompletions(content)
        self.chat = SimpleNamespace(completions=self.completions)


class LLMServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_api_key = settings.groq_api_key
        self.previous_model = settings.groq_model
        self.previous_temperature = settings.groq_temperature
        self.previous_tokens = settings.groq_max_completion_tokens
        self.previous_timeout = settings.groq_timeout_seconds
        self.previous_retries = settings.groq_max_retries
        settings.groq_api_key = "test-groq-key"
        settings.groq_model = "qwen/qwen3.6-27b"
        settings.groq_temperature = 0.2
        settings.groq_max_completion_tokens = 512
        settings.groq_timeout_seconds = 30
        settings.groq_max_retries = 2
        llm_service.clear_groq_client_cache()

    def tearDown(self) -> None:
        llm_service.clear_groq_client_cache()
        settings.groq_api_key = self.previous_api_key
        settings.groq_model = self.previous_model
        settings.groq_temperature = self.previous_temperature
        settings.groq_max_completion_tokens = self.previous_tokens
        settings.groq_timeout_seconds = self.previous_timeout
        settings.groq_max_retries = self.previous_retries

    def test_client_is_cached_and_completion_uses_grounded_settings(self) -> None:
        client = FakeGroqClient()
        messages = [
            {"role": "system", "content": "Return JSON."},
            {"role": "user", "content": "Question and context"},
        ]
        with patch.object(
            llm_service,
            "_create_groq_client",
            return_value=client,
        ) as create_client:
            first = llm_service.generate_json_completion(messages)
            llm_service.generate_json_completion(messages, max_completion_tokens=99)

        self.assertEqual(first, '{"answer":"ok","source_ids":["S1"]}')
        create_client.assert_called_once_with("test-groq-key", 30, 2)
        self.assertEqual(len(client.completions.calls), 2)
        options = client.completions.calls[0]
        self.assertEqual(options["model"], "qwen/qwen3.6-27b")
        self.assertEqual(options["messages"], messages)
        self.assertEqual(options["temperature"], 0.2)
        self.assertEqual(options["max_completion_tokens"], 512)
        self.assertEqual(options["reasoning_effort"], "none")
        self.assertEqual(options["response_format"], {"type": "json_object"})
        self.assertEqual(options["citation_options"], "disabled")
        self.assertEqual(client.completions.calls[1]["max_completion_tokens"], 99)

    def test_missing_key_and_invalid_settings_are_rejected(self) -> None:
        settings.groq_api_key = None
        with self.assertRaises(llm_service.LLMConfigurationError):
            llm_service.generate_json_completion(
                [{"role": "user", "content": "hello"}]
            )

        settings.groq_api_key = "test"
        settings.groq_temperature = 3
        with self.assertRaises(llm_service.LLMConfigurationError):
            llm_service.generate_json_completion(
                [{"role": "user", "content": "hello"}]
            )

    def test_provider_failure_and_empty_completion_are_wrapped(self) -> None:
        failing_client = FakeGroqClient()
        failing_client.completions.create = lambda **options: (_ for _ in ()).throw(
            OSError("network failed")
        )
        with patch.object(
            llm_service,
            "_create_groq_client",
            return_value=failing_client,
        ):
            with self.assertRaises(llm_service.LLMProviderError):
                llm_service.generate_json_completion(
                    [{"role": "user", "content": "hello"}]
                )

        llm_service.clear_groq_client_cache()
        with patch.object(
            llm_service,
            "_create_groq_client",
            return_value=FakeGroqClient("   "),
        ):
            with self.assertRaises(llm_service.LLMResponseError):
                llm_service.generate_json_completion(
                    [{"role": "user", "content": "hello"}]
                )


if __name__ == "__main__":
    unittest.main()
