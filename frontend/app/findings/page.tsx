"use client";

import { useCallback, useEffect, useState } from "react";
import { Search, SlidersHorizontal } from "lucide-react";

import { FindingsTable } from "@/components/findings";
import {
  EmptyState,
  ErrorState,
  NoDataset,
  PageHeader,
  Skeleton,
  useMounted,
} from "@/components/ui";
import { api } from "@/lib/api";
import { useAppStore } from "@/store/useAppStore";
import type { Finding, FindingsFilters } from "@/types/contract";

const EMPTY_FILTERS: FindingsFilters = { type: "", severity: "", status: "", search: "" };

export default function FindingsPage() {
  const mounted = useMounted();
  const datasetId = useAppStore((state) => state.datasetId);
  const [filters, setFilters] = useState<FindingsFilters>(EMPTY_FILTERS);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!datasetId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const list = await api.findings(datasetId, filters);
      setFindings(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [datasetId, filters]);

  useEffect(() => {
    if (!mounted) return;
    const timer = window.setTimeout(() => {
      void load();
    }, 250);
    return () => window.clearTimeout(timer);
  }, [mounted, load]);

  if (!mounted) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-9 w-48" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-80 w-full" />
      </div>
    );
  }

  if (!datasetId) {
    return (
      <div>
        <PageHeader title="Findings" description="Evidence-backed operational risks detected in your data." />
        <NoDataset />
      </div>
    );
  }

  const activeFilters = Boolean(filters.type || filters.severity || filters.status || filters.search);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Findings"
        description="Every finding separates what the deterministic engine verified from what the AI suspects."
        actions={
          <span className="chip bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
            {findings.length} results
          </span>
        }
      />

      <section className="card card-pad">
        <div className="flex items-center gap-2 text-sm font-medium">
          <SlidersHorizontal className="h-4 w-4 text-slate-400" aria-hidden="true" />
          Filters
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <label className="relative text-xs text-slate-500 dark:text-slate-400 xl:col-span-2">
            Search
            <span className="pointer-events-none absolute left-3 top-[30px] text-slate-400">
              <Search className="h-4 w-4" aria-hidden="true" />
            </span>
            <input
              className="field mt-1 pl-9"
              placeholder="Title, product, courier, order id…"
              value={filters.search}
              onChange={(event) => setFilters((prev) => ({ ...prev, search: event.target.value }))}
            />
          </label>
          <label className="text-xs text-slate-500 dark:text-slate-400">
            Type
            <select
              className="field mt-1"
              value={filters.type}
              onChange={(event) => setFilters((prev) => ({ ...prev, type: event.target.value as FindingsFilters["type"] }))}
            >
              <option value="">All types</option>
              <option value="recurring_issue">Recurring issue</option>
              <option value="complaint_spike">Complaint spike</option>
              <option value="delivery_risk">Delivery risk</option>
              <option value="inventory_risk">Inventory risk</option>
              <option value="anomaly">Anomaly</option>
            </select>
          </label>
          <label className="text-xs text-slate-500 dark:text-slate-400">
            Severity
            <select
              className="field mt-1"
              value={filters.severity}
              onChange={(event) => setFilters((prev) => ({ ...prev, severity: event.target.value as FindingsFilters["severity"] }))}
            >
              <option value="">All severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </label>
          <label className="text-xs text-slate-500 dark:text-slate-400">
            Status
            <select
              className="field mt-1"
              value={filters.status}
              onChange={(event) => setFilters((prev) => ({ ...prev, status: event.target.value as FindingsFilters["status"] }))}
            >
              <option value="">All statuses</option>
              <option value="open">Open</option>
              <option value="investigating">Investigating</option>
              <option value="escalated">Escalated</option>
              <option value="resolved">Resolved</option>
              <option value="rejected">Rejected</option>
            </select>
          </label>
        </div>
        {activeFilters ? (
          <button type="button" className="btn-ghost mt-3 py-1.5 text-xs" onClick={() => setFilters(EMPTY_FILTERS)}>
            Clear filters
          </button>
        ) : null}
      </section>

      {error ? (
        <ErrorState message={error} onRetry={() => void load()} />
      ) : loading ? (
        <div className="card card-pad space-y-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-12 w-full" />
          ))}
        </div>
      ) : findings.length === 0 ? (
        <EmptyState
          title={activeFilters ? "No findings match these filters" : "No findings yet"}
          description={
            activeFilters
              ? "Try a different search or clear the filters."
              : "Run the analysis from the upload screen to generate findings."
          }
          action={
            activeFilters ? (
              <button type="button" className="btn-secondary" onClick={() => setFilters(EMPTY_FILTERS)}>
                Clear filters
              </button>
            ) : null
          }
        />
      ) : (
        <FindingsTable findings={findings} />
      )}
    </div>
  );
}
