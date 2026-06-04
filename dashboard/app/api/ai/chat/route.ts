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

function aiServiceUrl() {
  return (process.env.AI_SERVICE_URL ?? "http://127.0.0.1:8770").replace(/\/$/, "");
}

function aiTimeoutMs() {
  const parsed = Number(process.env.AI_CHAT_TIMEOUT_MS ?? "70000");
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 70000;
}
