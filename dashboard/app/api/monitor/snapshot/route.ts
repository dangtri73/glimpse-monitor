import { NextRequest, NextResponse } from "next/server";

import { agentFetch } from "@/app/lib/agent";
import { withGatewayRequestEvent } from "@/app/lib/gateway-events";
import type { ResourceSnapshot } from "@/app/types/monitor";

export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  return withGatewayRequestEvent(
    request,
    {
      routeTemplate: "/api/monitor/snapshot",
      upstream: "monitor-agent",
    },
    async () => {
      try {
        const snapshot = await agentFetch<ResourceSnapshot>("/api/snapshot");
        return NextResponse.json(snapshot);
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
