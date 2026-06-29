from __future__ import annotations

import unittest

from app.ollama import OllamaSettings, build_messages, ollama_headers, prepare_chat


class OllamaTests(unittest.TestCase):
    def test_build_messages_from_single_message(self) -> None:
        model, messages = build_messages({"message": "Hi"}, "gemma3")

        self.assertEqual(model, "gemma3")
        self.assertEqual(messages[-1], {"role": "user", "content": "Hi"})
        self.assertEqual(messages[0]["role"], "system")

    def test_build_messages_from_history(self) -> None:
        model, messages = build_messages(
            {
                "model": "llama3.2",
                "messages": [
                    {"role": "user", "content": "hello"},
                    {"role": "assistant", "content": "hi"},
                    {"role": "tool", "content": "ignored"},
                ],
            },
            "gemma3",
        )

        self.assertEqual(model, "llama3.2")
        self.assertEqual(messages[-2], {"role": "user", "content": "hello"})
        self.assertEqual(messages[-1], {"role": "assistant", "content": "hi"})

    def test_build_messages_requires_user_message(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one user"):
            build_messages({"messages": [{"role": "assistant", "content": "hi"}]}, "gemma3")

    def test_build_messages_falls_back_to_message_when_history_empty(self) -> None:
        _model, messages = build_messages({"message": "Hi", "messages": []}, "gemma3")

        self.assertEqual(messages[-1], {"role": "user", "content": "Hi"})

    def test_prepare_chat_adds_tarot_rag_context(self) -> None:
        prepared = prepare_chat(
            {
                "feature": "tarot",
                "message": "Read my spread",
                "tarot": {
                    "readingType": "general",
                    "readingLabel": "General",
                    "spreadName": "Five-card path",
                    "question": "What should I understand?",
                    "selectedCards": [
                        {
                            "name": "The Fool",
                            "position": "Where you are now",
                            "orientation": "upright",
                            "keywords": ["beginning", "trust"],
                        }
                    ],
                    "retrieval": {
                        "vectorDb": "qdrant",
                        "candidateLimit": 12,
                        "rerankLimit": 4,
                        "reranker": "bge-reranker",
                    },
                },
            },
            "gemma3",
        )

        system_message = prepared.messages[0]["content"]
        self.assertIn("Tarot entertainment mode is active", system_message)
        self.assertIn("RAG technical contract", system_message)
        self.assertIn("The Fool", system_message)
        self.assertTrue(prepared.rag_metadata["ragUsed"])
        self.assertEqual(prepared.rag_metadata["retrieval"]["vectorDb"], "qdrant")

    def test_ollama_headers_include_configured_user_agent(self) -> None:
        headers = ollama_headers(
            OllamaSettings(
                base_url="https://ollama.glimpse-go.site",
                model="deepseek-v2:16b",
                timeout_seconds=60,
                user_agent="PostmanRuntime/7.44.0",
            )
        )

        self.assertEqual(headers["User-Agent"], "PostmanRuntime/7.44.0")
        self.assertEqual(headers["Content-Type"], "application/json")


if __name__ == "__main__":
    unittest.main()
