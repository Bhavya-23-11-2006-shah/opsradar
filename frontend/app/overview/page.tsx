"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowUpRight,
  Boxes,
  Filter,
  Flame,
  RotateCcw,
  ShieldAlert,
  Truck,
} from "lucide-react";

import { CategoryChart, ProductsChart, RiskDistributionChart, TrendChart } from "@/components/charts";
import {
  CardsSkeleton,
  EmptyState,
  ErrorState,
  NoDataset,
  PageHeader,
  RiskMeter,
  SectionTitle,
  SeverityBadge,
  Skeleton,
  StatusChip,
  TypeBadge,
  cn,
  useCountUp,
  useMounted,
} from "@/components/ui";
import { api } from "@/lib/api";
import { toast } from "@/lib/toast";
import { useAppStore } from "@/store/useAppStore";
import type { Finding, OverviewFilters, OverviewResponse } from "@/types/contract";

type Group = "courier" | "warehouse" | "city";

function KpiCard({
  label,
  value,
  hint,
  icon: Icon,
  tone,
}: {
  label: string;
  value: number;
  hint: string;
  icon: typeof Flame;
  tone: string;
}) {
  const display = useCountUp(value);
  return (
    <div className="card card-pad animate-fade-up">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</p>
          <p className="mt-2 text-3xl font-semibold tabular-nums">{display}</p>
          <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">{hint}</p>
        </div>
        <span className={cn("flex h-9 w-9 items-center justify-center rounded-xl", tone)}>
          <Icon className="h-4 w-4" aria-hidden="true" />
        </span>
      </div>
    </div>
  );
}

