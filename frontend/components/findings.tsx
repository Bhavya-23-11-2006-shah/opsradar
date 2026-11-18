"use client";

import Link from "next/link";
import { useState } from "react";
import {
  ArrowUpDown,
  Check,
  ChevronRight,
  Loader2,
  Plus,
  ShieldCheck,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  TriangleAlert,
  X,
} from "lucide-react";

import {
  ConfidenceBar,
  PriorityBadge,
  RiskMeter,
  SeverityBadge,
  StatusChip,
  TypeBadge,
  cn,
} from "@/components/ui";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/constants";
import { toast } from "@/lib/toast";
import type {
  ActionLog,
  Decision,
  EvidenceRow,
  Finding,
  Severity,
} from "@/types/contract";

type Entities = Finding["relatedEntities"];

const SEVERITY_ORDER: Record<Severity, number> = { critical: 4, high: 3, medium: 2, low: 1 };

type SortKey = "riskScore" | "title" | "severity" | "status" | "createdAt";

export function FindingsTable({ findings }: { findings: Finding[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("riskScore");
  const [ascending, setAscending] = useState(false);

  const sorted = [...findings].sort((a, b) => {
    let result = 0;
    switch (sortKey) {
      case "riskScore":
        result = a.riskScore - b.riskScore;
        break;
      case "severity":
        result = SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity];
        break;
      case "title":
        result = a.title.localeCompare(b.title);
        break;
      case "status":
        result = a.status.localeCompare(b.status);
        break;
      case "createdAt":
        result = a.createdAt.localeCompare(b.createdAt);
        break;
    }
    return ascending ? result : -result;
  });

  const header = (key: SortKey, label: string) => (
    <th scope="col" className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
      <button
        type="button"
        className="inline-flex items-center gap-1 hover:text-slate-900 dark:hover:text-slate-100"
        onClick={() => {
          if (sortKey === key) setAscending((value) => !value);
          else {
            setSortKey(key);
            setAscending(false);
          }
        }}
        aria-label={`Sort by ${label}`}
      >
        {label}
        <ArrowUpDown className={cn("h-3 w-3", sortKey === key ? "text-slate-900 dark:text-slate-100" : "opacity-40")} />
      </button>
    </th>
  );

  return (
    <div className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-100 text-sm dark:divide-slate-800">
          <thead className="bg-slate-50/80 dark:bg-slate-900/60">
            <tr>
              {header("title", "Finding")}
              <th scope="col" className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Type
              </th>
              {header("severity", "Severity")}
              {header("riskScore", "Risk")}
              {header("status", "Status")}
              <th scope="col" className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Evidence
              </th>
              <th scope="col" className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {sorted.map((finding) => (
              <tr key={finding.id} className="group transition hover:bg-slate-50/70 dark:hover:bg-slate-950/40">
                <td className="max-w-md px-4 py-3">
                  <Link href={`/findings/${finding.id}`} className="block">
                    <p className="line-clamp-2 font-medium group-hover:underline">{finding.title}</p>
                    <p className="mt-0.5 line-clamp-1 text-xs text-slate-500 dark:text-slate-400">{finding.summary}</p>
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <TypeBadge type={finding.type} />
                </td>
                <td className="px-4 py-3">
                  <SeverityBadge severity={finding.severity} />
                </td>
                <td className="px-4 py-3">
                  <RiskMeter score={finding.riskScore} severity={finding.severity} />
                </td>
                <td className="px-4 py-3">
                  <StatusChip status={finding.status} />
                </td>
                <td className="px-4 py-3 text-xs text-slate-500 dark:text-slate-400">
                  <span className="tabular-nums">{finding.verifiedFacts.length} facts</span>
                  <span className="mx-1">·</span>
                  <span className="tabular-nums">{finding.aiHypotheses.length} hypotheses</span>
                </td>
                <td className="px-4 py-3 text-right">
                  <Link
                    href={`/findings/${finding.id}`}
                    className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100"
                    aria-label={`Open ${finding.title}`}
                  >
                    Open
                    <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function FactsPanel({ facts }: { facts: Finding["verifiedFacts"] }) {
  return (
    <div className="space-y-3">
      {facts.map((fact, index) => (
        <div key={`${fact.metric}-${index}`} className="rounded-xl border border-teal-100 bg-teal-50/40 p-3 dark:border-teal-900/60 dark:bg-teal-950/20">
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <span className="chip bg-teal-100 text-verified dark:bg-teal-900/60 dark:text-teal-200">
              <ShieldCheck className="h-3 w-3" aria-hidden="true" />
              Verified Fact
            </span>
            <span className="font-mono text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400">
              {fact.metric}
            </span>
          </div>
          <p className="text-sm text-slate-700 dark:text-slate-200">{fact.statement}</p>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            value: <span className="font-medium">{String(fact.value)}</span>
          </p>
        </div>
      ))}
    </div>
  );
}

export function HypothesesPanel({ hypotheses }: { hypotheses: Finding["aiHypotheses"] }) {
  return (
    <div className="space-y-3">
      {hypotheses.map((hypothesis, index) => (
        <div key={index} className="rounded-xl border border-purple-100 bg-purple-50/40 p-3 dark:border-purple-900/60 dark:bg-purple-950/20">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className="chip bg-purple-100 text-ai dark:bg-purple-900/60 dark:text-purple-200">
              <Sparkles className="h-3 w-3" aria-hidden="true" />
              AI Hypothesis
            </span>
            <span className="text-[10px] font-medium uppercase tracking-wide text-ai">Unconfirmed, requires investigation</span>
          </div>
          <p className="text-sm text-slate-700 dark:text-slate-200">{hypothesis.statement}</p>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{hypothesis.reasoning}</p>
          <div className="mt-2 max-w-xs">
            <ConfidenceBar value={hypothesis.confidence} />
          </div>
        </div>
      ))}
    </div>
  );
}

export function RecommendationCard({ finding }: { finding: Finding }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Recommended action</h3>
        <PriorityBadge priority={finding.recommendation.priority} />
      </div>
      <p className="text-sm text-slate-700 dark:text-slate-200">{finding.recommendation.action}</p>
      <div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-950/60">
        <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">Why this recommendation</p>
        <p className="mt-1 text-xs leading-relaxed text-slate-600 dark:text-slate-300">{finding.recommendation.why}</p>
      </div>
      <div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-950/60">
        <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">Preventive control</p>
        <p className="mt-1 text-xs leading-relaxed text-slate-600 dark:text-slate-300">{finding.recommendation.preventive}</p>
      </div>
    </div>
  );
}

export function EvidenceTable({ rows }: { rows: EvidenceRow[] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
      <table className="min-w-full divide-y divide-slate-100 text-sm dark:divide-slate-800">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500 dark:bg-slate-900 dark:text-slate-400">
          <tr>
            <th scope="col" className="px-4 py-2 text-left font-medium">Source</th>
            <th scope="col" className="px-4 py-2 text-left font-medium">Row ID</th>
            <th scope="col" className="px-4 py-2 text-left font-medium">Fields</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {rows.map((row, index) => (
            <tr key={`${row.rowId}-${index}`} className="align-top">
              <td className="whitespace-nowrap px-4 py-3">
                <span className="chip bg-slate-100 font-mono text-[10px] text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                  {row.source}
                </span>
              </td>
              <td className="whitespace-nowrap px-4 py-3 font-mono text-[11px] text-slate-500 dark:text-slate-400">{row.rowId}</td>
              <td className="px-4 py-3">
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(row.fields)
                    .filter(([, value]) => value !== null && value !== "")
                    .map(([key, value]) => (
                      <span
                        key={key}
                        className="inline-flex max-w-[280px] items-baseline gap-1 rounded-md bg-slate-50 px-1.5 py-0.5 text-[11px] text-slate-600 dark:bg-slate-950 dark:text-slate-300"
                        title={`${key}: ${String(value)}`}
                      >
                        <span className="font-mono text-[10px] text-slate-400">{key}</span>
                        <span className="truncate">{String(value).slice(0, 80)}</span>
                      </span>
                    ))}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const NODE_COLORS: Record<string, string> = {
  center: "#0f172a",
  product: "#0d9488",
  courier: "#ea580c",
  location: "#2563eb",
  evidence: "#7c3aed",
};

export function RelationshipGraph({
  entities,
  evidenceCount,
  severity,
}: {
  entities: Entities;
  evidenceCount: number;
  severity: Severity;
}) {
  const satellites = [
    ...entities.products.slice(0, 3).map((label) => ({ label, kind: "product" as const })),
    ...entities.couriers.slice(0, 2).map((label) => ({ label, kind: "courier" as const })),
    ...entities.locations.slice(0, 3).map((label) => ({ label, kind: "location" as const })),
  ];
  const nodes = [...satellites, { label: `${evidenceCount} evidence rows`, kind: "evidence" as const }];

  const width = 720;
  const height = 300;
  const centerX = width / 2;
  const centerY = height / 2;
  const radiusX = 250;
  const radiusY = 105;

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Relationship graph between the finding, its entities and evidence" className="min-w-[620px]">
        {nodes.map((node, index) => {
          const angle = (Math.PI * 2 * index) / Math.max(nodes.length, 1) - Math.PI / 2;
          const x = centerX + Math.cos(angle) * radiusX;
          const y = centerY + Math.sin(angle) * radiusY;
          return (
            <g key={`${node.kind}-${node.label}`}>
              <line x1={centerX} y1={centerY} x2={x} y2={y} stroke="#cbd5e1" strokeWidth={1.2} strokeDasharray="4 4" />
              <circle cx={x} cy={y} r={26} fill={NODE_COLORS[node.kind]} opacity={0.12} />
              <circle cx={x} cy={y} r={4} fill={NODE_COLORS[node.kind]} />
              <text
                x={x}
                y={y + 40}
                textAnchor="middle"
                fontSize={10}
                fill="currentColor"
                className="fill-slate-600 dark:fill-slate-300"
              >
                {node.label.length > 20 ? `${node.label.slice(0, 18)}…` : node.label}
              </text>
            </g>
          );
        })}
        <circle cx={centerX} cy={centerY} r={38} fill={NODE_COLORS.center} />
        <text x={centerX} y={centerY - 2} textAnchor="middle" fontSize={11} fill="#ffffff" fontWeight={600}>
          Risk
        </text>
        <text x={centerX} y={centerY + 12} textAnchor="middle" fontSize={9} fill="#cbd5e1">
          {severity}
        </text>
      </svg>
      <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-slate-500 dark:text-slate-400">
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-verified" /> product</span>
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-high" /> courier</span>
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-blue-600" /> location</span>
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-ai" /> evidence</span>
      </div>
    </div>
  );
}

export function EntityChips({ entities }: { entities: Entities }) {
  const groups = [
    { label: "Products", values: entities.products },
    { label: "Locations", values: entities.locations },
    { label: "Couriers", values: entities.couriers },
    { label: "Orders", values: entities.orders },
  ];
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {groups.map((group) => (
        <div key={group.label}>
          <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">{group.label}</p>
          <div className="flex flex-wrap gap-1.5">
            {group.values.length === 0 ? (
              <span className="text-xs text-slate-400">—</span>
            ) : (
              group.values.map((value) => (
                <span key={value} className="chip bg-slate-100 font-mono text-[10px] text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                  {value}
                </span>
              ))
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

export function DecisionBar({
  datasetId,
  finding,
  onUpdated,
  onActionsChanged,
}: {
  datasetId: string;
  finding: Finding;
  onUpdated: (finding: Finding) => void;
  onActionsChanged: () => void;
}) {
  const [note, setNote] = useState("");
  const [pending, setPending] = useState<Decision | null>(null);
  const [taskTitle, setTaskTitle] = useState("");
  const [creatingTask, setCreatingTask] = useState(false);

  const decide = async (decision: Decision) => {
    setPending(decision);
    try {
      const updated = await api.decide(datasetId, finding.id, { decision, note: note.trim() });
      onUpdated(updated);
      setNote("");
      toast(
        decision === "approve"
          ? "Approved — moved to investigating"
          : decision === "reject"
            ? "Rejected"
            : "Escalated",
        "success",
      );
      onActionsChanged();
    } catch (error) {
      toast(error instanceof Error ? error.message : "Decision failed", "error");
    } finally {
      setPending(null);
    }
  };

  const createTask = async () => {
    if (!taskTitle.trim()) return;
    setCreatingTask(true);
    try {
      await api.createTask(datasetId, finding.id, { title: taskTitle.trim() });
      setTaskTitle("");
      toast("Investigation task created", "success");
      onActionsChanged();
    } catch (error) {
      toast(error instanceof Error ? error.message : "Could not create task", "error");
    } finally {
      setCreatingTask(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <label htmlFor="decision-note" className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-300">
          Decision note
        </label>
        <textarea
          id="decision-note"
          rows={2}
          className="field resize-none"
          placeholder="What did you decide, and why?"
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
      </div>

      <div className="grid grid-cols-3 gap-2">
        <button
          type="button"
          className="btn-primary bg-teal-700 hover:bg-teal-800 dark:bg-teal-500 dark:text-white dark:hover:bg-teal-400"
          onClick={() => void decide("approve")}
          disabled={pending !== null}
        >
          {pending === "approve" ? <Loader2 className="h-4 w-4 animate-spin" /> : <ThumbsUp className="h-4 w-4" />}
          Approve
        </button>
        <button
          type="button"
          className="btn-secondary"
          onClick={() => void decide("reject")}
          disabled={pending !== null}
        >
          {pending === "reject" ? <Loader2 className="h-4 w-4 animate-spin" /> : <ThumbsDown className="h-4 w-4" />}
          Reject
        </button>
        <button
          type="button"
          className="btn-secondary"
          onClick={() => void decide("escalate")}
          disabled={pending !== null}
        >
          {pending === "escalate" ? <Loader2 className="h-4 w-4 animate-spin" /> : <TriangleAlert className="h-4 w-4" />}
          Escalate
        </button>
      </div>

      <div className="rounded-xl border border-slate-200 p-3 dark:border-slate-800">
        <p className="mb-2 flex items-center gap-1.5 text-xs font-medium">
          <Plus className="h-3.5 w-3.5" aria-hidden="true" />
          Create investigation task
        </p>
        <div className="flex gap-2">
          <input
            className="field"
            placeholder="e.g. Call the carrier about missed promises"
            value={taskTitle}
            onChange={(event) => setTaskTitle(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void createTask();
            }}
            aria-label="Investigation task title"
          />
          <button type="button" className="btn-secondary shrink-0" onClick={() => void createTask()} disabled={creatingTask || !taskTitle.trim()}>
            {creatingTask ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
            Add
          </button>
        </div>
      </div>

      <p className="text-[11px] text-slate-500 dark:text-slate-400">
        Approve moves the finding to investigating, reject closes it as rejected, escalate raises it for a decision.
      </p>
    </div>
  );
}

export function ActionsMini({ logs }: { logs: ActionLog[] }) {
  const label: Record<string, string> = {
    approve: "Approved",
    reject: "Rejected",
    escalate: "Escalated",
    task_created: "Task created",
    status_changed: "Status changed",
  };
  if (logs.length === 0) {
    return <p className="text-xs text-slate-500 dark:text-slate-400">No actions yet for this finding.</p>;
  }
  return (
    <ul className="space-y-2">
      {logs.map((log) => (
        <li key={log.id} className="rounded-lg border border-slate-200 px-3 py-2 text-xs dark:border-slate-800">
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium">{label[log.decision] ?? log.decision}</span>
            <span className="text-[10px] text-slate-400">{formatDateTime(log.at)}</span>
          </div>
          {log.note ? <p className="mt-1 text-slate-500 dark:text-slate-400">{log.note}</p> : null}
          <p className="mt-1 text-[10px] text-slate-400">by {log.actor}</p>
        </li>
      ))}
    </ul>
  );
}

export function DecisionIcon({ decision }: { decision: Decision }) {
  if (decision === "approve") return <ThumbsUp className="h-3.5 w-3.5" />;
  if (decision === "reject") return <X className="h-3.5 w-3.5" />;
  return <TriangleAlert className="h-3.5 w-3.5" />;
}
