"use client";

import type { CSSProperties } from "react";
import { useEffect, useRef, useState } from "react";

import { MiniChart } from "./MiniChart";
import type {
  DeviceSummary,
  DomainGatewayPolicy,
  MetricSample,
  PortMappingActionResult,
  PortMapping,
  ResourceSnapshot,
  ServiceSummary,
} from "@/app/types/monitor";

type AssistantResponse = {
  answer: string;
  model?: string;
  provider?: string;
  durationMs?: number;
  ragUsed?: boolean;
  error?: string;
  detail?: string;
};

type ChatStreamChunk = {
  delta?: string;
  done?: boolean;
  model?: string;
  durationMs?: number;
  error?: string;
  detail?: string;
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  meta?: string;
  pending?: boolean;
};

const REFRESH_MS = 2500;

export function DashboardShell() {
  const [snapshot, setSnapshot] = useState<ResourceSnapshot | null>(null);
  const [samples, setSamples] = useState<MetricSample[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>("mac-studio");
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string>("never");
  const [refreshNonce, setRefreshNonce] = useState(0);
  const [chatInput, setChatInput] = useState("Why is the sky blue?");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Ask a basic question and I will answer through Ollama. RAG and deeper system tools will be added later.",
      meta: "Ollama chat",
    },
  ]);
  const [assistantPending, setAssistantPending] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function refresh() {
      try {
        const [snapshotResponse, samplesResponse] = await Promise.all([
          fetch("/api/monitor/snapshot", { cache: "no-store" }),
          fetch("/api/monitor/samples?limit=90", { cache: "no-store" }),
        ]);

        if (!snapshotResponse.ok || !samplesResponse.ok) {
          throw new Error("Monitor agent is not reachable");
        }

        const nextSnapshot = (await snapshotResponse.json()) as ResourceSnapshot;
        const nextSamples = (await samplesResponse.json()) as { samples: MetricSample[] };

        if (cancelled) return;

        setSnapshot(nextSnapshot);
        setSamples(nextSamples.samples);
        setError(null);
        setLastUpdated(new Date().toLocaleTimeString());
      } catch (refreshError) {
        if (cancelled) return;
        setError(refreshError instanceof Error ? refreshError.message : "Unknown monitor error");
      }
    }

    refresh();
    const interval = window.setInterval(refresh, REFRESH_MS);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [refreshNonce]);

  const devices = snapshot?.topology.devices ?? [];
  const selectedDevice = devices.find((device) => device.id === selectedDeviceId) ?? devices[0] ?? null;

  async function askAssistant() {
    const prompt = chatInput.trim();
    if (!prompt || assistantPending) return;

    const userMessage: ChatMessage = {
      id: newId(),
      role: "user",
      content: prompt,
    };
    const pendingMessage: ChatMessage = {
      id: newId(),
      role: "assistant",
      content: "Thinking...",
      pending: true,
      meta: "Ollama",
    };
    const modelMessages = [...chatMessages.filter((item) => !item.pending), userMessage]
      .filter((item) => item.role === "user" || item.role === "assistant")
      .slice(-12)
      .map((item) => ({ role: item.role, content: item.content }));

    setChatMessages((current) => [...current, userMessage, pendingMessage]);
    setChatInput("");
    setAssistantPending(true);

    try {
      const response = await fetch("/api/ai/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: prompt,
          messages: modelMessages,
          system: buildMonitorSystemPrompt(snapshot),
          stream: true,
        }),
      });

      if (!response.ok || !response.body) {
        const payload = (await response.json().catch(() => ({}))) as AssistantResponse;
        const answer = `${payload.error ?? "Assistant unavailable"}. ${payload.detail ?? ""}`.trim();
        updateChatMessage(pendingMessage.id, answer, "error", false);
        return;
      }

      let streamedAnswer = "";
      let finalMeta = "Ollama stream";

      for await (const chunk of readSseChunks(response.body)) {
        if (chunk.error) {
          updateChatMessage(
            pendingMessage.id,
            `${chunk.error}. ${chunk.detail ?? ""}`.trim(),
            "error",
            false,
          );
          return;
        }

        if (chunk.delta) {
          streamedAnswer += chunk.delta;
          updateChatMessage(pendingMessage.id, streamedAnswer, finalMeta, true);
        }

        if (chunk.model || chunk.durationMs) {
          finalMeta = `${chunk.model ?? "model"}${chunk.durationMs ? ` - ${chunk.durationMs} ms` : ""}`;
        }
      }

      updateChatMessage(
        pendingMessage.id,
        streamedAnswer.trim() || "Ollama returned an empty answer.",
        finalMeta,
        false,
      );
    } catch (assistantError) {
      setChatMessages((current) =>
        current.map((message) =>
          message.id === pendingMessage.id
            ? {
                ...message,
                content: assistantError instanceof Error ? assistantError.message : "Assistant request failed.",
                meta: "error",
                pending: false,
              }
            : message,
        ),
      );
    } finally {
      setAssistantPending(false);
    }
  }

  function updateChatMessage(messageId: string, content: string, meta: string, pending: boolean) {
    setChatMessages((current) =>
      current.map((message) =>
        message.id === messageId
          ? {
              ...message,
              content,
              meta,
              pending,
            }
          : message,
      ),
    );
  }

  return (
    <main className="monitor-shell">
      <section className="hero-panel">
        <div className="hero-copy">
          <p className="eyebrow">Glimpse Dev Gateway</p>
          <h1>Resource map for services, devices, and public access.</h1>
          <p>
            Monitor live CPU, RAM, SSD, network flow, process health, and gateway mappings from
            one topology-first dashboard.
          </p>
        </div>
        <div className="hero-status">
          <span className={error ? "status-dot danger" : "status-dot"} />
          <div>
            <strong>{error ? "Agent offline" : "Live telemetry"}</strong>
            <small>{error ?? `Updated ${lastUpdated}`}</small>
          </div>
        </div>
      </section>

      <section className="grid metrics-grid">
        <Gauge
          label="CPU load"
          value={snapshot?.resources.cpu.loadPercent ?? 0}
          detail={snapshot ? `${snapshot.resources.cpu.cpuCount} cores - ${snapshot.resources.cpu.load1} load` : "Waiting"}
          color="#f7c96f"
        />
        <Gauge
          label="RAM used"
          value={snapshot?.resources.memory.usedPercent ?? 0}
          detail={snapshot ? `${formatBytes(snapshot.resources.memory.availableBytes)} free` : "Waiting"}
          color="#7ce7c7"
        />
        <Gauge
          label="SSD used"
          value={snapshot?.resources.disk.usedPercent ?? 0}
          detail={
            snapshot
              ? `${formatBytes(snapshot.resources.disk.freeBytes)} free on ${snapshot.resources.disk.mount}`
              : "Waiting"
          }
          color="#ff8c6b"
        />
        <NetworkCard snapshot={snapshot} />
      </section>

      <UserDiskUsagePanel snapshot={snapshot} />

      <section className="dashboard-grid">
        <TopologyPanel
          snapshot={snapshot}
          selectedDevice={selectedDevice}
          selectedDeviceId={selectedDevice?.id ?? null}
          onSelectDevice={setSelectedDeviceId}
        />
        <div className="stacked">
          <MiniChart
            title="Compute pressure"
            samples={samples}
            keys={[
              { key: "cpuLoadPercent", color: "#f7c96f", label: "CPU" },
              { key: "memoryUsedPercent", color: "#7ce7c7", label: "RAM" },
              { key: "diskUsedPercent", color: "#ff8c6b", label: "SSD" },
            ]}
          />
          <MiniChart
            title="Network throughput"
            samples={samples}
            unit="bytes"
            keys={[
              { key: "networkRxBytesPerSecond", color: "#8fc7ff", label: "RX" },
              { key: "networkTxBytesPerSecond", color: "#f4a7ff", label: "TX" },
            ]}
          />
        </div>
      </section>

      <section className="dashboard-grid lower-grid">
        <ServicesPanel services={snapshot?.services ?? []} onAction={() => setLastUpdated("refreshing")} />
        <PortMapsPanel
          mappings={snapshot?.portMappings ?? []}
          policy={snapshot?.domainGateway ?? null}
          onChanged={() => setRefreshNonce((current) => current + 1)}
        />
        <AssistantPanel
          input={chatInput}
          messages={chatMessages}
          pending={assistantPending}
          onInputChange={setChatInput}
          onAsk={askAssistant}
        />
      </section>

      <section className="process-panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Process Detail</p>
            <h2>Top resource consumers</h2>
          </div>
          <span>{snapshot?.host.hostname ?? "agent not connected"}</span>
        </div>
        <div className="process-list">
          {(snapshot?.topProcesses ?? []).map((process) => (
            <div className="process-row" key={`${process.pid}-${process.command}`}>
              <span>{process.pid}</span>
              <strong>{process.command}</strong>
              <meter max="100" value={process.cpuPercent} />
              <small>CPU {process.cpuPercent.toFixed(1)}%</small>
              <small>RAM {process.memoryPercent.toFixed(1)}%</small>
            </div>
          ))}
          {!snapshot?.topProcesses?.length && <p className="empty-state">Waiting for process data.</p>}
        </div>
      </section>
    </main>
  );
}

