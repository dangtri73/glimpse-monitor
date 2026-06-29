from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from collections.abc import Iterator
from typing import Any

from .tarot_rag import build_tarot_prompt_context

DEFAULT_SYSTEM_PROMPT = """You are Glimpse, a concise system monitoring assistant.
Answer the user's question directly. If monitor context is provided, use it.
Do not claim to have checked live systems unless the context says so.
For destructive actions such as stopping services or changing public ports, explain the safe next step instead of executing it.
"""


@dataclass(frozen=True)
class OllamaSettings:
    base_url: str
    model: str
    timeout_seconds: float
    user_agent: str


@dataclass(frozen=True)
class PreparedChat:
    model: str
    messages: list[dict[str, str]]
    rag_metadata: dict[str, Any]


def load_settings() -> OllamaSettings:
    return OllamaSettings(
        base_url=os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434").rstrip("/"),
        model=os.getenv("OLLAMA_MODEL", "gemma3"),
        timeout_seconds=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60")),
        user_agent=os.getenv("OLLAMA_USER_AGENT", "GlimpseAI/0.1").strip() or "GlimpseAI/0.1",
    )


def prepare_chat(payload: dict[str, Any], default_model: str) -> PreparedChat:
    model = str(payload.get("model") or default_model).strip() or default_model
    system = str(payload.get("system") or DEFAULT_SYSTEM_PROMPT).strip()
    feature_context, rag_metadata = build_tarot_prompt_context(payload)
    if feature_context:
        system = f"{system}\n\n{feature_context}" if system else feature_context

    raw_messages = payload.get("messages")
    messages: list[dict[str, str]] = []

    if system:
        messages.append({"role": "system", "content": system})

    if isinstance(raw_messages, list):
        for item in raw_messages:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").strip()
            content = str(item.get("content") or "").strip()
            if role in {"user", "assistant", "system"} and content:
                messages.append({"role": role, "content": content})

    message = str(payload.get("message") or "").strip()
    if message and not any(item["role"] == "user" for item in messages):
        messages.append({"role": "user", "content": message})

    if not any(item["role"] == "user" for item in messages):
        raise ValueError("message or messages with at least one user entry is required")

    return PreparedChat(model=model, messages=messages[-16:], rag_metadata=rag_metadata)


def build_messages(payload: dict[str, Any], default_model: str) -> tuple[str, list[dict[str, str]]]:
    prepared = prepare_chat(payload, default_model)
    return prepared.model, prepared.messages


def chat_with_ollama(payload: dict[str, Any], settings: OllamaSettings | None = None) -> dict[str, Any]:
    settings = settings or load_settings()
    prepared = prepare_chat(payload, settings.model)

    request_payload = {
        "model": prepared.model,
        "messages": prepared.messages,
        "stream": False,
    }

    data = json.dumps(request_payload).encode("utf-8")
    request = urllib.request.Request(
        f"{settings.base_url}/api/chat",
        data=data,
        headers=ollama_headers(settings),
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=settings.timeout_seconds) as response:
            ollama_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama returned HTTP {error.code}: {body[:500]}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Ollama is unreachable at {settings.base_url}: {error.reason}") from error

    message = ollama_payload.get("message") if isinstance(ollama_payload, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    answer = content or ollama_payload.get("response") or ""

    return {
        "answer": str(answer).strip(),
        "model": ollama_payload.get("model", prepared.model),
        "createdAt": ollama_payload.get("created_at"),
        "done": bool(ollama_payload.get("done", True)),
        "provider": "ollama",
        "ragUsed": bool(prepared.rag_metadata.get("ragUsed")),
        "rag": prepared.rag_metadata.get("retrieval"),
        "toolCalls": [],
        "raw": {
            "totalDuration": ollama_payload.get("total_duration"),
            "loadDuration": ollama_payload.get("load_duration"),
            "promptEvalCount": ollama_payload.get("prompt_eval_count"),
            "evalCount": ollama_payload.get("eval_count"),
        },
    }


def stream_chat_with_ollama(
    payload: dict[str, Any],
    settings: OllamaSettings | None = None,
) -> Iterator[dict[str, Any]]:
    settings = settings or load_settings()
    prepared = prepare_chat(payload, settings.model)

    request_payload = {
        "model": prepared.model,
        "messages": prepared.messages,
        "stream": True,
    }

    data = json.dumps(request_payload).encode("utf-8")
    request = urllib.request.Request(
        f"{settings.base_url}/api/chat",
        data=data,
        headers=ollama_headers(settings),
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=settings.timeout_seconds) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                chunk = json.loads(line)
                message = chunk.get("message") if isinstance(chunk, dict) else None
                content = message.get("content") if isinstance(message, dict) else ""
                yield {
                    "delta": str(content or ""),
                    "done": bool(chunk.get("done", False)),
                    "model": chunk.get("model", prepared.model),
                    "createdAt": chunk.get("created_at"),
                    "provider": "ollama",
                    "ragUsed": bool(prepared.rag_metadata.get("ragUsed")),
                    "rag": prepared.rag_metadata.get("retrieval") if chunk.get("done") else None,
                    "raw": {
                        "totalDuration": chunk.get("total_duration"),
                        "loadDuration": chunk.get("load_duration"),
                        "promptEvalCount": chunk.get("prompt_eval_count"),
                        "evalCount": chunk.get("eval_count"),
                    },
                }
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama returned HTTP {error.code}: {body[:500]}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Ollama is unreachable at {settings.base_url}: {error.reason}") from error


def ollama_headers(settings: OllamaSettings) -> dict[str, str]:
    return {
        "Accept": "application/x-ndjson, application/json",
        "Content-Type": "application/json",
        "User-Agent": settings.user_agent,
    }
