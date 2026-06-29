from __future__ import annotations

import re
from typing import Any

from .tarot_vector import load_vector_settings, retrieve_tarot_qdrant_documents

TAROT_FEATURE = "tarot"

TAROT_KNOWLEDGE: list[dict[str, Any]] = [
    {
        "id": "safety-entertainment",
        "title": "Tarot safety boundary",
        "tags": ["safety", "entertainment", "professional-advice"],
        "text": (
            "Tarot responses are for entertainment, journaling, and self-reflection. They must not be framed "
            "as factual predictions or as medical, legal, financial, or professional advice."
        ),
    },
    {
        "id": "reading-method",
        "title": "Reflective reading method",
        "tags": ["method", "spread", "reflection"],
        "text": (
            "Interpret the card, its spread position, orientation, and the user's question together. Prefer "
            "grounded reflection, pattern language, and a practical next step over certainty."
        ),
    },
    {
        "id": "general-spread",
        "title": "General five-card spread",
        "tags": ["general", "five-card", "path"],
        "text": (
            "A general five-card spread can move from present state, constraint, strength, area needing care, "
            "and potential. The synthesis should connect the cards into one coherent pattern."
        ),
    },
    {
        "id": "love-spread",
        "title": "Love tarot spread",
        "tags": ["love", "relationship", "heart"],
        "text": (
            "Love tarot should focus on emotional needs, communication patterns, expectations, boundaries, "
            "and mutual agency. Avoid claiming to know another person's private feelings as fact."
        ),
    },
    {
        "id": "yes-no-spread",
        "title": "Yes or no tarot spread",
        "tags": ["yes-no", "single-card", "choice"],
        "text": (
            "A yes/no tarot answer should give a symbolic leaning with nuance. Explain what would make the "
            "answer stronger or weaker rather than promising an outcome."
        ),
    },
    {
        "id": "daily-spread",
        "title": "Daily tarot focus",
        "tags": ["daily", "one-card", "action"],
        "text": (
            "Daily tarot is best as a short focus: mood, opportunity, friction, and one gentle action the user "
            "can take today."
        ),
    },
    {
        "id": "card-fool",
        "title": "The Fool",
        "tags": ["the fool", "fool", "beginning", "trust", "leap"],
        "text": "The Fool points to beginnings, trust, openness, experimentation, and the risk of moving without grounding.",
    },
    {
        "id": "card-magician",
        "title": "The Magician",
        "tags": ["the magician", "magician", "will", "tools", "focus"],
        "text": "The Magician points to skill, attention, available tools, deliberate action, and turning intent into form.",
    },
    {
        "id": "card-high-priestess",
        "title": "The High Priestess",
        "tags": ["the high priestess", "high priestess", "intuition", "mystery"],
        "text": "The High Priestess points to intuition, privacy, subtle knowledge, patience, and listening before acting.",
    },
    {
        "id": "card-empress",
        "title": "The Empress",
        "tags": ["the empress", "empress", "growth", "care", "abundance"],
        "text": "The Empress points to growth, care, creativity, embodiment, and the need to nourish what matters.",
    },
    {
        "id": "card-emperor",
        "title": "The Emperor",
        "tags": ["the emperor", "emperor", "structure", "authority", "boundaries"],
        "text": "The Emperor points to structure, boundaries, responsibility, stability, and the shadow of rigidity.",
    },
    {
        "id": "card-hierophant",
        "title": "The Hierophant",
        "tags": ["the hierophant", "hierophant", "tradition", "learning", "guidance"],
        "text": "The Hierophant points to tradition, teaching, shared values, mentorship, and inherited rules.",
    },
    {
        "id": "card-lovers",
        "title": "The Lovers",
        "tags": ["the lovers", "lovers", "choice", "values", "union"],
        "text": "The Lovers points to alignment, values, meaningful choice, attraction, and honest relationship with self and others.",
    },
    {
        "id": "card-chariot",
        "title": "The Chariot",
        "tags": ["the chariot", "chariot", "direction", "discipline", "momentum"],
        "text": "The Chariot points to disciplined movement, direction, confidence, and holding competing forces together.",
    },
    {
        "id": "card-strength",
        "title": "Strength",
        "tags": ["strength", "patience", "courage", "gentleness"],
        "text": "Strength points to courage through patience, self-trust, compassion, and calm influence instead of force.",
    },
    {
        "id": "card-hermit",
        "title": "The Hermit",
        "tags": ["the hermit", "hermit", "solitude", "wisdom", "search"],
        "text": "The Hermit points to inner searching, solitude, discernment, quiet study, and protecting attention.",
    },
    {
        "id": "card-wheel",
        "title": "Wheel of Fortune",
        "tags": ["wheel of fortune", "wheel", "cycle", "change", "timing"],
        "text": "Wheel of Fortune points to cycles, timing, change, uncertainty, and adapting to movement outside full control.",
    },
    {
        "id": "card-justice",
        "title": "Justice",
        "tags": ["justice", "truth", "balance", "accountability"],
        "text": "Justice points to fairness, accountability, cause and effect, truth-telling, and balanced decisions.",
    },
    {
        "id": "card-hanged-man",
        "title": "The Hanged Man",
        "tags": ["the hanged man", "hanged man", "pause", "surrender", "new view"],
        "text": "The Hanged Man points to pause, surrender, altered perspective, and releasing the need to force progress.",
    },
    {
        "id": "card-death",
        "title": "Death",
        "tags": ["death", "ending", "release", "renewal"],
        "text": "Death points to endings, release, transformation, grief, and the space made by letting an old form close.",
    },
    {
        "id": "card-temperance",
        "title": "Temperance",
        "tags": ["temperance", "balance", "healing", "integration"],
        "text": "Temperance points to moderation, integration, healing, patience, and combining differences carefully.",
    },
    {
        "id": "card-devil",
        "title": "The Devil",
        "tags": ["the devil", "devil", "attachment", "shadow", "choice"],
        "text": "The Devil points to attachment, temptation, avoidance, power dynamics, and reclaiming choice from a pattern.",
    },
    {
        "id": "card-tower",
        "title": "The Tower",
        "tags": ["the tower", "tower", "disruption", "truth", "liberation"],
        "text": "The Tower points to disruption, exposed truth, sudden change, and liberation from an unstable structure.",
    },
    {
        "id": "card-star",
        "title": "The Star",
        "tags": ["the star", "star", "hope", "renewal", "clarity"],
        "text": "The Star points to hope, renewal, honesty, calm inspiration, and reconnecting with a larger sense of meaning.",
    },
    {
        "id": "card-moon",
        "title": "The Moon",
        "tags": ["the moon", "moon", "uncertainty", "dream", "emotion"],
        "text": "The Moon points to uncertainty, emotion, projection, dreams, and the need to move gently through unclear terrain.",
    },
    {
        "id": "card-sun",
        "title": "The Sun",
        "tags": ["the sun", "sun", "joy", "vitality", "openness"],
        "text": "The Sun points to clarity, joy, vitality, confidence, visibility, and simple truth after confusion.",
    },
    {
        "id": "card-judgement",
        "title": "Judgement",
        "tags": ["judgement", "awakening", "calling", "review"],
        "text": "Judgement points to review, awakening, accountability, answering a call, and integrating the past.",
    },
    {
        "id": "card-world",
        "title": "The World",
        "tags": ["the world", "world", "completion", "integration", "arrival"],
        "text": "The World points to completion, integration, maturity, arrival, and seeing the whole pattern.",
    },
]