function UserDiskUsagePanel({ snapshot }: { snapshot: ResourceSnapshot | null }) {
  const disk = snapshot?.resources.disk;
  const users = disk?.userUsage ?? [];
  const scanInProgress = disk?.userUsageScanInProgress ?? false;
  const maxUserBytes = Math.max(...users.map((user) => user.usedBytes), 1);
  const scannedAt = disk?.userUsageScannedAtMs
    ? new Date(disk.userUsageScannedAtMs).toLocaleTimeString()
    : "waiting";
  const scanAge = typeof disk?.userUsageScanAgeSeconds === "number" ? `${disk.userUsageScanAgeSeconds}s ago` : scannedAt;

  return (
    <section className="panel user-disk-panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">SSD Detail</p>
          <h2>User storage</h2>
        </div>
        <span>{disk ? `${formatBytes(disk.freeBytes)} free` : "agent not connected"}</span>
      </div>

      <div className="disk-summary">
        <div>
          <small>Mount</small>
          <strong>{disk?.mount ?? "/"}</strong>
        </div>
        <div>
          <small>Users Root</small>
          <strong>{disk?.userUsageRoot || "waiting for scan"}</strong>
        </div>
        <div>
          <small>Users Total</small>
          <strong>{formatBytes(disk?.userUsageTotalBytes ?? 0)}</strong>
        </div>
        <div>
          <small>Scanned</small>
          <strong>{scanAge}</strong>
        </div>
      </div>

      <div className="user-disk-list">
        {users.map((user) => {
          const width = user.usedBytes > 0 ? Math.max(2, (user.usedBytes / maxUserBytes) * 100) : 0;
          return (
            <article className="user-disk-row" key={user.path}>
              <div className="user-disk-user">
                <strong>{user.name}</strong>
                <small>{user.path}</small>
              </div>
              <div className="user-disk-size">
                <strong>{formatBytes(user.usedBytes)}</strong>
                <small>{formatPercent(user.usedPercentOfDisk)} of SSD</small>
              </div>
              <div
                className="user-disk-meter"
                aria-label={`${user.name} uses ${formatBytes(user.usedBytes)}`}
              >
                <span style={{ width: `${width}%` }} />
              </div>
            </article>
          );
        })}
      </div>

      {disk?.userUsageError && !scanInProgress && <p className="panel-note">{disk.userUsageError}</p>}
      {!users.length && (
        <p className="empty-state">
          {scanInProgress ? "Scanning user disk usage in the background." : "Waiting for user disk usage scan."}
        </p>
      )}
    </section>
  );
}

