# AI Operator Tools

The AI feature should be a LangGraph agent with constrained tools. It should not have raw shell access.

## Tools

- `get_system_snapshot`: live CPU, RAM, disk, network, devices, services, mappings.
- `get_metric_samples`: recent chart samples.
- `compare_recent_windows`: compare newest metric window with previous window.
- `get_service_status`: configured service state and process IDs.
- `get_port_mappings`: gateway exposure rules.
- `search_runbooks`: RAG over docs, runbooks, Nginx templates, incident notes.
- `query_metric_history`: Timescale query for hour/day/week comparisons.
- `create_port_mapping_draft`: creates a pending mapping, not active config.

## Response Quality

The assistant should answer with:

- current facts first
- trend or comparison if the question asks for time windows
- uncertainty if the agent lacks stored history
- recommended next action when a service or resource is unhealthy
- no destructive action without explicit user approval

## Current Wiring

Basic chat is now implemented in:

```txt
ai-service/
dashboard/app/api/ai/chat/route.ts
dashboard/app/components/DashboardShell.tsx
```

Current flow:

```txt
Dashboard chat panel
  -> /api/ai/chat
  -> ai-service /api/chat
  -> Ollama /api/chat
```

RAG and LangGraph are not wired yet.

## Future Wiring

Prototype code lives in `agent/ai/langgraph_tools.py`.

For production:

```txt
LangGraph node
  -> classify question
  -> call live tools and history tools
  -> retrieve relevant runbook docs
  -> answer with cited tool observations
```

Use a local Ollama-compatible model for private system questions when possible. Keep cloud model usage optional because monitoring data may include private hostnames, IPs, paths, and process names.
