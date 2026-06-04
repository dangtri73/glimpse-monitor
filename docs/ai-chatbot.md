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

If Ollama is exposed through your dev gateway, set:

```env
OLLAMA_BASE_URL=https://dev.api.hftvn.com/ai
OLLAMA_MODEL=gemma3
```

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

Response:

```json
{
  "answer": "Short answer from Ollama",
  "model": "gemma3:270m",
  "provider": "ollama",
  "ragUsed": false
}
```

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
