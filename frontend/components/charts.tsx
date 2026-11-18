"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { OverviewResponse } from "@/types/contract";

const AXIS = "#94a3b8";
const GRID = "#e2e8f0";

const tooltipStyle = {
  borderRadius: 12,
  border: "1px solid #e2e8f0",
  fontSize: 12,
  boxShadow: "0 10px 30px rgba(15,23,42,.08)",
};

export const CHART_COLORS = ["#0d9488", "#0891b2", "#2563eb", "#7c3aed", "#db2777", "#ea580c"];

function shortDate(value: string): string {
  const parts = value.split("-");
  return parts.length === 3 ? `${parts[2]}/${parts[1]}` : value;
}

function AnomalyDot(props: { cx?: number; cy?: number; payload?: { anomaly?: boolean } }) {
  const { cx, cy, payload } = props;
  if (cx === undefined || cy === undefined) return null;
  if (payload?.anomaly) {
    return (
      <g>
        <circle cx={cx} cy={cy} r={7} fill="#dc2626" opacity={0.18} />
        <circle cx={cx} cy={cy} r={4} fill="#dc2626" stroke="#ffffff" strokeWidth={1.5} />
      </g>
    );
  }
  return <circle cx={cx} cy={cy} r={1.8} fill="#0d9488" />;
}

export function TrendChart({ data }: { data: OverviewResponse["trends"] }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={data} margin={{ top: 10, right: 8, left: -18, bottom: 0 }}>
        <defs>
          <linearGradient id="complaints" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0d9488" stopOpacity={0.28} />
            <stop offset="100%" stopColor="#0d9488" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis
          dataKey="date"
          tickFormatter={shortDate}
          tick={{ fontSize: 11, fill: AXIS }}
          tickLine={false}
          axisLine={{ stroke: GRID }}
          minTickGap={24}
        />
        <YAxis tick={{ fontSize: 11, fill: AXIS }} tickLine={false} axisLine={false} allowDecimals={false} />
        <Tooltip
          contentStyle={tooltipStyle}
          labelFormatter={(value) => String(value)}
          formatter={(value) => [`${value} complaints`, "Complaints"]}
        />
        <Area
          type="monotone"
          dataKey="complaints"
          stroke="#0d9488"
          strokeWidth={2}
          fill="url(#complaints)"
          dot={<AnomalyDot />}
          activeDot={{ r: 4 }}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function CategoryChart({ data }: { data: OverviewResponse["categoryBreakdown"] }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} horizontal={false} />
        <XAxis type="number" tick={{ fontSize: 11, fill: AXIS }} axisLine={false} tickLine={false} allowDecimals={false} />
        <YAxis
          type="category"
          dataKey="category"
          width={128}
          tick={{ fontSize: 11, fill: AXIS }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip contentStyle={tooltipStyle} formatter={(value) => [`${value} complaints`, ""]} />
        <Bar dataKey="count" radius={[0, 6, 6, 0]} barSize={16}>
          {data.map((entry, index) => (
            <Cell key={entry.category} fill={CHART_COLORS[index % CHART_COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function RiskDistributionChart({
  data,
}: {
  data: OverviewResponse["riskDistribution"];
}) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} horizontal={false} />
        <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11, fill: AXIS }} axisLine={false} tickLine={false} />
        <YAxis
          type="category"
          dataKey="name"
          width={112}
          tick={{ fontSize: 11, fill: AXIS }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip contentStyle={tooltipStyle} formatter={(value) => [`${value}/100`, "Risk"]} />
        <Bar dataKey="riskScore" radius={[0, 6, 6, 0]} barSize={14}>
          {data.map((entry) => (
            <Cell
              key={`${entry.group}-${entry.name}`}
              fill={entry.riskScore >= 70 ? "#dc2626" : entry.riskScore >= 50 ? "#ea580c" : "#0d9488"}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function ProductsChart({ data }: { data: OverviewResponse["topProblemProducts"] }) {
  const rows = data.map((item) => ({
    name: item.productName ?? item.productId,
    complaints: item.complaints,
  }));
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} horizontal={false} />
        <XAxis type="number" tick={{ fontSize: 11, fill: AXIS }} axisLine={false} tickLine={false} allowDecimals={false} />
        <YAxis
          type="category"
          dataKey="name"
          width={128}
          tick={{ fontSize: 11, fill: AXIS }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip contentStyle={tooltipStyle} formatter={(value) => [`${value} complaints`, ""]} />
        <Bar dataKey="complaints" fill="#7c3aed" radius={[0, 6, 6, 0]} barSize={14} />
      </BarChart>
    </ResponsiveContainer>
  );
}
