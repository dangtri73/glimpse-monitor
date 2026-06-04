"use client";

import type { MetricSample } from "@/app/types/monitor";

type MetricKey = keyof Pick<
  MetricSample,
  | "cpuLoadPercent"
  | "memoryUsedPercent"
  | "diskUsedPercent"
  | "networkRxBytesPerSecond"
  | "networkTxBytesPerSecond"
>;

type MiniChartProps = {
  title: string;
  samples: MetricSample[];
  keys: Array<{ key: MetricKey; color: string; label: string }>;
  unit?: "%" | "bytes";
  height?: number;
};

export function MiniChart({ title, samples, keys, unit = "%", height = 168 }: MiniChartProps) {
  const width = 720;
  const gradientId = `${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-grid`;
  const padded = samples.length > 1 ? samples : buildFlatSamples(keys);
  const values = keys.flatMap((item) => padded.map((sample) => sample[item.key] || 0));
  const max = Math.max(unit === "%" ? 100 : 1, ...values);
  const min = unit === "%" ? 0 : Math.min(0, ...values);

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div>
          <p className="eyebrow">{title}</p>
          <strong>{formatLatest(padded[padded.length - 1], keys, unit)}</strong>
        </div>
        <div className="chart-legend">
          {keys.map((item) => (
            <span key={item.key}>
              <i style={{ background: item.color }} />
              {item.label}
            </span>
          ))}
        </div>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={title}>
        <defs>
          <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="rgba(255,255,255,.18)" />
            <stop offset="100%" stopColor="rgba(255,255,255,.03)" />
          </linearGradient>
        </defs>
        <rect width={width} height={height} rx="18" fill={`url(#${gradientId})`} />
        {[0, 1, 2, 3].map((line) => (
          <line
            key={line}
            x1="18"
            x2={width - 18}
            y1={24 + line * 38}
            y2={24 + line * 38}
            stroke="rgba(255,255,255,.12)"
            strokeDasharray="5 7"
          />
        ))}
        {keys.map((item) => (
          <path
            key={item.key}
            d={buildPath(padded, item.key, width, height, min, max)}
            fill="none"
            stroke={item.color}
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="4"
          />
        ))}
      </svg>
    </div>
  );
}

function buildPath(
  samples: MetricSample[],
  key: MetricKey,
  width: number,
  height: number,
  min: number,
  max: number,
) {
  const left = 18;
  const right = width - 18;
  const top = 18;
  const bottom = height - 18;
  const range = Math.max(1, max - min);

  return samples
    .map((sample, index) => {
      const x = left + (index / Math.max(1, samples.length - 1)) * (right - left);
      const y = bottom - (((sample[key] || 0) - min) / range) * (bottom - top);
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

function buildFlatSamples(keys: Array<{ key: MetricKey }>): MetricSample[] {
  const sample = {
    generatedAt: "",
    generatedAtMs: Date.now(),
    cpuLoadPercent: 0,
    memoryUsedPercent: 0,
    diskUsedPercent: 0,
    networkRxBytesPerSecond: 0,
    networkTxBytesPerSecond: 0,
  };

  keys.forEach((item) => {
    sample[item.key] = 0;
  });

  return [sample, sample];
}

function formatLatest(
  sample: MetricSample | undefined,
  keys: Array<{ key: MetricKey; label: string }>,
  unit: "%" | "bytes",
) {
  if (!sample) return "Waiting for samples";

  return keys
    .map((item) => {
      const value = sample[item.key] || 0;
      return `${item.label} ${unit === "%" ? `${value.toFixed(1)}%` : `${formatBytes(value)}/s`}`;
    })
    .join(" - ");
}

function formatBytes(value: number) {
  if (value > 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`;
  if (value > 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${value.toFixed(0)} B`;
}
