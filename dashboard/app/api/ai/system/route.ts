import { NextRequest, NextResponse } from "next/server";

import { agentFetch } from "@/app/lib/agent";
import { withGatewayRequestEvent } from "@/app/lib/gateway-events";
import type { MetricSample, ResourceSnapshot } from "@/app/types/monitor";

const TOOLS = [
  "get_system_snapshot",
  "get_metric_samples",
  "compare_recent_windows",
  "get_service_status",
  "get_port_mappings",
];

export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  return withGatewayRequestEvent(
    request,
    {
      routeTemplate: "/api/ai/system",
      upstream: "ai-system",
    },
    async () => {
      const body = (await request.json().catch(() => ({}))) as { question?: string };
      const question = body.question?.trim() ?? "";

      if (!question) {
        return NextResponse.json({ error: "Question is required" }, { status: 400 });
      }

      try {
        const [snapshot, samplePayload] = await Promise.all([
          agentFetch<ResourceSnapshot>("/api/snapshot"),
          agentFetch<{ samples: MetricSample[] }>("/api/samples?limit=60"),
        ]);

        return NextResponse.json({
          answer: buildLocalAnswer(question, snapshot, samplePayload.samples),
          toolsUsed: ["get_system_snapshot", "get_metric_samples"],
          nextStep:
            "Replace this local responder with the LangGraph graph in glimpse-monitor/agent/ai/langgraph_tools.py when an LLM runtime is configured.",
          availableTools: TOOLS,
        });
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

function buildLocalAnswer(question: string, snapshot: ResourceSnapshot, samples: MetricSample[]) {
  const lower = question.toLowerCase();
  const cpu = snapshot.resources.cpu.loadPercent;
  const memory = snapshot.resources.memory.usedPercent;
  const disk = snapshot.resources.disk.usedPercent;
  const rx = formatBytes(snapshot.resources.network.rxBytesPerSecond);
  const tx = formatBytes(snapshot.resources.network.txBytesPerSecond);
  const runningServices = snapshot.services.filter((service) => service.status === "running").length;
  const stoppedServices = snapshot.services.length - runningServices;

  if (lower.includes("compare") || lower.includes("hour") || lower.includes("trend")) {
    const midpoint = Math.floor(samples.length / 2);
    const older = averageWindow(samples.slice(0, midpoint));
    const newer = averageWindow(samples.slice(midpoint));
    return `Recent trend: CPU changed ${signed(newer.cpu - older.cpu)} points, memory changed ${signed(
      newer.memory - older.memory,
    )} points, and network receive changed ${formatBytes(newer.rx - older.rx)}/s. This local mode compares the latest ${
      samples.length
    } samples; LangGraph should use persisted Postgres/TimescaleDB data for hour/day windows.`;
  }

  if (lower.includes("service")) {
    return `Services: ${runningServices} running, ${stoppedServices} stopped. Running services are ${snapshot.services
      .filter((service) => service.status === "running")
      .map((service) => service.name)
      .join(", ") || "none"}. Service control is disabled unless the agent is explicitly configured with safe commands.`;
  }

  if (lower.includes("port") || lower.includes("gateway") || lower.includes("nginx")) {
    return `Gateway mappings: ${snapshot.portMappings.length} configured. Public exposure should stay behind login, audit logs, and generated Nginx config review before reload. Current planned mapping targets ${snapshot.portMappings
      .map((mapping) => `${mapping.publicHost}:${mapping.publicPort} -> ${mapping.targetHost}:${mapping.targetPort}`)
      .join(", ") || "none"}.`;
  }

  return `Current system state: CPU ${cpu}%, RAM ${memory}%, disk ${disk}%, network ${rx}/s down and ${tx}/s up. ${
    stoppedServices > 0 ? `${stoppedServices} configured service(s) appear stopped.` : "All configured services appear running."
  }`;
}

function averageWindow(samples: MetricSample[]) {
  if (!samples.length) {
    return { cpu: 0, memory: 0, rx: 0 };
  }

  return {
    cpu: avg(samples.map((item) => item.cpuLoadPercent)),
    memory: avg(samples.map((item) => item.memoryUsedPercent)),
    rx: avg(samples.map((item) => item.networkRxBytesPerSecond)),
  };
}

function avg(values: number[]) {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function signed(value: number) {
  const rounded = Math.round(value * 100) / 100;
  return rounded > 0 ? `+${rounded}` : `${rounded}`;
}

function formatBytes(value: number) {
  const absolute = Math.abs(value);
  if (absolute > 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`;
  if (absolute > 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${value.toFixed(0)} B`;
}
