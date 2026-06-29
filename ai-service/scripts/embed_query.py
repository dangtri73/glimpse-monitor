#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

AGENT_DIR = Path(__file__).resolve().parents[1]
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from app.tarot_vector import TarotVectorSettings, embed_text  # noqa: E402


def main() -> None:
    load_env_file(AGENT_DIR / ".env", override=True)
    args = parse_args()
    question = read_question(args.question)
    if not question:
        raise SystemExit("Question is required. Pass it as an argument, pipe stdin, or type it at the prompt.")

    settings = TarotVectorSettings(
        provider="qdrant",
        qdrant_url=args.qdrant_url.rstrip("/"),
        collection=args.collection,
        embedding_base_url=args.embedding_base_url.rstrip("/"),
        embedding_model=args.embedding_model,
        timeout_seconds=args.timeout_seconds,
        user_agent=args.embedding_user_agent,
    )
    vector = embed_text(question, settings)

    if args.format == "qdrant-search":
        output: Any = {
            "vector": vector,
            "limit": args.limit,
            "with_payload": True,
            "with_vector": False,
        }
    elif args.format == "metadata":
        output = {
            "question": question,
            "embeddingBaseUrl": settings.embedding_base_url,
            "embeddingModel": settings.embedding_model,
            "dimensions": len(vector),
            "qdrantSearchPath": f"/collections/{settings.collection}/points/search",
        }
    else:
        output = vector

    print(json.dumps(output, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Embed a question with the configured Ollama embedding model.")
    parser.add_argument("question", nargs="*", help="Question text. If omitted, stdin or an interactive prompt is used.")
    parser.add_argument(
        "--format",
        choices=["vector", "qdrant-search", "metadata"],
        default="vector",
        help="Output raw vector, a Qdrant /points/search body, or vector metadata.",
    )
    parser.add_argument("--limit", type=int, default=5, help="Result limit used only with --format qdrant-search.")
    parser.add_argument("--qdrant-url", default=os.getenv("TAROT_QDRANT_URL", "http://127.0.0.1:6333"))
    parser.add_argument("--collection", default=os.getenv("TAROT_QDRANT_COLLECTION", "tarot_knowledge"))
    parser.add_argument(
        "--embedding-base-url",
        default=os.getenv("OLLAMA_EMBEDDING_BASE_URL", os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")),
    )
    parser.add_argument("--embedding-model", default=os.getenv("OLLAMA_EMBEDDING_MODEL", "bge-m3:latest"))
    parser.add_argument(
        "--embedding-user-agent",
        default=os.getenv("OLLAMA_EMBEDDING_USER_AGENT", os.getenv("OLLAMA_USER_AGENT", "GlimpseAI/0.1")),
    )
    parser.add_argument("--timeout-seconds", type=float, default=float(os.getenv("TAROT_INGEST_TIMEOUT_SECONDS", "120")))
    return parser.parse_args()


def read_question(parts: list[str]) -> str:
    if parts:
        return " ".join(parts).strip()
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    return input("Question: ").strip()


def load_env_file(path: Path, *, override: bool = False) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and (override or key not in os.environ):
            os.environ[key] = value


if __name__ == "__main__":
    main()
