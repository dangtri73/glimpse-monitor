import { NextRequest, NextResponse } from "next/server";

import { agentFetch } from "@/app/lib/agent";
import { withGatewayRequestEvent } from "@/app/lib/gateway-events";
import type { PortMappingActionResult } from "@/app/types/monitor";

export const runtime = "nodejs";

const SUPPORTED_ACTIONS = new Set(["validate", "verify", "apply", "rollback"]);

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ mappingId: string; action: string }> },
) {
  return withGatewayRequestEvent(
    request,
    {
      routeTemplate: "/api/monitor/port-maps/[mappingId]/[action]",
      upstream: "monitor-agent",
    },
    async () => {
      const { mappingId, action } = await params;
      if (!SUPPORTED_ACTIONS.has(action)) {
        return NextResponse.json({ ok: false, error: "Unsupported port mapping action" }, { status: 400 });
      }

      try {
        const payload = await agentFetch<PortMappingActionResult>(
          `/api/port-maps/${encodeURIComponent(mappingId)}/${action}`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-Glimpse-Actor": "local-dashboard",
            },
          },
        );
        return NextResponse.json(payload, { status: payload.ok ? 200 : 400 });
      } catch (error) {
        return NextResponse.json(
          {
            ok: false,
            error: "Monitor agent is unavailable",
            detail: error instanceof Error ? error.message : "Unknown error",
          },
          { status: 502 },
        );
      }
    },
  );
}
