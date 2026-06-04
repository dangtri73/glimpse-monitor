import { NextRequest, NextResponse } from "next/server";

import { agentFetch } from "@/app/lib/agent";
import { withGatewayRequestEvent } from "@/app/lib/gateway-events";

type Params = {
  params: Promise<{
    serviceId: string;
    action: string;
  }>;
};

export const runtime = "nodejs";

export async function POST(request: NextRequest, { params }: Params) {
  return withGatewayRequestEvent(
    request,
    {
      routeTemplate: "/api/monitor/services/[serviceId]/[action]",
      upstream: "monitor-agent",
    },
    async () => {
      const resolvedParams = await params;
      const { serviceId, action } = resolvedParams;

      if (!["start", "stop", "restart"].includes(action)) {
        return NextResponse.json({ error: "Unsupported service action" }, { status: 400 });
      }

      try {
        const payload = await agentFetch(`/api/services/${serviceId}/${action}`, {
          method: "POST",
        });
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
