from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TarotVectorSettings:
    provider: str
    qdrant_url: str
    collection: str
    embedding_base_url: str
    embedding_model: str
    timeout_seconds: float
    user_agent: str


def load_vector_settings() -> TarotVectorSettings:
    return TarotVectorSettings(
        provider=os.getenv("TAROT_RAG_PROVIDER", "auto").strip().lower() or "auto",
        qdrant_url=os.getenv("TAROT_QDRANT_URL", "http://qdrant:6333").rstrip("/"),
        collection=os.getenv("TAROT_QDRANT_COLLECTION", "tarot_knowledge").strip() or "tarot_knowledge",
        embedding_base_url=os.getenv("OLLAMA_EMBEDDING_BASE_URL", os.getenv("OLLAMA_BASE_URL", "")).rstrip("/"),
        embedding_model=os.getenv("OLLAMA_EMBEDDING_MODEL", "bge-m3:latest").strip() or "bge-m3:latest",
        timeout_seconds=float(os.getenv("TAROT_RAG_TIMEOUT_SECONDS", "3")),
        user_agent=(
            os.getenv("OLLAMA_EMBEDDING_USER_AGENT")
            or os.getenv("OLLAMA_USER_AGENT")
            or "GlimpseAI/0.1"
        ).strip(),
    )


def retrieve_tarot_qdrant_documents(query: str, limit: int) -> list[dict[str, Any]]:
    settings = load_vector_settings()
    if settings.provider == "memory" or not settings.qdrant_url or not settings.embedding_base_url:
        return []

    try:
        if not qdrant_collection_available(settings):
            return []
        vector = embed_text(query, settings)
        payload = {
            "vector": vector,
            "limit": max(1, min(limit, 20)),
            "with_payload": True,
        }
        response = request_json(
            f"{settings.qdrant_url}/collections/{settings.collection}/points/search",
            payload,
            timeout=settings.timeout_seconds,
            user_agent=settings.user_agent,
        )
    except (RuntimeError, ValueError, urllib.error.URLError, TimeoutError):
        return []

    documents: list[dict[str, Any]] = []
    for item in response.get("result", []):
        payload = item.get("payload") if isinstance(item, dict) else None
        if not isinstance(payload, dict):
            continue
        text = str(payload.get("text") or "").strip()
        title = str(payload.get("title") or payload.get("name") or payload.get("id") or "Tarot context").strip()
        document_id = str(payload.get("id") or item.get("id") or title).strip()
        if not text:
            continue
        documents.append(
            {
                "id": document_id,
                "title": title,
                "text": text,
                "score": item.get("score"),
                "source": payload.get("source"),
                "tags": payload.get("tags", []),
            }
        )
    return documents


def qdrant_collection_available(settings: TarotVectorSettings) -> bool:
    request = urllib.request.Request(
        f"{settings.qdrant_url}/collections/{settings.collection}",
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.timeout_seconds):
            return True
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return False
        raise


def embed_text(text: str, settings: TarotVectorSettings) -> list[float]:
    response = request_json(
        f"{settings.embedding_base_url}/api/embeddings",
        {"model": settings.embedding_model, "prompt": text},
        timeout=settings.timeout_seconds,
        user_agent=settings.user_agent,
    )
    vector = response.get("embedding")
    if not isinstance(vector, list) or not vector:
        raise RuntimeError("Ollama embedding response did not include an embedding vector.")
    return [float(value) for value in vector]


def request_json(
    url: str,
    payload: dict[str, Any],
    timeout: float,
    user_agent: str | None = None,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": user_agent
            or os.getenv("OLLAMA_EMBEDDING_USER_AGENT")
            or os.getenv("OLLAMA_USER_AGENT")
            or "GlimpseAI/0.1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code} from {url}: {body[:500]}") from error
