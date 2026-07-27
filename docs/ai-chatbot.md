# Basic AI Chatbot

## Current Implementation

The basic chatbot is implemented as a separate service:

```txt
glimpse-monitor/ai-service
```

Current flow:

```txt
Dashboard chat panel
  -> Next.js API route /api/ai/chat
  -> ai-service /api/chat
  -> Ollama /api/chat
  -> answer returned to dashboard
```

RAG is not implemented yet.

## Why It Is Separate From The Agent

The monitor agent should stay focused on OS collection and safe service control.

The chatbot has different responsibilities:

- Ollama model calls
- LangGraph later
- RAG later
- prompt management
- chat history later
- retrieval from ClickHouse/Postgres/Qdrant later

Keeping it in `ai-service` prevents heavy AI logic from making the OS agent less reliable.

## Local URLs

```txt
Dashboard chat: http://localhost:3000
AI service:     http://127.0.0.1:8771
AI health:      http://127.0.0.1:8771/health
```

## Ollama Configuration

Default Docker config:

```env
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=gemma3:270m
```

The dev gateway no longer exposes a default public Ollama/API route. Use `http://host.docker.internal:11434` from Docker on Mac Studio, or an SSH tunnel for private remote testing.

The service calls:

```txt
POST {OLLAMA_BASE_URL}/api/chat
```

## API

Request:

```json
{
  "message": "Why is the sky blue?",
  "model": "gemma3:270m",
  "stream": false
}
```

Tarot entertainment request:

```json
{
  "feature": "tarot",
  "message": "Please read this General tarot spread for my question.",
  "stream": true,
  "tarot": {
    "stage": "reading",
    "readingType": "general",
    "readingLabel": "General",
    "spreadName": "Five-card path",
    "question": "What should I understand about my current path?",
    "selectedCards": [
      {
        "id": "fool",
        "name": "The Fool",
        "position": "Where you are now",
        "orientation": "upright",
        "suit": "Major Arcana",
        "keywords": ["beginning", "trust", "leap"]
      }
    ],
    "retrieval": {
      "vectorDb": "qdrant-or-pgvector",
      "candidateLimit": 24,
      "rerankLimit": 8,
      "reranker": "cross-encoder-compatible"
    }
  }
}
```

Response:

```json
{
  "answer": "Short answer from Ollama",
  "model": "gemma3:270m",
  "provider": "ollama",
  "ragUsed": false,
  "rag": null
}
```

For `feature: "tarot"`, `ai-service` builds a tarot-specific system prompt before calling Ollama. The prompt includes:

- entertainment-only and professional-advice safety boundaries
- selected spread type, user question, card positions, card names, and orientation
- an explicit RAG technical contract for vector retrieval and reranking
- retrieved context from Qdrant when `tarot_knowledge` is populated, otherwise the in-memory seed corpus

Current tarot RAG status:

```txt
Dashboard /entertain
  -> /api/ai/chat with feature=tarot and tarot context
  -> ai-service prompt builder
  -> Qdrant tarot_knowledge collection when available
  -> in-memory tarot_knowledge fallback when Qdrant is unavailable or empty
  -> Ollama /api/chat
```

The Qdrant ingestion script can import:

- local Glimpse tarot seed documents
- `metabismuth/tarot-json` canonical 78-card deck metadata
- optional `barissglc/tarot` Hugging Face three-card example readings

`metabismuth/tarot-json` is MIT licensed. The Hugging Face dataset does not declare a license on its dataset card, so keep that import optional unless the deployment owner has accepted the source risk.

Start Qdrant:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor/infra
docker compose up -d qdrant
```

Ingest only seed docs plus the canonical deck:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor/ai-service
python3 scripts/ingest_tarot_knowledge.py --recreate
```

Add Hugging Face examples when licensing is acceptable:

```bash
python3 scripts/ingest_tarot_knowledge.py --include-hf --hf-limit 500
```

Set `--hf-limit 5769` to import the full displayed dataset.

Streaming request:

```json
{
  "message": "Why is the sky blue?",
  "model": "gemma3:270m",
  "stream": true
}
```

Streaming responses use server-sent events:

```txt
data: {"delta":"The","done":false}

data: {"delta":" sky","done":false}

data: {"done":true,"durationMs":1234}
```

## Start

Start the service through Compose:

```bash
cd /Users/vutri/Desktop/projects/Glimpse/glimpse-monitor/infra
docker compose up -d --build ai-service
```

Check health:

```bash
curl http://127.0.0.1:8771/health
```

Test direct chat:

```bash
curl -s http://127.0.0.1:8771/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Hi","model":"gemma3:270m"}'
```

Test direct streaming chat:

```bash
curl -N http://127.0.0.1:8771/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Hi","model":"gemma3:270m","stream":true}'
```

Test through the dashboard API:

```bash
curl -s http://127.0.0.1:3000/api/ai/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Hi"}'
```

Test through the dashboard streaming proxy:

```bash
curl -N http://127.0.0.1:3000/api/ai/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Hi","stream":true}'
```

## Next RAG Steps

Later flow:

```txt
Dashboard chat
  -> ai-service
  -> LangGraph planner
  -> tools:
      live system state from monitor agent
      ClickHouse gateway logs
      Postgres/Timescale metrics history
      Qdrant runbooks and technical docs
  -> Ollama answer with cited context
```

Recommended next tools:

- `get_live_snapshot`
- `query_gateway_logs`
- `query_metric_history`
- `search_runbooks`
- `search_incident_summaries`
