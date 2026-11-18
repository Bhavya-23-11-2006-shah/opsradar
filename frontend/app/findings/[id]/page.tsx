"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, GitBranch, ListChecks } from "lucide-react";

import {
  ActionsMini,
  DecisionBar,
  EntityChips,
  EvidenceTable,
  FactsPanel,
  HypothesesPanel,
  RecommendationCard,
  RelationshipGraph,
} from "@/components/findings";
import {
  ErrorState,
  PageHeader,
  RiskGauge,
  SectionTitle,
  SeverityBadge,
  Skeleton,
  StatusChip,
  TypeBadge,
  useMounted,
} from "@/components/ui";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/constants";
import { useAppStore } from "@/store/useAppStore";
import type { ActionsResponse, Finding } from "@/types/contract";

export default function FindingDetailPage() {
  const mounted = useMounted();
  const params = useParams<{ id: string }>();
  const findingId = params?.id;
  const datasetId = useAppStore((state) => state.datasetId);
  const upsertFinding = useAppStore((state) => state.upsertFinding);
  const [finding, setFinding] = useState<Finding | null>(null);
  const [actions, setActions] = useState<ActionsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadActions = useCallback(async () => {
    if (!datasetId) return;
    try {
      const response = await api.actions(datasetId);
      setActions(response);
    } catch {
      setActions(null);
    }
  }, [datasetId]);

  const load = useCallback(async () => {
    if (!datasetId || !findingId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const detail = await api.finding(datasetId, findingId);
      setFinding(detail);
      upsertFinding(detail);
      await loadActions();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [datasetId, findingId, loadActions, upsertFinding]);

  useEffect(() => {
    if (!mounted) return;
    void load();
  }, [mounted, load]);

  if (!mounted) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-9 w-72" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <Link href="/findings" className="btn-ghost w-fit">
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back to findings
        </Link>
        <ErrorState message={error} onRetry={() => void load()} />
      </div>
    );
  }

  if (loading || !finding) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-40" />
        <div className="card card-pad space-y-4">
          <Skeleton className="h-6 w-2/3" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
          <div className="grid gap-4 sm:grid-cols-3">
            <Skeleton className="h-20" />
            <Skeleton className="h-20" />
            <Skeleton className="h-20" />
          </div>
        </div>
      </div>
    );
  }

  const relatedLogs = actions?.log.filter((log) => log.findingId === finding.id) ?? [];
  const relatedTasks = actions?.tasks.filter((task) => task.findingId === finding.id) ?? [];

  return (
    <div className="space-y-5">
      <Link href="/findings" className="btn-ghost w-fit py-1.5">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Back to findings
      </Link>

      <section className="card card-pad">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <TypeBadge type={finding.type} />
              <SeverityBadge severity={finding.severity} />
              <StatusChip status={finding.status} />
              <span className="text-xs text-slate-400">created {formatDateTime(finding.createdAt)}</span>
            </div>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight">{finding.title}</h1>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{finding.summary}</p>
            <div className="mt-4 rounded-xl bg-slate-50 p-3 dark:bg-slate-950/60">
              <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">Business impact</p>
              <p className="mt-1 text-sm text-slate-700 dark:text-slate-200">{finding.businessImpact}</p>
            </div>
          </div>
          <div className="flex flex-col items-center gap-2">
            <RiskGauge score={finding.riskScore} severity={finding.severity} />
            <span className="chip bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
              {finding.riskScore.toFixed(1)} / 100
            </span>
          </div>
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-3">
        <div className="space-y-4 xl:col-span-2">
          <section className="card card-pad">
            <SectionTitle
              title="Verified facts"
              hint="Computed by the deterministic engine. These numbers are never written by the AI."
            />
            <FactsPanel facts={finding.verifiedFacts} />
          </section>

          <section className="card card-pad">
            <SectionTitle
              title="AI hypotheses"
              hint="Causal explanations to investigate — each says what evidence would confirm or reject it."
            />
            <HypothesesPanel hypotheses={finding.aiHypotheses} />
          </section>
        </div>

        <div className="space-y-4">
          <section className="card card-pad">
            <RecommendationCard finding={finding} />
          </section>

          <section className="card card-pad">
            <SectionTitle title="Decision" hint="Record your call — it is written to the action log." />
            <DecisionBar
              datasetId={datasetId!}
              finding={finding}
              onUpdated={(updated) => {
                setFinding(updated);
                upsertFinding(updated);
              }}
              onActionsChanged={() => void loadActions()}
            />
          </section>

          <section className="card card-pad">
            <SectionTitle title="Action history" />
            <ActionsMini logs={relatedLogs} />
            {relatedTasks.length ? (
              <div className="mt-3 border-t border-slate-100 pt-3 dark:border-slate-800">
                <p className="mb-1 flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  <ListChecks className="h-3 w-3" aria-hidden="true" />
                  Tasks
                </p>
                <ul className="space-y-1 text-xs text-slate-600 dark:text-slate-300">
                  {relatedTasks.map((task) => (
                    <li key={task.id} className="flex items-center justify-between gap-2">
                      <span>{task.title}</span>
                      <StatusChip status={task.status} />
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </section>
        </div>
      </div>

      <section className="card card-pad">
        <SectionTitle
          title="Evidence rows"
          hint={`All ${finding.evidenceRows.length} rows behind this finding, with source and row id.`}
        />
        <EvidenceTable rows={finding.evidenceRows} />
      </section>

      <div className="grid gap-4 xl:grid-cols-2">
        <section className="card card-pad">
          <SectionTitle title="Related entities" hint="Everything the evidence links to." />
          <EntityChips entities={finding.relatedEntities} />
        </section>

        <section className="card card-pad">
          <SectionTitle
            title="Relationship graph"
            hint="Shared factors between products, couriers, locations and complaints."
            right={<GitBranch className="h-4 w-4 text-slate-400" aria-hidden="true" />}
          />
          <RelationshipGraph
            entities={finding.relatedEntities}
            evidenceCount={finding.evidenceRows.length}
            severity={finding.severity}
          />
        </section>
      </div>
    </div>
  );
}
