import { NextRequest, NextResponse } from "next/server";

import { agentFetch } from "@/app/lib/agent";
import { withGatewayRequestEvent } from "@/app/lib/gateway-events";
import type { DomainGatewayPolicy, PortMapping, PortMappingActionResult } from "@/app/types/monitor";

export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  return withGatewayRequestEvent(
    request,
    {
      routeTemplate: "/api/monitor/port-maps",
      upstream: "monitor-agent",
    },
    async () => {
      try {
        const payload = await agentFetch<{
          portMappings: PortMapping[];
          domainGateway: DomainGatewayPolicy;
        }>("/api/port-maps");
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

export async function POST(request: NextRequest) {
  return withGatewayRequestEvent(
    request,
    {
      routeTemplate: "/api/monitor/port-maps",
      upstream: "monitor-agent",
    },
    async () => {
      try {
        const body = await request.json();
        const payload = await agentFetch<PortMappingActionResult>("/api/port-maps/drafts", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Glimpse-Actor": "local-dashboard",
          },
          body: JSON.stringify(body),
        });
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
