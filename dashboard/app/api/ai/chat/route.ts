import { NextRequest, NextResponse } from "next/server";

import { withGatewayRequestEvent } from "@/app/lib/gateway-events";

type ChatMessage = {
  role: "system" | "user" | "assistant";
  content: string;
};

type ChatRequestBody = {
  message?: string;
  messages?: ChatMessage[];
  system?: string;
  model?: string;
  stream?: boolean;
  feature?: string;
  tarot?: unknown;
};

export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  return withGatewayRequestEvent(
    request,
    {
      routeTemplate: "/api/ai/chat",
      upstream: "ai-service",
    },
    async () => {
      const body = (await request.json().catch(() => ({}))) as ChatRequestBody;
      const message = body.message?.trim();
      const messages = sanitizeMessages(body.messages ?? []);

      if (!message && !messages.some((item) => item.role === "user")) {
        return NextResponse.json({ error: "Message is required" }, { status: 400 });
      }

      try {
        const response = await fetch(`${aiServiceUrl()}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message,
            messages,
            system: body.system,
            model: body.model ?? process.env.AI_CHAT_MODEL ?? "gemma3",
            stream: body.stream === true,
            feature: sanitizeFeature(body.feature),
            tarot: sanitizeTarotContext(body.tarot),
          }),
          signal: AbortSignal.timeout(aiTimeoutMs()),
        });

        if (body.stream === true && response.ok && response.body) {
          return new Response(response.body, {
            status: 200,
            headers: {
              "Content-Type": "text/event-stream; charset=utf-8",
              "Cache-Control": "no-cache, no-transform",
              Connection: "keep-alive",
            },
          });
        }

        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          return NextResponse.json(
            {
              error: "AI service is unavailable",
              detail: payload.detail ?? payload.error ?? "Unknown AI service error",
            },
            { status: 502 },
          );
        }

        return NextResponse.json(payload);
      } catch (error) {
        return NextResponse.json(
          {
            error: "AI service is unavailable",
            detail: error instanceof Error ? error.message : "Unknown AI service error",
          },
          { status: 502 },
        );
      }
    },
  );
}

function sanitizeMessages(messages: ChatMessage[]) {
  return messages
    .filter((item) => ["system", "user", "assistant"].includes(item.role))
    .map((item) => ({ role: item.role, content: String(item.content ?? "").trim() }))
    .filter((item) => item.content)
    .slice(-16);
}

function sanitizeFeature(feature: string | undefined) {
  return feature === "tarot" ? "tarot" : undefined;
}

function sanitizeTarotContext(value: unknown) {
  if (!value || typeof value !== "object") return undefined;

  const record = value as Record<string, unknown>;
  const selectedCards = Array.isArray(record.selectedCards)
    ? record.selectedCards
        .slice(0, 10)
        .map((item) => sanitizeTarotCard(item))
        .filter((item) => item !== null)
    : [];
  const retrieval = record.retrieval && typeof record.retrieval === "object"
    ? (record.retrieval as Record<string, unknown>)
    : {};

  return {
    stage: boundedString(record.stage, 24),
    readingType: boundedString(record.readingType, 40),
    readingLabel: boundedString(record.readingLabel, 60),
    spreadName: boundedString(record.spreadName, 80),
    question: boundedString(record.question, 240),
    selectedCards,
    retrieval: {
      vectorDb: boundedString(retrieval.vectorDb, 80),
      candidateLimit: boundedNumber(retrieval.candidateLimit, 24),
      rerankLimit: boundedNumber(retrieval.rerankLimit, 8),
      reranker: boundedString(retrieval.reranker, 80),
    },
  };
}

function sanitizeTarotCard(value: unknown) {
  if (!value || typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  const keywords = Array.isArray(record.keywords)
    ? record.keywords.map((keyword) => boundedString(keyword, 32)).filter(Boolean).slice(0, 8)
    : [];

  return {
    id: boundedString(record.id, 80),
    name: boundedString(record.name, 80),
    position: boundedString(record.position, 80),
    orientation: boundedString(record.orientation, 20),
    suit: boundedString(record.suit, 40),
    keywords,
  };
}

function boundedString(value: unknown, maxLength: number) {
  return String(value ?? "").trim().slice(0, maxLength);
}

function boundedNumber(value: unknown, fallback: number) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? Math.min(parsed, 100) : fallback;
}

function aiServiceUrl() {
  return (process.env.AI_SERVICE_URL ?? "http://127.0.0.1:8770").replace(/\/$/, "");
}

function aiTimeoutMs() {
  const parsed = Number(process.env.AI_CHAT_TIMEOUT_MS ?? "70000");
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 70000;
}
