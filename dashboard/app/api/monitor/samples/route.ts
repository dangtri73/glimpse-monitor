import { NextRequest, NextResponse } from "next/server";

import { agentFetch } from "@/app/lib/agent";
import { withGatewayRequestEvent } from "@/app/lib/gateway-events";
import type { MetricSample } from "@/app/types/monitor";

export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  return withGatewayRequestEvent(
    request,
    {
      routeTemplate: "/api/monitor/samples",
      upstream: "monitor-agent",
    },
    async () => {
      const limit = request.nextUrl.searchParams.get("limit") ?? "120";

      try {
        const payload = await agentFetch<{ samples: MetricSample[] }>(`/api/samples?limit=${limit}`);
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