export default function OverviewPage() {
  const mounted = useMounted();
  const datasetId = useAppStore((state) => state.datasetId);
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [filters, setFilters] = useState<OverviewFilters>({});
  const [group, setGroup] = useState<Group>("courier");
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
      const response = await api.overview(datasetId, filters);
      setOverview(response);
      if (findings.length === 0) {
        const list = await api.findings(datasetId);
        setFindings(list);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [datasetId, filters, findings.length]);

  useEffect(() => {
    if (!mounted) return;
    const timer = window.setTimeout(() => {
      void load();
    }, 200);
    return () => window.clearTimeout(timer);
  }, [mounted, load]);

  if (!mounted) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-9 w-56" />
        <CardsSkeleton />
      </div>
    );
  }

  if (!datasetId) {
    return (
      <div>
        <PageHeader title="Overview" description="Portfolio-level early warning signals from your operational data." />
        <NoDataset />
      </div>
    );
  }

  const emerging = [...findings].sort((a, b) => b.riskScore - a.riskScore).slice(0, 5);
  const groupData = overview?.riskDistribution.filter((item) => item.group === group) ?? [];
  const empty = overview && overview.trends.length === 0 && overview.categoryBreakdown.length === 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Overview"
        description="Portfolio-level early warning signals. Everything on this page comes from the analysed dataset."
        actions={
          <>
            <Link href="/findings" className="btn-secondary">
              All findings
              <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
            </Link>
            <button type="button" className="btn-ghost" onClick={() => void load()}>
              Refresh
            </button>
          </>
        }
      />

      <section className="card card-pad">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Filter className="h-4 w-4 text-slate-400" aria-hidden="true" />
            Filters
          </div>
          <div className="grid flex-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <label className="text-xs text-slate-500 dark:text-slate-400">
              From
              <input
                type="date"
                className="field mt-1"
                value={filters.from ?? ""}
                min={overview?.filters.dateMin ?? undefined}
                max={filters.to ?? overview?.filters.dateMax ?? undefined}
                onChange={(event) => setFilters((prev) => ({ ...prev, from: event.target.value || undefined }))}
              />
            </label>
            <label className="text-xs text-slate-500 dark:text-slate-400">
              To
              <input
                type="date"
                className="field mt-1"
                value={filters.to ?? ""}
                min={filters.from ?? overview?.filters.dateMin ?? undefined}
                max={overview?.filters.dateMax ?? undefined}
                onChange={(event) => setFilters((prev) => ({ ...prev, to: event.target.value || undefined }))}
              />
            </label>
            <label className="text-xs text-slate-500 dark:text-slate-400">
              Product
              <select
                className="field mt-1"
                value={filters.product ?? ""}
                onChange={(event) => setFilters((prev) => ({ ...prev, product: event.target.value || undefined }))}
              >
                <option value="">All products</option>
                {overview?.filters.products.map((product) => (
                  <option key={product} value={product}>
                    {product}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs text-slate-500 dark:text-slate-400">
              Location
              <select
                className="field mt-1"
                value={filters.location ?? ""}
                onChange={(event) => setFilters((prev) => ({ ...prev, location: event.target.value || undefined }))}
              >
                <option value="">All locations</option>
                {overview?.filters.locations.map((location) => (
                  <option key={location} value={location}>
                    {location}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs text-slate-500 dark:text-slate-400">
              Courier
              <select
                className="field mt-1"
                value={filters.courier ?? ""}
                onChange={(event) => setFilters((prev) => ({ ...prev, courier: event.target.value || undefined }))}
              >
                <option value="">All couriers</option>
                {overview?.filters.couriers.map((courier) => (
                  <option key={courier} value={courier}>
                    {courier}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <button
            type="button"
            className="btn-ghost w-fit"
            onClick={() => {
              setFilters({});
              toast("Filters cleared", "info");
            }}
          >
            <RotateCcw className="h-4 w-4" aria-hidden="true" />
            Reset
          </button>
        </div>
      </section>

      {error ? (
        <ErrorState message={error} onRetry={() => void load()} />
      ) : loading && !overview ? (
        <>
          <CardsSkeleton />
          <div className="grid gap-4 xl:grid-cols-3">
            <div className="card card-pad xl:col-span-2">
              <Skeleton className="h-64 w-full" />
            </div>
            <div className="card card-pad">
              <Skeleton className="h-64 w-full" />
            </div>
          </div>
        </>
      ) : empty ? (
        <EmptyState
          icon={AlertTriangle}
          title="No signals in this range"
          description="Try widening the date range or clearing filters. You can also rerun the analysis from the upload screen."
          action={
            <Link href="/" className="btn-primary">
              Go to upload
            </Link>
          }
        />
      ) : (
        <>
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <KpiCard
              label="Open issues"
              value={overview?.kpis.openIssues ?? 0}
              hint="Findings still open or in progress"
              icon={AlertTriangle}
              tone="bg-amber-50 text-medium dark:bg-amber-950/40 dark:text-amber-300"
            />
            <KpiCard
              label="Critical risks"
              value={overview?.kpis.criticalRisks ?? 0}
              hint="Risk score 80 or above"
              icon={ShieldAlert}
              tone="bg-red-50 text-critical dark:bg-red-950/40 dark:text-red-300"
            />
            <KpiCard
              label="Orders at risk"
              value={overview?.kpis.ordersAtRisk ?? 0}
              hint="Likely to miss their promise"
              icon={Truck}
              tone="bg-orange-50 text-high dark:bg-orange-950/40 dark:text-orange-300"
            />
            <KpiCard
              label="Near stockout"
              value={overview?.kpis.productsNearStockout ?? 0}
              hint="Seven days of cover or less"
              icon={Boxes}
              tone="bg-purple-50 text-ai dark:bg-purple-950/40 dark:text-purple-300"
            />
            <KpiCard
              label="Complaint spikes"
              value={overview?.kpis.complaintSpikes ?? 0}
              hint="Emerging complaint clusters"
              icon={Flame}
              tone="bg-teal-50 text-verified dark:bg-teal-950/40 dark:text-teal-300"
            />
          </section>

          <section className="grid gap-4 xl:grid-cols-3">
            <div className="card card-pad xl:col-span-2">
              <SectionTitle
                title="Complaints over time"
                hint="Red points are statistically anomalous weeks."
                right={
                  <span className="chip bg-red-50 text-critical dark:bg-red-950/40 dark:text-red-300">
                    Anomaly
                  </span>
                }
              />
              {overview ? <TrendChart data={overview.trends} /> : <Skeleton className="h-64 w-full" />}
            </div>
            <div className="card card-pad">
              <SectionTitle title="Emerging risks" hint="Highest risk scores first." />
              <ul className="space-y-3">
                {emerging.length === 0 ? (
                  <li className="text-sm text-slate-500 dark:text-slate-400">No open findings yet.</li>
                ) : (
                  emerging.map((finding) => (
                    <li key={finding.id}>
                      <Link
                        href={`/findings/${finding.id}`}
                        className="block rounded-xl border border-slate-200 p-3 transition hover:border-slate-300 hover:bg-slate-50 dark:border-slate-800 dark:hover:border-slate-700 dark:hover:bg-slate-950"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <p className="line-clamp-2 text-sm font-medium">{finding.title}</p>
                          <SeverityBadge severity={finding.severity} />
                        </div>
                        <div className="mt-2 flex items-center justify-between gap-2">
                          <RiskMeter score={finding.riskScore} severity={finding.severity} />
                          <StatusChip status={finding.status} />
                        </div>
                      </Link>
                    </li>
                  ))
                )}
              </ul>
            </div>
          </section>

          <section className="grid gap-4 xl:grid-cols-2">
            <div className="card card-pad">
              <SectionTitle title="Complaint categories" hint="Categorised from free-text complaints." />
              {overview ? <CategoryChart data={overview.categoryBreakdown} /> : <Skeleton className="h-64 w-full" />}
            </div>
            <div className="card card-pad">
              <SectionTitle
                title="Risk by shared factor"
                hint="Complaint concentration blended with delivery exposure."
                right={
                  <div className="flex gap-1 rounded-lg bg-slate-100 p-1 dark:bg-slate-800">
                    {(["courier", "warehouse", "city"] as Group[]).map((option) => (
                      <button
                        key={option}
                        type="button"
                        onClick={() => setGroup(option)}
                        aria-pressed={group === option}
                        className={cn(
                          "rounded-md px-2.5 py-1 text-[11px] font-medium capitalize transition",
                          group === option
                            ? "bg-white text-slate-900 shadow-sm dark:bg-slate-950 dark:text-slate-100"
                            : "text-slate-500 dark:text-slate-400",
                        )}
                      >
                        {option}
                      </button>
                    ))}
                  </div>
                }
              />
              {overview ? (
                groupData.length ? (
                  <RiskDistributionChart data={groupData} />
                ) : (
                  <p className="py-16 text-center text-sm text-slate-500 dark:text-slate-400">
                    No {group} signals in this range.
                  </p>
                )
              ) : (
                <Skeleton className="h-64 w-full" />
              )}
            </div>
          </section>

          <section className="card card-pad">
            <SectionTitle title="Top problem products" hint="Products with the most complaints in range." />
            {overview && overview.topProblemProducts.length ? (
              <ProductsChart data={overview.topProblemProducts} />
            ) : (
              <p className="py-10 text-center text-sm text-slate-500 dark:text-slate-400">
                No product complaints in this range.
              </p>
            )}
          </section>
        </>
      )}
    </div>
  );
}
