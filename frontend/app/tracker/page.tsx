"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type DragEvent } from "react";
import { Download, GripVertical, History, ListChecks, Search } from "lucide-react";

import {
  EmptyState,
  ErrorState,
  NoDataset,
  PageHeader,
  RiskMeter,
  SectionTitle,
  SeverityBadge,
  Skeleton,
  StatusChip,
  cn,
  useMounted,
} from "@/components/ui";
import { api } from "@/lib/api";
import { KANBAN_COLUMNS, formatDateTime } from "@/lib/constants";
import { toast } from "@/lib/toast";
import { useAppStore } from "@/store/useAppStore";
import type { ActionsResponse, ActionLog, Finding, Status } from "@/types/contract";

const DECISION_LABELS: Record<ActionLog["decision"], string> = {
  approve: "Approve",
  reject: "Reject",
  escalate: "Escalate",
  task_created: "Task created",
  status_changed: "Status changed",
};

function escapeCsv(value: string): string {
  return `"${value.replace(/"/g, '""')}"`;
}

export default function TrackerPage() {
  const mounted = useMounted();
  const datasetId = useAppStore((state) => state.datasetId);
  const upsertFinding = useAppStore((state) => state.upsertFinding);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [actions, setActions] = useState<ActionsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dragId, setDragId] = useState<string | null>(null);
  const [showRejected, setShowRejected] = useState(false);
  const [logFilter, setLogFilter] = useState<"all" | ActionLog["decision"]>("all");
  const [logSearch, setLogSearch] = useState("");

  const load = useCallback(async () => {
    if (!datasetId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [list, response] = await Promise.all([
        api.findings(datasetId),
        api.actions(datasetId),
      ]);
      setFindings(list);
      setActions(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [datasetId]);

  useEffect(() => {
    if (!mounted) return;
    void load();
  }, [mounted, load]);

  const move = async (findingId: string, status: Status) => {
    if (!datasetId) return;
    const previous = findings;
    setFindings((items) => items.map((item) => (item.id === findingId ? { ...item, status } : item)));
    try {
      const updated = await api.patchStatus(datasetId, findingId, { status });
      upsertFinding(updated);
      toast(`Moved to ${status}`, "success");
      await load();
    } catch (err) {
      setFindings(previous);
      toast(err instanceof Error ? err.message : "Could not move the finding", "error");
    }
  };

  const onDrop = (event: DragEvent<HTMLDivElement>, status: Status) => {
    event.preventDefault();
    const id = event.dataTransfer.getData("text/plain") || dragId;
    setDragId(null);
    if (id) void move(id, status);
  };

  const logs = useMemo(() => {
    const source = actions?.log ?? [];
    const needle = logSearch.trim().toLowerCase();
    return source.filter((log) => {
      if (logFilter !== "all" && log.decision !== logFilter) return false;
      if (!needle) return true;
      return `${log.findingTitle} ${log.note} ${log.actor} ${log.decision}`.toLowerCase().includes(needle);
    });
  }, [actions?.log, logFilter, logSearch]);

  const exportCsv = () => {
    const header = ["at", "finding", "decision", "note", "actor"];
    const rows = logs.map((log) => [
      log.at,
      log.findingTitle,
      DECISION_LABELS[log.decision],
      log.note,
      log.actor,
    ]);
    const csv = [header, ...rows].map((row) => row.map(escapeCsv).join(",")).join("\r\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "opsradar-action-history.csv";
    anchor.click();
    URL.revokeObjectURL(url);
    toast("Action history exported", "success");
  };

  if (!mounted) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-9 w-56" />
        <div className="grid gap-4 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-64" />
          ))}
        </div>
      </div>
    );
  }

  if (!datasetId) {
    return (
      <div>
        <PageHeader title="Action Tracker" description="Move findings through investigation and keep a full decision history." />
        <NoDataset />
      </div>
    );
  }

  const rejected = findings.filter((finding) => finding.status === "rejected");
  const tasks = actions?.tasks ?? [];

  return (
    <div className="space-y-5">
      <PageHeader
        title="Action Tracker"
        description="Drag findings between columns to change status. Every move is written to the decision history."
        actions={
          <button type="button" className="btn-secondary" onClick={() => void load()}>
            Refresh
          </button>
        }
      />

      {error ? (
        <ErrorState message={error} onRetry={() => void load()} />
      ) : loading ? (
        <div className="grid gap-4 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-64" />
          ))}
        </div>
      ) : findings.length === 0 ? (
        <EmptyState
          icon={ListChecks}
          title="No findings to track"
          description="Run the analysis first, then move findings through the board."
        />
      ) : (
        <>
          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {KANBAN_COLUMNS.map((column) => {
              const items = findings.filter((finding) => finding.status === column.status);
              return (
                <div
                  key={column.status}
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={(event) => onDrop(event, column.status)}
                  className="card flex min-h-[260px] flex-col p-3"
                  aria-label={`${column.label} column`}
                >
                  <div className="mb-2 flex items-center justify-between px-1">
                    <h2 className="text-sm font-semibold">{column.label}</h2>
                    <span className="chip bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                      {items.length}
                    </span>
                  </div>
                  <div className="flex-1 space-y-2">
                    {items.map((finding) => (
                      <article
                        key={finding.id}
                        draggable
                        onDragStart={(event) => {
                          event.dataTransfer.setData("text/plain", finding.id);
                          setDragId(finding.id);
                        }}
                        onDragEnd={() => setDragId(null)}
                        className={cn(
                          "cursor-grab rounded-xl border border-slate-200 bg-white p-3 shadow-sm transition active:cursor-grabbing dark:border-slate-800 dark:bg-slate-950",
                          dragId === finding.id && "opacity-50",
                        )}
                      >
                        <div className="mb-1 flex items-start gap-1">
                          <GripVertical className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-300" aria-hidden="true" />
                          <Link href={`/findings/${finding.id}`} className="line-clamp-2 text-xs font-medium hover:underline">
                            {finding.title}
                          </Link>
                        </div>
                        <div className="mt-2 flex items-center justify-between gap-2">
                          <SeverityBadge severity={finding.severity} />
                          <StatusChip status={finding.status} />
                        </div>
                        <div className="mt-2">
                          <RiskMeter score={finding.riskScore} severity={finding.severity} />
                        </div>
                      </article>
                    ))}
                    {items.length === 0 ? (
                      <p className="rounded-xl border border-dashed border-slate-200 px-3 py-6 text-center text-[11px] text-slate-400 dark:border-slate-800">
                        Drop a finding here
                      </p>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </section>

          <section className="card card-pad">
            <button
              type="button"
              className="flex w-full items-center justify-between text-left"
              aria-expanded={showRejected}
              onClick={() => setShowRejected((value) => !value)}
            >
              <span className="text-sm font-semibold">
                Rejected <span className="ml-1 text-xs font-normal text-slate-500">({rejected.length})</span>
              </span>
              <span className="text-xs text-slate-500">{showRejected ? "Hide" : "Show"}</span>
            </button>
            {showRejected ? (
              <ul className="mt-3 flex flex-wrap gap-2">
                {rejected.length === 0 ? (
                  <li className="text-xs text-slate-500 dark:text-slate-400">Nothing rejected.</li>
                ) : (
                  rejected.map((finding) => (
                    <li key={finding.id}>
                      <Link
                        href={`/findings/${finding.id}`}
                        className="chip border border-slate-200 text-slate-500 line-through dark:border-slate-800"
                      >
                        {finding.title}
                      </Link>
                    </li>
                  ))
                )}
              </ul>
            ) : null}
          </section>

          <section className="card card-pad space-y-4">
            <SectionTitle
              title="Decision history"
              hint="Every approve, reject, escalate, status change and task."
              right={
                <button type="button" className="btn-secondary py-1.5 text-xs" onClick={exportCsv}>
                  <Download className="h-3.5 w-3.5" aria-hidden="true" />
                  Export CSV
                </button>
              }
            />
            <div className="flex flex-col gap-2 sm:flex-row">
              <label className="relative flex-1 text-xs text-slate-500 dark:text-slate-400">
                Search
                <span className="pointer-events-none absolute left-3 top-[30px] text-slate-400">
                  <Search className="h-4 w-4" aria-hidden="true" />
                </span>
                <input
                  className="field mt-1 pl-9"
                  placeholder="Finding, note or actor…"
                  value={logSearch}
                  onChange={(event) => setLogSearch(event.target.value)}
                />
              </label>
              <label className="text-xs text-slate-500 dark:text-slate-400 sm:w-48">
                Decision
                <select
                  className="field mt-1"
                  value={logFilter}
                  onChange={(event) => setLogFilter(event.target.value as typeof logFilter)}
                >
                  <option value="all">All decisions</option>
                  <option value="approve">Approve</option>
                  <option value="reject">Reject</option>
                  <option value="escalate">Escalate</option>
                  <option value="status_changed">Status changed</option>
                  <option value="task_created">Task created</option>
                </select>
              </label>
            </div>

            <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
              <table className="min-w-full divide-y divide-slate-100 text-sm dark:divide-slate-800">
                <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                  <tr>
                    <th scope="col" className="px-4 py-2 text-left font-medium">When</th>
                    <th scope="col" className="px-4 py-2 text-left font-medium">Finding</th>
                    <th scope="col" className="px-4 py-2 text-left font-medium">Decision</th>
                    <th scope="col" className="px-4 py-2 text-left font-medium">Note</th>
                    <th scope="col" className="px-4 py-2 text-left font-medium">Actor</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {logs.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-4 py-8 text-center text-xs text-slate-500 dark:text-slate-400">
                        No actions recorded{logSearch || logFilter !== "all" ? " for this filter" : " yet"}.
                      </td>
                    </tr>
                  ) : (
                    logs.map((log) => (
                      <tr key={log.id}>
                        <td className="whitespace-nowrap px-4 py-2 text-xs text-slate-500 dark:text-slate-400">
                          {formatDateTime(log.at)}
                        </td>
                        <td className="max-w-xs px-4 py-2">
                          <Link href={`/findings/${log.findingId}`} className="line-clamp-1 text-xs hover:underline">
                            {log.findingTitle}
                          </Link>
                        </td>
                        <td className="px-4 py-2">
                          <span className="chip bg-slate-100 text-[10px] text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                            {DECISION_LABELS[log.decision]}
                          </span>
                        </td>
                        <td className="max-w-xs px-4 py-2 text-xs text-slate-600 dark:text-slate-300">{log.note}</td>
                        <td className="px-4 py-2 text-xs text-slate-500 dark:text-slate-400">{log.actor}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section className="card card-pad">
            <SectionTitle title="Investigation tasks" hint="Created from a finding with a concrete title." />
            {tasks.length === 0 ? (
              <p className="text-sm text-slate-500 dark:text-slate-400">No tasks yet. Create one from any finding.</p>
            ) : (
              <ul className="divide-y divide-slate-100 dark:divide-slate-800">
                {tasks.map((task) => (
                  <li key={task.id} className="flex flex-col gap-1 py-3 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <p className="text-sm font-medium">{task.title}</p>
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        <Link href={`/findings/${task.findingId}`} className="hover:underline">
                          {task.findingId}
                        </Link>
                        {" · "}
                        {formatDateTime(task.createdAt)}
                      </p>
                    </div>
                    <StatusChip status={task.status} />
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}