function Gauge({ label, value, detail, color }: { label: string; value: number; detail: string; color: string }) {
  const bounded = Math.max(0, Math.min(100, value));

  return (
    <article className="metric-card">
      <div
        className="gauge"
        style={{
          "--value": `${bounded * 3.6}deg`,
          "--gauge-color": color,
        } as CSSProperties}
      >
        <span>{bounded.toFixed(0)}%</span>
      </div>
      <div>
        <p className="eyebrow">{label}</p>
        <strong>{detail}</strong>
      </div>
    </article>
  );
}

function NetworkCard({ snapshot }: { snapshot: ResourceSnapshot | null }) {
  return (
    <article className="metric-card wide">
      <div className="network-runes">
        <span />
        <span />
        <span />
      </div>
      <div>
        <p className="eyebrow">Network</p>
        <strong>
          RX {formatRate(snapshot?.resources.network.rxBytesPerSecond ?? 0)} - TX{" "}
          {formatRate(snapshot?.resources.network.txBytesPerSecond ?? 0)}
        </strong>
        <small>
          {(snapshot?.resources.network.interfaces ?? []).map((item) => item.name).join(", ") ||
            "waiting for interfaces"}
        </small>
      </div>
    </article>
  );
}

function TopologyPanel({
  snapshot,
  selectedDevice,
  selectedDeviceId,
  onSelectDevice,
}: {
  snapshot: ResourceSnapshot | null;
  selectedDevice: DeviceSummary | null;
  selectedDeviceId: string | null;
  onSelectDevice: (deviceId: string) => void;
}) {
  const gateway = snapshot?.topology.gateway;
  const devices = snapshot?.topology.devices ?? [];

  return (
    <section className="panel topology-panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">System Map</p>
          <h2>Gateway connections</h2>
        </div>
        <span>{devices.length} devices</span>
      </div>

      <div className="topology-canvas">
        <button className="node gateway-node" type="button">
          <strong>{gateway?.name ?? "Dev Gateway"}</strong>
          <small>{gateway?.host ?? "public host"}</small>
        </button>
        <div className="connection-lines" aria-hidden="true">
          {devices.map((device) => (
            <i key={device.id} />
          ))}
        </div>
        <div className="device-cluster">
          {devices.map((device) => (
            <button
              className={device.id === selectedDeviceId ? "node device-node active" : "node device-node"}
              key={device.id}
              type="button"
              onClick={() => onSelectDevice(device.id)}
            >
              <strong>{device.name}</strong>
              <small>{device.role}</small>
            </button>
          ))}
        </div>
      </div>

      <DeviceDetail device={selectedDevice} mappings={snapshot?.portMappings ?? []} />
    </section>
  );
}

