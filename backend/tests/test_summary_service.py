"""Tests for hierarchical document summarization."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.core.config import settings
from app.services import summary_service
from app.services.document_service import DocumentChunk
from app.services.llm_service import LLMResponseError


def make_chunks(count: int, text_length: int = 30) -> list[DocumentChunk]:
    return [
        DocumentChunk(
            chunk_id=f"document:{index}",
            text=f"Fact {index}: " + ("x" * text_length),
            metadata={"page_number": index + 1},
        )
        for index in range(count)
    ]


class SummaryServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_batch_characters = settings.summary_batch_characters
        self.previous_intermediate_tokens = settings.summary_intermediate_max_tokens
        self.previous_final_tokens = settings.summary_final_max_tokens
        self.previous_reduction_rounds = settings.summary_max_reduction_rounds
        settings.summary_batch_characters = 12_000
        settings.summary_intermediate_max_tokens = 111
        settings.summary_final_max_tokens = 222
        settings.summary_max_reduction_rounds = 8

    def tearDown(self) -> None:
        settings.summary_batch_characters = self.previous_batch_characters
        settings.summary_intermediate_max_tokens = self.previous_intermediate_tokens
        settings.summary_final_max_tokens = self.previous_final_tokens
        settings.summary_max_reduction_rounds = self.previous_reduction_rounds

    def test_single_batch_brief_summary_preserves_page_context(self) -> None:
        chunks = make_chunks(2)
        with patch.object(
            summary_service,
            "get_document",
            return_value=SimpleNamespace(status="ready"),
        ), patch.object(
            summary_service,
            "load_document_chunks",
            return_value=chunks,
        ), patch.object(
            summary_service,
            "generate_json_completion",
            return_value='{"summary":"A concise grounded summary."}',
        ) as generate:
            result = summary_service.summarize_document("document", "brief")

        self.assertEqual(result.detail, "brief")
        self.assertEqual(result.summary, "A concise grounded summary.")
        generate.assert_called_once()
        self.assertEqual(generate.call_args.kwargs["max_completion_tokens"], 222)
        user_prompt = generate.call_args.args[0][1]["content"]
        self.assertIn("PAGE 1 | CHUNK document:0", user_prompt)
        self.assertIn("PAGE 2 | CHUNK document:1", user_prompt)
        self.assertIn("one or two paragraphs", user_prompt)

    def test_long_document_uses_multiple_reduction_rounds(self) -> None:
        settings.summary_batch_characters = 120
        calls: list[tuple[str, int]] = []

        def fake_completion(messages, *, max_completion_tokens):
            user_prompt = messages[1]["content"]
            calls.append((user_prompt, max_completion_tokens))
            if "comprehensive" in user_prompt:
                return '{"summary":"# Detailed Summary\\nAll facts combined."}'
            return '{"summary":"Condensed facts."}'

        with patch.object(
            summary_service,
            "get_document",
            return_value=SimpleNamespace(status="ready"),
        ), patch.object(
            summary_service,
            "load_document_chunks",
            return_value=make_chunks(6, text_length=70),
        ), patch.object(
            summary_service,
            "generate_json_completion",
            side_effect=fake_completion,
        ):
            result = summary_service.summarize_document("document", "detailed")

        self.assertEqual(result.summary, "# Detailed Summary\nAll facts combined.")
        self.assertGreater(len(calls), 3)
        self.assertEqual(calls[-1][1], 222)
        self.assertTrue(all(token_limit == 111 for _, token_limit in calls[:-1]))
        self.assertTrue(any("PARTIAL SUMMARY" in prompt for prompt, _ in calls))

    def test_not_ready_and_malformed_outputs_are_rejected(self) -> None:
        with patch.object(
            summary_service,
            "get_document",
            return_value=SimpleNamespace(status="ingested"),
        ):
            with self.assertRaises(summary_service.SummaryDocumentNotReadyError):
                summary_service.summarize_document("document", "brief")

        with patch.object(
            summary_service,
            "get_document",
            return_value=SimpleNamespace(status="ready"),
        ), patch.object(
            summary_service,
            "load_document_chunks",
            return_value=make_chunks(1),
        ), patch.object(
            summary_service,
            "generate_json_completion",
            return_value='{"answer":"wrong schema"}',
        ):
            with self.assertRaises(LLMResponseError):
                summary_service.summarize_document("document", "brief")

    def test_oversized_unit_is_split_to_respect_batch_limit(self) -> None:
        batches = summary_service._group_units(["x" * 25], 10)

        self.assertEqual([len(batch) for batch in batches], [10, 10, 5])


if __name__ == "__main__":
    unittest.main()
