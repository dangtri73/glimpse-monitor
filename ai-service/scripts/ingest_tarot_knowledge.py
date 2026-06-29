from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

AGENT_DIR = Path(__file__).resolve().parents[1]
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from app.tarot_rag import TAROT_KNOWLEDGE  # noqa: E402
from app.tarot_vector import TarotVectorSettings, embed_text  # noqa: E402


METABISMUTH_TAROT_IMAGES_URL = "https://raw.githubusercontent.com/metabismuth/tarot-json/master/tarot-images.json"
HF_PARQUET_URL = "https://huggingface.co/datasets/barissglc/tarot/resolve/main/tarot_readings.parquet"
HF_ROWS_URL = "https://datasets-server.huggingface.co/rows"
SOURCE_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://glimpse.local/tarot-knowledge")


def main() -> None:
    load_env_file(AGENT_DIR / ".env", override=True)
    args = parse_args()
    qdrant_url = args.qdrant_url.rstrip("/")
    collection = args.collection
    hf_cache_path = Path(args.hf_cache_path)
    if not hf_cache_path.is_absolute():
        hf_cache_path = AGENT_DIR / hf_cache_path
    settings = TarotVectorSettings(
        provider="qdrant",
        qdrant_url=qdrant_url,
        collection=collection,
        embedding_base_url=args.embedding_base_url.rstrip("/"),
        embedding_model=args.embedding_model,
        timeout_seconds=args.timeout_seconds,
        user_agent=args.embedding_user_agent,
    )

    documents = build_documents(
        include_hf=args.include_hf,
        hf_source=args.hf_source,
        hf_limit=args.hf_limit,
        hf_page_size=args.hf_page_size,
        hf_page_delay_seconds=args.hf_page_delay_seconds,
        hf_fetch_retries=args.hf_fetch_retries,
        hf_parquet_url=args.hf_parquet_url,
        hf_cache_path=hf_cache_path,
        timeout_seconds=args.timeout_seconds,
    )
    source_counts = count_by_source(documents)
    if args.dry_run:
        print(json.dumps({"documents": len(documents), "sources": source_counts, "sample": documents[:3]}, ensure_ascii=False, indent=2))
        return

    if not documents:
        raise SystemExit("No tarot documents were loaded.")

    print(f"embedding base url: {settings.embedding_base_url}")
    print(f"embedding model: {settings.embedding_model}")

    first_vector = embed_document(document_text(documents[0]), settings, args.embedding_retries)
    ensure_collection(qdrant_url, collection, len(first_vector), args.recreate, args.timeout_seconds)

    batch: list[dict[str, Any]] = []
    upserted = 0
    started_at = time.time()
    for index, document in enumerate(documents):
        vector = first_vector if index == 0 else embed_document(document_text(document), settings, args.embedding_retries)
        batch.append(
            {
                "id": str(uuid.uuid5(SOURCE_NAMESPACE, document["id"])),
                "vector": vector,
                "payload": document,
            }
        )
        if len(batch) >= args.batch_size:
            upsert_points(qdrant_url, collection, batch, args.timeout_seconds)
            upserted += len(batch)
            print(f"upserted {upserted}/{len(documents)}")
            batch = []

    if batch:
        upsert_points(qdrant_url, collection, batch, args.timeout_seconds)
        upserted += len(batch)

    print(
        json.dumps(
            {
                "ok": True,
                "collection": collection,
                "documents": upserted,
                "sources": source_counts,
                "embeddingModel": args.embedding_model,
                "durationSeconds": round(time.time() - started_at, 2),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest tarot deck and reading examples into Qdrant.")
    default_include_hf = bool_env("TAROT_INCLUDE_HF", True)
    parser.add_argument("--qdrant-url", default=os.getenv("TAROT_QDRANT_URL", "http://127.0.0.1:6333"))
    parser.add_argument("--collection", default=os.getenv("TAROT_QDRANT_COLLECTION", "tarot_knowledge"))
    parser.add_argument("--embedding-base-url", default=os.getenv("OLLAMA_EMBEDDING_BASE_URL", os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")))
    parser.add_argument("--embedding-model", default=os.getenv("OLLAMA_EMBEDDING_MODEL", "bge-m3:latest"))
    parser.add_argument("--embedding-user-agent", default=os.getenv("OLLAMA_EMBEDDING_USER_AGENT", os.getenv("OLLAMA_USER_AGENT", "GlimpseAI/0.1")))
    parser.add_argument("--timeout-seconds", type=float, default=float(os.getenv("TAROT_INGEST_TIMEOUT_SECONDS", "120")))
    parser.add_argument("--embedding-retries", type=int, default=int(os.getenv("TAROT_INGEST_RETRIES", "3")))
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--recreate", action="store_true", help="Delete and recreate the target Qdrant collection.")
    parser.add_argument("--include-hf", dest="include_hf", action="store_true", default=default_include_hf, help="Include Hugging Face barissglc/tarot reading examples.")
    parser.add_argument("--skip-hf", dest="include_hf", action="store_false", help="Skip Hugging Face barissglc/tarot reading examples.")
    parser.add_argument("--hf-source", choices=["parquet", "rows"], default=os.getenv("TAROT_HF_SOURCE", "parquet"))
    parser.add_argument("--hf-parquet-url", default=os.getenv("TAROT_HF_PARQUET_URL", HF_PARQUET_URL))
    parser.add_argument("--hf-cache-path", default=os.getenv("TAROT_HF_CACHE_PATH", str(AGENT_DIR / ".cache" / "tarot_readings.parquet")))
    parser.add_argument("--hf-limit", type=int, default=int(os.getenv("TAROT_HF_LIMIT", "6000")), help="Maximum Hugging Face example rows to import.")
    parser.add_argument("--hf-page-size", type=int, default=100)
    parser.add_argument("--hf-page-delay-seconds", type=float, default=float(os.getenv("TAROT_HF_PAGE_DELAY_SECONDS", "0.5")))
    parser.add_argument("--hf-fetch-retries", type=int, default=int(os.getenv("TAROT_HF_FETCH_RETRIES", "6")))
    parser.add_argument("--dry-run", action="store_true", help="Build documents but do not embed or write to Qdrant.")
    return parser.parse_args()


def embed_document(text: str, settings: TarotVectorSettings, retries: int) -> list[float]:
    attempts = max(1, retries + 1)
    last_error: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return embed_text(text, settings)
        except (RuntimeError, TimeoutError, urllib.error.URLError, OSError) as error:
            last_error = error
            if attempt >= attempts:
                break
            sleep_seconds = min(2 * attempt, 10)
            print(f"embedding attempt {attempt}/{attempts} failed: {error}; retrying in {sleep_seconds}s", file=sys.stderr)
            time.sleep(sleep_seconds)
    raise RuntimeError(f"Embedding failed after {attempts} attempts: {last_error}") from last_error


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


def bool_env(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def build_documents(
    include_hf: bool,
    hf_source: str,
    hf_limit: int,
    hf_page_size: int,
    hf_page_delay_seconds: float,
    hf_fetch_retries: int,
    hf_parquet_url: str,
    hf_cache_path: Path,
    timeout_seconds: float,
) -> list[dict[str, Any]]:
    documents = seed_documents()
    documents.extend(deck_documents(timeout_seconds))
    if include_hf:
        documents.extend(
            huggingface_example_documents(
                hf_source,
                hf_limit,
                hf_page_size,
                hf_page_delay_seconds,
                hf_fetch_retries,
                hf_parquet_url,
                hf_cache_path,
                timeout_seconds,
            )
        )
    return dedupe_documents(documents)


def seed_documents() -> list[dict[str, Any]]:
    return [
        {
            "id": f"seed:{item['id']}",
            "title": item["title"],
            "text": item["text"],
            "tags": item.get("tags", []),
            "source": "glimpse_seed",
            "kind": "tarot_seed_context",
        }
        for item in TAROT_KNOWLEDGE
    ]


def deck_documents(timeout_seconds: float) -> list[dict[str, Any]]:
    payload = fetch_json(METABISMUTH_TAROT_IMAGES_URL, timeout_seconds)
    cards = payload.get("cards") if isinstance(payload, dict) else None
    if not isinstance(cards, list):
        return []

    documents: list[dict[str, Any]] = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        name = clean(card.get("name"))
        if not name:
            continue
        arcana = clean(card.get("arcana"))
        suit = clean(card.get("suit"))
        number = clean(card.get("number"))
        img = clean(card.get("img"))
        tags = [name.lower(), arcana.lower()]
        if suit:
            tags.append(suit.lower())
        documents.append(
            {
                "id": f"deck:{slug(name)}",
                "title": name,
                "text": f"{name} is a {arcana} tarot card. Number: {number or 'not applicable'}. Suit: {suit or 'none'}.",
                "tags": [tag for tag in tags if tag],
                "source": "metabismuth/tarot-json",
                "license": "MIT for dataset; Rider-Waite-Smith image public-domain status varies by country",
                "kind": "tarot_card",
                "card": {
                    "name": name,
                    "number": number,
                    "arcana": arcana,
                    "suit": suit or None,
                    "image": img or None,
                },
            }
        )
    return documents


def huggingface_example_documents(
    source: str,
    limit: int,
    page_size: int,
    page_delay_seconds: float,
    fetch_retries: int,
    parquet_url: str,
    cache_path: Path,
    timeout_seconds: float,
) -> list[dict[str, Any]]:
    if source == "parquet":
        return huggingface_parquet_documents(limit, parquet_url, cache_path, timeout_seconds)
    return huggingface_rows_documents(limit, page_size, page_delay_seconds, fetch_retries, timeout_seconds)


def huggingface_parquet_documents(limit: int, parquet_url: str, cache_path: Path, timeout_seconds: float) -> list[dict[str, Any]]:
    try:
        import pandas as pd  # type: ignore[import-not-found]
    except ImportError as error:
        raise SystemExit(
            "Reading barissglc/tarot parquet requires pandas and pyarrow. "
            "Install them with: python3 -m pip install -r requirements-ingest.txt"
        ) from error

    download_file(parquet_url, cache_path, timeout_seconds)
    frame = pd.read_parquet(cache_path)
    records = frame.head(max(0, limit)).to_dict(orient="records")
    return huggingface_row_documents(records)


def huggingface_rows_documents(
    limit: int,
    page_size: int,
    page_delay_seconds: float,
    fetch_retries: int,
    timeout_seconds: float,
) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    offset = 0
    page_size = max(1, min(page_size, 100))
    while len(documents) < limit:
        length = min(page_size, limit - len(documents))
        params = urllib.parse.urlencode(
            {
                "dataset": "barissglc/tarot",
                "config": "default",
                "split": "train",
                "offset": offset,
                "length": length,
            }
        )
        payload = fetch_json(f"{HF_ROWS_URL}?{params}", timeout_seconds, retries=fetch_retries)
        rows = payload.get("rows") if isinstance(payload, dict) else None
        if not rows:
            break
        page_records: list[dict[str, Any]] = []
        for row_item in rows:
            row = row_item.get("row") if isinstance(row_item, dict) else None
            if not isinstance(row, dict):
                continue
            row_idx = int(row_item.get("row_idx", offset + len(documents)))
            page_records.append({**row, "_row_idx": row_idx})
        documents.extend(huggingface_row_documents(page_records))
        offset += len(rows)
        if page_delay_seconds > 0 and len(documents) < limit:
            time.sleep(page_delay_seconds)
    return documents


def huggingface_row_documents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for row_idx, row in enumerate(rows):
        row = normalize_row_keys(row)
        source_row_idx = int(row.get("_row_idx", row_idx))
        cards = [clean(row.get("Card 1")), clean(row.get("Card 2")), clean(row.get("Card 3"))]
        reading = clean(row.get("Reading"))
        if not reading:
            continue
        title = "Example reading: " + " / ".join(card for card in cards if card)
        documents.append(
            {
                "id": f"hf:barissglc-tarot:{source_row_idx}",
                "title": title,
                "text": f"Cards: {', '.join(card for card in cards if card)}.\nReading: {reading}",
                "tags": [slug(card).replace("-", " ") for card in cards if card] + ["three-card", "example-reading"],
                "source": "huggingface/barissglc/tarot",
                "license": "not declared on dataset card at ingestion time",
                "kind": "tarot_example_reading",
                "dataset": "barissglc/tarot",
                "rowIndex": source_row_idx,
                "card1": cards[0] or None,
                "card2": cards[1] or None,
                "card3": cards[2] or None,
                "reading": reading,
                "cards": cards,
            }
        )
    return documents


def normalize_row_keys(row: dict[str, Any]) -> dict[str, Any]:
    return {clean(key): value for key, value in row.items()}


def dedupe_documents(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for document in documents:
        document_id = str(document.get("id") or "").strip()
        if not document_id or document_id in seen:
            continue
        seen.add(document_id)
        deduped.append(document)
    return deduped


def document_text(document: dict[str, Any]) -> str:
    tags = ", ".join(str(tag) for tag in document.get("tags", []))
    return f"{document.get('title', '')}\n{document.get('text', '')}\nTags: {tags}".strip()


def count_by_source(documents: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for document in documents:
        source = str(document.get("source") or "unknown")
        counts[source] = counts.get(source, 0) + 1
    return counts


def ensure_collection(qdrant_url: str, collection: str, vector_size: int, recreate: bool, timeout_seconds: float) -> None:
    collection_url = f"{qdrant_url}/collections/{collection}"
    if recreate:
        request_json(collection_url, None, "DELETE", timeout_seconds, accept_404=True)

    current = request_json(collection_url, None, "GET", timeout_seconds, accept_404=True)
    if current:
        return

    request_json(
        collection_url,
        {"vectors": {"size": vector_size, "distance": "Cosine"}},
        "PUT",
        timeout_seconds,
    )


def upsert_points(qdrant_url: str, collection: str, points: list[dict[str, Any]], timeout_seconds: float) -> None:
    request_json(
        f"{qdrant_url}/collections/{collection}/points?wait=true",
        {"points": points},
        "PUT",
        timeout_seconds,
    )


def fetch_json(url: str, timeout_seconds: float, *, retries: int = 3) -> dict[str, Any]:
    attempts = max(1, retries + 1)
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": os.getenv("OLLAMA_USER_AGENT", "GlimpseAI/0.1")},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt >= attempts:
                raise
            retry_after = parse_retry_after(error.headers.get("Retry-After"))
            sleep_seconds = retry_after if retry_after is not None else min(2 * attempt, 30)
            print(f"fetch attempt {attempt}/{attempts} was rate limited; retrying in {sleep_seconds}s", file=sys.stderr)
            time.sleep(sleep_seconds)
    raise RuntimeError(f"Failed to fetch JSON from {url}")


def download_file(url: str, destination: Path, timeout_seconds: float) -> None:
    if destination.exists():
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/octet-stream", "User-Agent": os.getenv("OLLAMA_USER_AGENT", "GlimpseAI/0.1")},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        destination.write_bytes(response.read())


def parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def request_json(
    url: str,
    payload: dict[str, Any] | None,
    method: str,
    timeout_seconds: float,
    *,
    accept_404: bool = False,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as error:
        if accept_404 and error.code == 404:
            return {}
        raise


def clean(value: Any) -> str:
    return str(value or "").strip()


def slug(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")


if __name__ == "__main__":
    main()