function DeviceDetail({ device, mappings }: { device: DeviceSummary | null; mappings: PortMapping[] }) {
  if (!device) {
    return <p className="empty-state">Connect the agent to show devices.</p>;
  }

  return (
    <div className="detail-drawer">
      <div>
        <p className="eyebrow">Expanded Device</p>
        <h3>{device.name}</h3>
      </div>
      <dl>
        <div>
          <dt>Role</dt>
          <dd>{device.role}</dd>
        </div>
        <div>
          <dt>LAN</dt>
          <dd>{device.lanIp ?? "not set"}</dd>
        </div>
        <div>
          <dt>Public</dt>
          <dd>{device.publicHost ?? "private only"}</dd>
        </div>
        <div>
          <dt>Health</dt>
          <dd>{device.healthPath ?? "not configured"}</dd>
        </div>
      </dl>
      <div className="pill-row">
        {device.tags.map((tag) => (
          <span key={tag}>{tag}</span>
        ))}
      </div>
      <div className="mapping-summary">
        {mappings
          .filter((mapping) => mapping.targetDeviceId === device.id)
          .map((mapping) => (
            <small key={mapping.id}>
              {mapping.publicHost}:{mapping.publicPort} routes to {mapping.targetHost}:{mapping.targetPort}
            </small>
          ))}
      </div>
    </div>
  );
}

function ServicesPanel({
  services,
  onAction,
}: {
  services: ServiceSummary[];
  onAction: (serviceId: string, action: string) => void;
}) {
  async function runAction(serviceId: string, action: string) {
    onAction(serviceId, action);
    await fetch(`/api/monitor/services/${serviceId}/${action}`, { method: "POST" });
  }

  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Services</p>
          <h2>Runtime control</h2>
        </div>
        <span>{services.filter((service) => service.status === "running").length} running</span>
      </div>

      <div className="service-list">
        {services.map((service) => (
          <article className="service-row" key={service.id}>
            <div>
              <strong>{service.name}</strong>
              <small>{service.ports.length ? `ports ${service.ports.join(", ")}` : service.processPattern}</small>
            </div>
            <span className={service.status === "running" ? "status-pill ok" : "status-pill"}>
              {service.status}
            </span>
            <div className="action-row">
              {["start", "stop", "restart"].map((action) => (
                <button key={action} type="button" onClick={() => runAction(service.id, action)}>
                  {action}
                </button>
              ))}
            </div>
          </article>
        ))}
        {!services.length && <p className="empty-state">Waiting for service data.</p>}
      </div>
    </section>
  );
}

