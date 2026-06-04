from __future__ import annotations

import unittest

from app.ollama import build_messages


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


if __name__ == "__main__":
    unittest.main()
