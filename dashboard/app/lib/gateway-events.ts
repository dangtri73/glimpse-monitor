import { randomUUID } from "crypto";
import { Kafka, logLevel, type Producer } from "kafkajs";
import type { NextRequest } from "next/server";

type GatewayRequestEvent = {
  eventId: string;
  observedAt: string;
  gatewayId: string;
  requestId: string;
  method: string;
  host: string;
  path: string;
  routeTemplate: string;
  queryShape: string;
  statusCode: number;
  durationMs: number;
  requestBytes: number | null;
  responseBytes: number | null;
  upstream: string;
  targetDeviceId: string | null;
  clientClass: string;
  errorClass: string | null;
  errorSummary: string | null;
  userAgentClass: string;
};

type RequestEventOptions = {
  routeTemplate: string;
  upstream: string;
  targetDeviceId?: string | null;
};

type Handler = () => Promise<Response> | Response;

const DEFAULT_TOPIC = "gateway.requests.raw";
const FAILURE_COOLDOWN_MS = 30_000;

let producerPromise: Promise<Producer> | null = null;
let lastFailureAt = 0;

export async function withGatewayRequestEvent(
  request: NextRequest,
  options: RequestEventOptions,
  handler: Handler,
) {
  const startedAt = Date.now();
  let response: Response | null = null;
  let caughtError: unknown = null;

  try {
    response = await handler();
    return response;
  } catch (error) {
    caughtError = error;
    throw error;
  } finally {
    const statusCode = response?.status ?? 500;
    const event = buildGatewayRequestEvent({
      request,
      options,
      statusCode,
      durationMs: Date.now() - startedAt,
      response,
      error: caughtError,
    });

    await publishGatewayRequestEvent(event);
  }
}

function buildGatewayRequestEvent({
  request,
  options,
  statusCode,
  durationMs,
  response,
  error,
}: {
  request: NextRequest;
  options: RequestEventOptions;
  statusCode: number;
  durationMs: number;
  response: Response | null;
  error: unknown;
}): GatewayRequestEvent {
  const url = request.nextUrl;
  const requestId = request.headers.get("x-request-id") ?? randomUUID();
  const userAgent = request.headers.get("user-agent") ?? "";

  return {
    eventId: randomUUID(),
    observedAt: new Date().toISOString(),
    gatewayId: process.env.GATEWAY_ID ?? "dev-gateway",
    requestId,
    method: request.method,
    host: request.headers.get("host") ?? url.host,
    path: url.pathname,
    routeTemplate: options.routeTemplate,
    queryShape: buildQueryShape(url.searchParams),
    statusCode,
    durationMs,
    requestBytes: numberHeader(request.headers.get("content-length")),
    responseBytes: response ? numberHeader(response.headers.get("content-length")) : null,
    upstream: options.upstream,
    targetDeviceId: options.targetDeviceId ?? null,
    clientClass: classifyClient(userAgent),
    errorClass: error ? errorName(error) : statusCode >= 500 ? "server_error" : null,
    errorSummary: error ? errorSummary(error) : null,
    userAgentClass: userAgent ? classifyUserAgent(userAgent) : "unknown",
  };
}

async function publishGatewayRequestEvent(event: GatewayRequestEvent) {
  if (!isKafkaEnabled()) return;
  if (Date.now() - lastFailureAt < FAILURE_COOLDOWN_MS) return;

  try {
    await withTimeout(
      (async () => {
        const producer = await getProducer();
        await producer.send({
          topic: process.env.KAFKA_GATEWAY_REQUEST_TOPIC ?? DEFAULT_TOPIC,
          messages: [
            {
              key: `${event.gatewayId}:${event.routeTemplate}`,
              value: JSON.stringify(event),
              headers: {
                event_type: "gateway.request",
                schema_version: "1",
              },
            },
          ],
        });
      })(),
      publishTimeoutMs(),
    );
  } catch (error) {
    lastFailureAt = Date.now();
    if (process.env.GATEWAY_REQUEST_EVENTS_LOG_FAILURES === "true") {
      console.warn("gateway request event publish failed", error);
    }
  }
}

function getProducer() {
  if (producerPromise) return producerPromise;

  const brokers = (process.env.KAFKA_BROKERS ?? "")
    .split(",")
    .map((broker) => broker.trim())
    .filter(Boolean);

  producerPromise = (async () => {
    const kafka = new Kafka({
      clientId: process.env.KAFKA_CLIENT_ID ?? "glimpse-dashboard",
      brokers,
      connectionTimeout: 1000,
      requestTimeout: 1500,
      logLevel: logLevel.NOTHING,
    });

    const producer = kafka.producer({
      allowAutoTopicCreation: false,
      idempotent: false,
    });

    await producer.connect();
    return producer;
  })();

  producerPromise.catch(() => {
    producerPromise = null;
  });

  return producerPromise;
}

function isKafkaEnabled() {
  const configured = Boolean(process.env.KAFKA_BROKERS?.trim());
  return process.env.GATEWAY_REQUEST_EVENTS_ENABLED !== "false" && configured;
}

function buildQueryShape(params: URLSearchParams) {
  const keys = Array.from(new Set(Array.from(params.keys()))).sort();
  if (!keys.length) return "none";
  return keys.map((key) => `${key}=redacted`).join("&");
}

function numberHeader(value: string | null) {
  if (!value) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function publishTimeoutMs() {
  const parsed = Number(process.env.KAFKA_PUBLISH_TIMEOUT_MS ?? "75");
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 75;
}

function classifyClient(userAgent: string) {
  const lower = userAgent.toLowerCase();
  if (!lower) return "unknown";
  if (lower.includes("mozilla")) return "browser";
  if (lower.includes("curl")) return "cli";
  if (lower.includes("prometheus")) return "metrics";
  return "service";
}

function classifyUserAgent(userAgent: string) {
  const lower = userAgent.toLowerCase();
  if (lower.includes("chrome")) return "chrome";
  if (lower.includes("safari")) return "safari";
  if (lower.includes("firefox")) return "firefox";
  if (lower.includes("curl")) return "curl";
  if (lower.includes("prometheus")) return "prometheus";
  return "other";
}

function errorName(error: unknown) {
  return error instanceof Error ? error.name : "unknown_error";
}

function errorSummary(error: unknown) {
  if (!(error instanceof Error)) return "Unknown error";
  return error.message.slice(0, 300);
}

async function withTimeout<T>(promise: Promise<T>, timeoutMs: number) {
  let timeout: ReturnType<typeof setTimeout> | undefined;

  try {
    return await Promise.race([
      promise,
      new Promise<never>((_resolve, reject) => {
        timeout = setTimeout(() => reject(new Error("Kafka publish timeout")), timeoutMs);
      }),
    ]);
  } finally {
    if (timeout) clearTimeout(timeout);
  }
}