function PortMapsPanel({
  mappings,
  policy,
  onChanged,
}: {
  mappings: PortMapping[];
  policy: DomainGatewayPolicy | null;
  onChanged: () => void;
}) {
  const targets = policy?.targets ?? [];
  const defaultTargetId = targets[0]?.id ?? "";
  const defaultPort = policy?.allowedPublicPorts?.[0] ?? 80;
  const [publicHost, setPublicHost] = useState("");
  const [targetId, setTargetId] = useState(defaultTargetId);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [result, setResult] = useState<PortMappingActionResult | null>(null);

  useEffect(() => {
    if (!targetId && defaultTargetId) {
      setTargetId(defaultTargetId);
    }
  }, [defaultTargetId, targetId]);

  async function createDraft() {
    const host = publicHost.trim();
    if (!host || !targetId) return;

    setBusyAction("create");
    setResult(null);
    try {
      const response = await fetch("/api/monitor/port-maps", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          publicHost: host,
          publicPort: defaultPort,
          targetId,
          protocol: "http",
        }),
      });
      const payload = (await response.json()) as PortMappingActionResult;
      setResult(payload);
      if (payload.ok) {
        setPublicHost("");
        onChanged();
      }
    } catch (error) {
      setResult({ ok: false, error: error instanceof Error ? error.message : "Request failed" });
    } finally {
      setBusyAction(null);
    }
  }

  async function runMappingAction(mappingId: string, action: "validate" | "verify" | "apply" | "rollback") {
    const actionKey = `${mappingId}:${action}`;
    setBusyAction(actionKey);
    setResult(null);
    try {
      const response = await fetch(`/api/monitor/port-maps/${mappingId}/${action}`, { method: "POST" });
      const payload = (await response.json()) as PortMappingActionResult;
      setResult(payload);
      if (payload.ok) onChanged();
    } catch (error) {
      setResult({ ok: false, error: error instanceof Error ? error.message : "Request failed" });
    } finally {
      setBusyAction(null);
    }
  }

  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Gateway</p>
          <h2>Domain gateway</h2>
        </div>
        <span>{mappings.filter((mapping) => mapping.status === "active").length} active</span>
      </div>

      <div className="domain-form">
        <label>
          <span>Domain</span>
          <input
            value={publicHost}
            onChange={(event) => setPublicHost(event.target.value)}
            placeholder="app.example.com"
          />
        </label>
        <label>
          <span>Target</span>
          <select value={targetId} onChange={(event) => setTargetId(event.target.value)}>
            {targets.map((target) => (
              <option key={target.id} value={target.id}>
                {target.name}
              </option>
            ))}
          </select>
        </label>
        <button
          className="primary-button"
          type="button"
          onClick={createDraft}
          disabled={!publicHost.trim() || !targetId || busyAction === "create"}
        >
          {busyAction === "create" ? "Creating..." : "Create draft"}
        </button>
      </div>

      {policy && (
        <div className="gateway-dns">
          <small>A {policy.publicIp ?? "public-ip-not-set"}</small>
          {policy.baseCname && <small>CNAME {policy.baseCname}</small>}
        </div>
      )}

      <div className="map-list">
        {mappings.map((mapping) => (
          <article key={mapping.id}>
            <div>
              <strong>{mapping.name}</strong>
              <small>
                {mapping.publicHost}:{mapping.publicPort} -&gt; {mapping.targetHost}:{mapping.targetPort}
              </small>
              {mapping.verification && (
                <small>
                  TXT {mapping.verification.name} = {mapping.verification.value}
                </small>
              )}
            </div>
            <div className="map-actions">
              <span className={mapping.status === "active" ? "status-pill ok" : "status-pill"}>
                {mapping.status}
              </span>
              <button
                type="button"
                onClick={() => runMappingAction(mapping.id, "validate")}
                disabled={busyAction === `${mapping.id}:validate`}
              >
                Validate
              </button>
              <button
                type="button"
                onClick={() => runMappingAction(mapping.id, "verify")}
                disabled={busyAction === `${mapping.id}:verify`}
              >
                Verify
              </button>
              <button
                type="button"
                onClick={() => runMappingAction(mapping.id, "apply")}
                disabled={busyAction === `${mapping.id}:apply` || mapping.status === "active"}
              >
                Apply
              </button>
              <button
                type="button"
                onClick={() => runMappingAction(mapping.id, "rollback")}
                disabled={busyAction === `${mapping.id}:rollback` || mapping.status === "disabled"}
              >
                Rollback
              </button>
            </div>
          </article>
        ))}
        {!mappings.length && <p className="empty-state">No mappings configured yet.</p>}
      </div>
      {result && (
        <div className={result.ok ? "action-result ok" : "action-result"}>
          <strong>{result.ok ? result.message ?? "Action completed." : result.error ?? "Action failed."}</strong>
          {result.dryRun && <small>Dry run only</small>}
          {result.checks?.map((check) => (
            <small key={check.id}>
              {check.ok ? "OK" : "Fail"} - {check.message}
            </small>
          ))}
          {result.warnings?.map((warning) => (
            <small key={warning.id}>Warning - {warning.message}</small>
          ))}
        </div>
      )}
    </section>
  );
}