def build_tarot_prompt_context(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    tarot = _tarot_payload(payload)
    if not tarot:
        return "", {"ragUsed": False}

    selected_cards = _selected_cards(tarot)
    retrieval = tarot.get("retrieval") if isinstance(tarot.get("retrieval"), dict) else {}
    candidate_limit = _positive_int(retrieval.get("candidateLimit"), 24)
    rerank_limit = _positive_int(retrieval.get("rerankLimit"), 8)
    query = _retrieval_query(payload, tarot, selected_cards)
    documents, rag_mode = retrieve_tarot_documents(query, tarot, selected_cards, candidate_limit, rerank_limit)

    reading_label = _clean(tarot.get("readingLabel") or tarot.get("readingType") or "Tarot", 80)
    spread_name = _clean(tarot.get("spreadName") or "Tarot spread", 100)
    question = _clean(tarot.get("question") or payload.get("message") or "", 260)
    vector_db = _clean(retrieval.get("vectorDb") or "qdrant-or-pgvector", 80)
    reranker = _clean(retrieval.get("reranker") or "cross-encoder-compatible", 80)

    cards_block = "\n".join(
        f"- {card['position']}: {card['name']} ({card['orientation']}; keywords: {', '.join(card['keywords']) or 'none'})"
        for card in selected_cards
    ) or "- No cards selected."
    context_block = "\n".join(
        f"[{doc['id']}] {doc['title']}: {doc['text']}" for doc in documents
    )

    prompt = f"""Tarot entertainment mode is active.

RAG technical contract:
- Target vector DB: {vector_db}, collection: tarot_knowledge
- Retrieval query: {query}
- Candidate retrieval: top {candidate_limit} by embedding similarity with metadata filters for reading type and selected cards
- Rerank: top {rerank_limit} with {reranker}
- Current implementation: {rag_mode}

Reading context:
- Type: {reading_label}
- Spread: {spread_name}
- Question: {question or 'not provided'}
- Selected cards:
{cards_block}

Retrieved context:
{context_block}

Answer rules:
- Respond naturally in Vietnamese. Keep tarot card names in English when helpful, but explain their meaning in Vietnamese.
- Say this is an entertainment and self-reflection reading, not a factual prediction.
- Interpret each selected card through its spread position and orientation.
- Synthesize the spread into a coherent pattern.
- Give one grounded reflection and one practical next step.
- For love readings, do not claim certainty about another person's private feelings.
- For yes/no readings, give a symbolic leaning with caveats instead of certainty.
- Refuse medical, legal, financial, crisis, or professional advice and suggest a qualified professional where relevant.
"""

    return prompt, {
        "ragUsed": True,
        "ragMode": rag_mode,
        "retrieval": {
            "query": query,
            "vectorDb": vector_db,
            "candidateLimit": candidate_limit,
            "rerankLimit": rerank_limit,
            "reranker": reranker,
            "sources": [{"id": doc["id"], "title": doc["title"]} for doc in documents],
        },
    }


def retrieve_tarot_documents(
    query: str,
    tarot: dict[str, Any],
    selected_cards: list[dict[str, Any]],
    candidate_limit: int,
    rerank_limit: int,
) -> tuple[list[dict[str, Any]], str]:
    vector_settings = load_vector_settings()
    if vector_settings.provider != "memory":
        vector_documents = retrieve_tarot_qdrant_documents(query, rerank_limit)
        if vector_documents:
            return vector_documents, "qdrant_vector_search"

    tokens = set(_tokens(query))
    reading_type = _clean(tarot.get("readingType"), 60).lower()
    card_terms = {
        term
        for card in selected_cards
        for term in [card["name"].lower(), card["name"].lower().replace("the ", ""), *card["keywords"]]
        if term
    }

    scored: list[tuple[float, dict[str, Any]]] = []
    for document in TAROT_KNOWLEDGE:
        tags = [str(tag).lower() for tag in document["tags"]]
        doc_tokens = set(_tokens(" ".join([document["title"], document["text"], " ".join(tags)])))
        score = float(len(tokens & doc_tokens))
        if reading_type and reading_type in tags:
            score += 5
        if any(term in tags for term in card_terms):
            score += 6
        if document["id"] in {"safety-entertainment", "reading-method"}:
            score += 2
        scored.append((score, document))

    scored.sort(key=lambda item: item[0], reverse=True)
    candidates = [document for score, document in scored[:candidate_limit] if score > 0]
    if not candidates:
        candidates = [TAROT_KNOWLEDGE[0], TAROT_KNOWLEDGE[1]]
    rag_mode = "in_memory_seed" if vector_settings.provider == "memory" else "in_memory_seed_fallback"
    return candidates[:rerank_limit], rag_mode


def _tarot_payload(payload: dict[str, Any]) -> dict[str, Any]:
    tarot = payload.get("tarot")
    if isinstance(tarot, dict):
        return tarot
    if payload.get("feature") == TAROT_FEATURE:
        return {"question": payload.get("message")}
    return {}


def _selected_cards(tarot: dict[str, Any]) -> list[dict[str, Any]]:
    cards = tarot.get("selectedCards")
    if not isinstance(cards, list):
        return []

    selected: list[dict[str, Any]] = []
    for index, card in enumerate(cards[:10]):
        if not isinstance(card, dict):
            continue
        keywords = card.get("keywords")
        selected.append(
            {
                "name": _clean(card.get("name") or f"Card {index + 1}", 80),
                "position": _clean(card.get("position") or f"Card {index + 1}", 80),
                "orientation": _clean(card.get("orientation") or "upright", 24),
                "keywords": [_clean(keyword, 40).lower() for keyword in keywords[:8]]
                if isinstance(keywords, list)
                else [],
            }
        )
    return selected


def _retrieval_query(
    payload: dict[str, Any],
    tarot: dict[str, Any],
    selected_cards: list[dict[str, Any]],
) -> str:
    parts = [
        _clean(tarot.get("readingType"), 60),
        _clean(tarot.get("spreadName"), 100),
        _clean(tarot.get("question") or payload.get("message"), 260),
    ]
    for card in selected_cards:
        parts.extend([card["name"], card["position"], *card["keywords"]])
    return " ".join(part for part in parts if part).strip() or "tarot reading"


def _tokens(value: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", value.lower()) if len(token) > 2]


def _clean(value: Any, max_length: int) -> str:
    return str(value or "").strip()[:max_length]


def _positive_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback
