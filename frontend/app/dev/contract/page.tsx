"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { CheckCircle2, Loader2, PlayCircle, XCircle } from "lucide-react";

import { PageHeader, Skeleton, cn } from "@/components/ui";
import { API_BASE_URL, ContractError, USE_MOCK, api } from "@/lib/api";
import type { HealthResponse } from "@/types/contract";

interface CheckResult {
  endpoint: string;
  label: string;
  ok: boolean;
  http: string;
  ms: number;
  issues: string[];
  detail?: string;
}

const SAMPLE_CSV =
  "orderId,customerId,productId,date,promisedDate,warehouse,city,courier,status,quantity,amount\n" +
  "ORD-9001,C1,P-1,2026-01-02,2026-01-05,WH-1,Leeds,MetroDash,delivered,1,49.0\n" +
  "ORD-9002,C2,P-2,2026-01-03,2026-01-06,WH-1,Bristol,ParcelOne,in_transit,2,88.0\n";

export default function ContractDevPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [results, setResults] = useState<CheckResult[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  const run = useCallback(async () => {
    setRunning(true);
    setError(null);
    const collected: CheckResult[] = [];

    const record = async (label: string, endpoint: string, action: () => Promise<unknown>) => {
      const startedAt = performance.now();
      try {
        await action();
        const elapsed = performance.now() - startedAt;
        collected.push({
          label,
          endpoint,
          ok: true,
          http: USE_MOCK ? "mock · 200" : "200",
          ms: Math.round(elapsed),
          issues: [],
        });
      } catch (err) {
        const elapsed = performance.now() - startedAt;
        const issues = err instanceof ContractError ? err.issues : [];
        collected.push({
          label,
          endpoint,
          ok: false,
          http: USE_MOCK ? "mock" : err && typeof err === "object" && "status" in err ? String((err as { status: number }).status) : "error",
          ms: Math.round(elapsed),
          issues,
          detail: err instanceof Error ? err.message : String(err),
        });
      }
      setResults([...collected]);
    };

    try {
      await record("Health", "GET /api/health", async () => {
        const response = await api.health();
        setHealth(response);
      });

      let datasetId = "";
      await record("Demo dataset", "POST /api/demo/generate", async () => {
        const demo = await api.demoGenerate({ industry: "fashion" });
        datasetId = demo.datasetId;
        const mapping = { files: demo.files.map((file) => file.suggestedMapping) };
        await record("Confirm mapping", "POST /api/map-schema", () =>
          api.mapSchema(datasetId, mapping),
        );
      });

      await record("Upload (multipart files)", "POST /api/upload", () =>
        api.upload([new File([SAMPLE_CSV], "contract-sample.csv", { type: "text/csv" })]),
      );

      if (!datasetId) throw new Error("No dataset id was produced by the demo endpoint.");

      await record("Analyze", "POST /api/analyze/:id", () => api.analyze(datasetId));
      await record("Progress", "GET /api/progress/:id", () => api.progress(datasetId));
      await record("Quality", "GET /api/quality/:id", () => api.quality(datasetId));
      await record("Overview", "GET /api/overview/:id", () => api.overview(datasetId));
      await record("Findings list", "GET /api/findings/:id", () => api.findings(datasetId));

      let findingId = "";
      await record("Finding detail", "GET /api/findings/:id/:findingId", async () => {
        const list = await api.findings(datasetId);
        findingId = list[0]?.id ?? "";
        if (!findingId) throw new Error("No findings were returned.");
        await api.finding(datasetId, findingId);
      });

      if (findingId) {
        await record("Decision", "POST /api/findings/:id/:findingId/decision", () =>
          api.decide(datasetId, findingId, { decision: "approve", note: "Contract self-test" }),
        );
        await record("Status", "PATCH /api/findings/:id/:findingId/status", () =>
          api.patchStatus(datasetId, findingId, { status: "resolved" }),
        );
        await record("Task", "POST /api/findings/:id/:findingId/task", () =>
          api.createTask(datasetId, findingId, { title: "Contract self-test task" }),
        );
      }

      await record("Actions", "GET /api/actions/:id", () => api.actions(datasetId));
      await record("Report", "POST /api/report/:id", () => api.report(datasetId));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setResults([...collected]);
      setRunning(false);
    }
  }, []);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void run();
  }, [run]);

  const passed = results.filter((result) => result.ok).length;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Contract self-test"
        description="Calls every endpoint in sequence and validates each response against the zod mirrors of CONTRACT v1."
        actions={
          <button type="button" className="btn-primary" onClick={() => void run()} disabled={running}>
            {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlayCircle className="h-4 w-4" />}
            Run all checks
          </button>
        }
      />

      <section className="grid gap-4 sm:grid-cols-3">
        <div className="card card-pad">
          <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Contract</p>
          <p className="mt-1 text-lg font-semibold">v{health?.contractVersion ?? "1"}</p>
        </div>
        <div className="card card-pad">
          <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">LLM mode</p>
          <p className="mt-1 text-lg font-semibold capitalize">{health?.llmMode ?? "—"}</p>
        </div>
        <div className="card card-pad">
          <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Transport</p>
          <p className="mt-1 truncate text-sm font-medium">{USE_MOCK ? "mock files" : API_BASE_URL}</p>
          <p className="text-[11px] text-slate-500 dark:text-slate-400">
            NEXT_PUBLIC_USE_MOCK={String(USE_MOCK)}
          </p>
        </div>
      </section>

      {error ? (
        <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/50 dark:text-red-200">
          {error}
        </p>
      ) : null}

      <section className="card overflow-hidden">
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3 dark:border-slate-800">
          <h2 className="text-sm font-semibold">Endpoint checks</h2>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            {passed}/{results.length} passing
          </span>
        </div>
        {results.length === 0 ? (
          <div className="space-y-2 p-4">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-100 text-sm dark:divide-slate-800">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                <tr>
                  <th scope="col" className="px-4 py-2 text-left font-medium">Status</th>
                  <th scope="col" className="px-4 py-2 text-left font-medium">Endpoint</th>
                  <th scope="col" className="px-4 py-2 text-left font-medium">HTTP</th>
                  <th scope="col" className="px-4 py-2 text-left font-medium">Time</th>
                  <th scope="col" className="px-4 py-2 text-left font-medium">Contract / error</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {results.map((result) => (
                  <tr key={result.endpoint + result.label}>
                    <td className="whitespace-nowrap px-4 py-2">
                      <span
                        className={cn(
                          "inline-flex items-center gap-1 text-xs font-medium",
                          result.ok ? "text-verified" : "text-critical",
                        )}
                      >
                        {result.ok ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
                        {result.ok ? "pass" : "fail"}
                      </span>
                    </td>
                    <td className="px-4 py-2">
                      <p className="text-xs font-medium">{result.label}</p>
                      <p className="font-mono text-[10px] text-slate-400">{result.endpoint}</p>
                    </td>
                    <td className="whitespace-nowrap px-4 py-2 font-mono text-[11px] text-slate-500 dark:text-slate-400">
                      {result.http}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2 text-xs tabular-nums text-slate-500 dark:text-slate-400">
                      {result.ms} ms
                    </td>
                    <td className="max-w-lg px-4 py-2">
                      {result.issues.length ? (
                        <ul className="space-y-0.5 font-mono text-[10px] text-critical">
                          {result.issues.map((issue) => (
                            <li key={issue}>{issue}</li>
                          ))}
                        </ul>
                      ) : result.ok ? (
                        <span className="text-xs text-slate-400">schema ok</span>
                      ) : (
                        <span className="text-xs text-critical">{result.detail}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <p className="text-xs text-slate-500 dark:text-slate-400">
        This page is intentionally unlinked from the main navigation. It is the first stop whenever the frontend and
        backend disagree.
      </p>
    </div>
  );
}
