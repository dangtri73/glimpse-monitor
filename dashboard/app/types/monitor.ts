export type ResourceSnapshot = {
  generatedAt: string;
  generatedAtMs: number;
  host: {
    hostname: string;
    platform: string;
    system: string;
    arch: string;
    cpuCount: number;
    uptimeSeconds: number | null;
  };
  resources: {
    cpu: {
      load1: number;
      load5: number;
      load15: number;
      loadPercent: number;
      cpuCount: number;
    };
    memory: {
      totalBytes: number;
      usedBytes: number;
      availableBytes: number;
      usedPercent: number;
    };
    disk: {
      mount: string;
      totalBytes: number;
      usedBytes: number;
      freeBytes: number;
      usedPercent: number;
    };
    network: {
      atMs: number;
      rxBytes: number;
      txBytes: number;
      rxBytesPerSecond: number;
      txBytesPerSecond: number;
      interfaces: Array<{
        name: string;
        rxBytes: number;
        txBytes: number;
      }>;
    };
  };
  topProcesses: ProcessSummary[];
  services: ServiceSummary[];
  topology: TopologySummary;
  portMappings: PortMapping[];
  domainGateway: DomainGatewayPolicy;
};

export type MetricSample = {
  generatedAt: string;
  generatedAtMs: number;
  cpuLoadPercent: number;
  memoryUsedPercent: number;
  diskUsedPercent: number;
  networkRxBytesPerSecond: number;
  networkTxBytesPerSecond: number;
};

export type ProcessSummary = {
  pid: number;
  command: string;
  cpuPercent: number;
  memoryPercent: number;
};

export type ServiceSummary = {
  id: string;
  name: string;
  status: "running" | "stopped" | string;
  processPattern: string;
  ports: number[];
  processes: Array<{ pid: number; command: string }>;
  actionsEnabled: boolean;
};

export type TopologySummary = {
  gateway: {
    id?: string;
    name?: string;
    role?: string;
    host?: string;
    lanIp?: string | null;
    notes?: string;
  };
  devices: DeviceSummary[];
  connections: ConnectionSummary[];
};

export type DeviceSummary = {
  id: string;
  name: string;
  role: string;
  lanIp: string | null;
  publicHost: string | null;
  healthPath: string | null;
  tags: string[];
};

export type ConnectionSummary = {
  id: string;
  from: string;
  to: string;
  label: string;
  status: string;
};

export type PortMapping = {
  id: string;
  name: string;
  publicHost: string;
  publicPort: number;
  targetId?: string;
  targetDeviceId: string;
  targetHost: string;
  targetPort: number;
  upstream?: string;
  protocol: string;
  status: string;
  authRequired: boolean;
  createdAt?: string;
  updatedAt?: string;
  verification?: DomainVerification;
};

export type DomainVerification = {
  method: "dns-txt" | string;
  name: string;
  value: string;
  status: "pending" | "verified" | string;
  checkedAt: string | null;
};

export type DomainGatewayTarget = {
  id: string;
  name: string;
  targetDeviceId: string;
  targetHost: string;
  targetPort: number;
  protocol: string;
};

export type DomainGatewayPolicy = {
  baseCname?: string;
  publicIp?: string;
  allowedPublicPorts: number[];
  allowedHostSuffixes: string[];
  targets: DomainGatewayTarget[];
};

export type PortMappingCheck = {
  id: string;
  ok: boolean;
  message: string;
};

export type PortMappingActionResult = {
  ok: boolean;
  dryRun?: boolean;
  mapping?: PortMapping;
  checks?: PortMappingCheck[];
  warnings?: Array<{ id: string; message: string; verification?: DomainVerification }>;
  records?: string[];
  expected?: string;
  renderedConfig?: string;
  generatedConfigPath?: string;
  message?: string;
  error?: string;
};
