import { NextRequest, NextResponse } from "next/server";

import { agentFetch } from "@/app/lib/agent";
import { withGatewayRequestEvent } from "@/app/lib/gateway-events";
import type { ServiceSummary } from "@/app/types/monitor";

export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  return withGatewayRequestEvent(
    request,
    {
      routeTemplate: "/api/monitor/services",
      upstream: "monitor-agent",
    },
    async () => {
      try {
        const payload = await agentFetch<{ services: ServiceSummary[] }>("/api/services");
        return NextResponse.json(payload);
      } catch (error) {
        return NextResponse.json(
          {
            error: "Monitor agent is unavailable",
            detail: error instanceof Error ? error.message : "Unknown error",
          },
          { status: 502 },
        );
      }
    },
  );
}
