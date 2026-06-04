const DEFAULT_AGENT_URL = "http://127.0.0.1:8765";

export class AgentError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
  }
}

export function agentBaseUrl() {
  return process.env.MONITOR_AGENT_URL ?? DEFAULT_AGENT_URL;
}

export async function agentFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const adminToken = process.env.MONITOR_AGENT_ADMIN_TOKEN;
  if (adminToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${adminToken}`);
  }

  const response = await fetch(`${agentBaseUrl()}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  if (!response.ok) {
    throw new AgentError(`Monitor agent returned ${response.status}`, response.status);
  }

  return response.json() as Promise<T>;
}
