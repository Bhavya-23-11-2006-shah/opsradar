"use client";

import { useState } from "react";
import { Download, FileText, Loader2, Printer, RefreshCw } from "lucide-react";

import { MarkdownView } from "@/components/markdown";
import {
  EmptyState,
  ErrorState,
  NoDataset,
  PageHeader,
  Skeleton,
  useMounted,
} from "@/components/ui";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/constants";
import { toast } from "@/lib/toast";
import { useAppStore } from "@/store/useAppStore";
import type { ReportResponse } from "@/types/contract";

export default function ReportPage() {
  const mounted = useMounted();
  const datasetId = useAppStore((state) => state.datasetId);
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generate = async () => {
    if (!datasetId) return;
    setLoading(true);
    setError(null);
    try {
      const response = await api.report(datasetId);
      setReport(response);
      toast("Report generated", "success");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const download = () => {
    if (!report) return;
    const blob = new Blob([report.markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `opsradar-report-${new Date().toISOString().slice(0, 10)}.md`;
    anchor.click();
    URL.revokeObjectURL(url);
    toast("Markdown downloaded", "success");
  };

  if (!mounted) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (!datasetId) {
    return (
      <div>
        <PageHeader title="Management Report" description="A board-ready summary grounded in the analysed data." />
        <NoDataset />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="no-print">
        <PageHeader
          title="Management Report"
          description="Executive summary, top risks, findings with facts and hypotheses kept separate, decisions and next steps."
          actions={
            <>
              <button type="button" className="btn-primary" onClick={() => void generate()} disabled={loading}>
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : report ? <RefreshCw className="h-4 w-4" /> : <FileText className="h-4 w-4" />}
                {report ? "Regenerate report" : "Generate report"}
              </button>
              {report ? (
                <>
                  <button type="button" className="btn-secondary" onClick={download}>
                    <Download className="h-4 w-4" aria-hidden="true" />
                    Download .md
                  </button>
                  <button type="button" className="btn-secondary" onClick={() => window.print()}>
                    <Printer className="h-4 w-4" aria-hidden="true" />
                    Print / PDF
                  </button>
                </>
              ) : null}
            </>
          }
        />
      </div>

      {error ? (
        <ErrorState message={error} onRetry={() => void generate()} />
      ) : loading ? (
        <div className="card card-pad space-y-3">
          <Skeleton className="h-7 w-64" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : report ? (
        <article className="card card-pad">
          <p className="mb-4 text-xs text-slate-500 dark:text-slate-400">
            Generated {formatDateTime(report.generatedAt)} · dataset <span className="font-mono">{datasetId}</span>
          </p>
          <MarkdownView markdown={report.markdown} />
        </article>
      ) : (
        <EmptyState
          icon={FileText}
          title="No report generated yet"
          description="Generate a report to pull the current findings, verified facts, AI hypotheses and logged decisions into one document."
          action={
            <button type="button" className="btn-primary" onClick={() => void generate()}>
              Generate report
            </button>
          }
        />
      )}
    </div>
  );
}