function AssistantPanel({
  input,
  messages,
  pending,
  onInputChange,
  onAsk,
}: {
  input: string;
  messages: ChatMessage[];
  pending: boolean;
  onInputChange: (question: string) => void;
  onAsk: () => void;
}) {
  const threadRef = useRef<HTMLDivElement | null>(null);
  const previousMessageCountRef = useRef(messages.length);

  useEffect(() => {
    const thread = threadRef.current;
    if (!thread) return;

    const behavior: ScrollBehavior =
      messages.length > previousMessageCountRef.current ? "smooth" : "auto";
    previousMessageCountRef.current = messages.length;
    thread.scrollTo({ top: thread.scrollHeight, behavior });
  }, [messages]);

  return (
    <section className="panel assistant-panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">AI Operator</p>
          <h2>Ollama chat</h2>
        </div>
        <span>RAG later</span>
      </div>
      <div className="chat-thread" aria-live="polite" ref={threadRef}>
        {messages.map((message) => (
          <article
            className={message.role === "user" ? "chat-message user" : "chat-message assistant"}
            key={message.id}
          >
            <small>{message.role === "user" ? "You" : message.meta ?? "Assistant"}</small>
            <p>{message.content}</p>
          </article>
        ))}
      </div>
      <textarea
        value={input}
        onChange={(event) => onInputChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
            event.preventDefault();
            onAsk();
          }
        }}
        rows={4}
        placeholder="Ask a question. Press Cmd/Ctrl + Enter to send."
      />
      <button className="primary-button" type="button" onClick={onAsk} disabled={pending || !input.trim()}>
        {pending ? "Thinking..." : "Send"}
      </button>
    </section>
  );
}

function buildMonitorSystemPrompt(snapshot: ResourceSnapshot | null) {
  const base =
    "You are Glimpse, a concise local dev-gateway assistant. Answer plainly. RAG is not enabled yet. If current monitor context is provided, use it as factual context.";

  if (!snapshot) return base;

  const services = snapshot.services
    .map((service) => `${service.name}:${service.status}`)
    .slice(0, 8)
    .join(", ");
  const userDisk = (snapshot.resources.disk.userUsage ?? [])
    .map((user) => `${user.name}:${formatBytes(user.usedBytes)}`)
    .slice(0, 6)
    .join(", ");

  return `${base}

Current monitor context:
- host: ${snapshot.host.hostname}
- cpu: ${snapshot.resources.cpu.loadPercent}%
- ram: ${snapshot.resources.memory.usedPercent}%
- disk: ${snapshot.resources.disk.usedPercent}%
- user disk: ${userDisk || "not scanned"}
- network: rx ${formatRate(snapshot.resources.network.rxBytesPerSecond)}, tx ${formatRate(
    snapshot.resources.network.txBytesPerSecond,
  )}
- services: ${services || "none"}
`;
}

async function* readSseChunks(stream: ReadableStream<Uint8Array>): AsyncGenerator<ChatStreamChunk> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";

      for (const frame of frames) {
        const data = frame
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trim())
          .join("\n");

        if (!data) continue;
        yield JSON.parse(data) as ChatStreamChunk;
      }
    }

    buffer += decoder.decode();
    if (buffer.trim()) {
      const data = buffer
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trim())
        .join("\n");
      if (data) yield JSON.parse(data) as ChatStreamChunk;
    }
  } finally {
    reader.releaseLock();
  }
}

function newId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function formatBytes(value: number) {
  if (value > 1024 ** 4) return `${(value / 1024 ** 4).toFixed(1)} TB`;
  if (value > 1024 ** 3) return `${(value / 1024 ** 3).toFixed(1)} GB`;
  if (value > 1024 ** 2) return `${(value / 1024 ** 2).toFixed(1)} MB`;
  if (value > 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${value.toFixed(0)} B`;
}

function formatPercent(value: number | null | undefined) {
  const safeValue = Number.isFinite(value) ? Number(value) : 0;
  return `${safeValue >= 10 ? safeValue.toFixed(0) : safeValue.toFixed(1)}%`;
}

function formatRate(value: number) {
  return `${formatBytes(value)}/s`;
}
