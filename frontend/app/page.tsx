"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  Database,
  Loader2,
  Play,
  RotateCcw,
  Table2,
} from "lucide-react";

import {
  AnalysisStepper,
  DemoButtons,
  Dropzone,
  MappingEditor,
  PreviewTable,
  QualityReport,
  UploadedFileList,
} from "@/components/upload";
import {
  EmptyState,
  PageHeader,
  SectionTitle,
  Skeleton,
  cn,
  useMounted,
} from "@/components/ui";
import { api } from "@/lib/api";
import { previewFile, type LocalPreview } from "@/lib/preview";
import { toast } from "@/lib/toast";
import { useAppStore } from "@/store/useAppStore";
import type {
  ProgressResponse,
  QualityResponse,
  SchemaMapping,
  UploadResponse,
} from "@/types/contract";

function messageOf(error: unknown): string {
  if (error instanceof Error) return error.message;
  return String(error);
}

export default function UploadPage() {
  const mounted = useMounted();
  const datasetId = useAppStore((state) => state.datasetId);
  const upload = useAppStore((state) => state.upload);
  const storedMapping = useAppStore((state) => state.mapping);
  const mappingConfirmed = useAppStore((state) => state.mappingConfirmed);
  const industry = useAppStore((state) => state.industry);
  const setUpload = useAppStore((state) => state.setUpload);
  const setMapping = useAppStore((state) => state.setMapping);
  const reset = useAppStore((state) => state.reset);

  const [busy, setBusy] = useState<"demo" | "upload" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [previews, setPreviews] = useState<LocalPreview[]>([]);
  const [draft, setDraft] = useState<SchemaMapping | null>(null);
  const [savingMapping, setSavingMapping] = useState(false);
  const [progress, setProgress] = useState<ProgressResponse | null>(null);
  const [quality, setQuality] = useState<QualityResponse | null>(null);
  const [running, setRunning] = useState(false);
  const startedRef = useRef(false);

  useEffect(() => {
    if (!upload) {
      setDraft(null);
      return;
    }
    setDraft(storedMapping ?? { files: upload.files.map((file) => file.suggestedMapping) });
  }, [upload, storedMapping]);

  useEffect(() => {
    if (!datasetId) {
      setProgress(null);
      setQuality(null);
      return;
    }
    let active = true;
    (async () => {
      try {
        const current = await api.progress(datasetId);
        if (!active) return;
        setProgress(current);
        if (current.status === "running") {
          setRunning(true);
        } else if (current.status === "done") {
          const report = await api.quality(datasetId);
          if (active) setQuality(report);
        }
      } catch (err) {
        if (active) setError(messageOf(err));
      }
    })();
    return () => {
      active = false;
    };
  }, [datasetId]);

  useEffect(() => {
    if (!running || !datasetId) return;
    let active = true;
    const tick = async () => {
      try {
        const current = await api.progress(datasetId);
        if (!active) return;
        setProgress(current);
        if (current.status === "done") {
          setRunning(false);
          const report = await api.quality(datasetId);
          if (active) {
            setQuality(report);
            toast("Analysis complete", "success");
          }
        } else if (current.status === "error") {
          setRunning(false);
          setError(current.message ?? "The analysis failed.");
        }
      } catch (err) {
        if (!active) return;
        setRunning(false);
        setError(messageOf(err));
      }
    };
    const interval = window.setInterval(tick, 1000);
    void tick();
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [running, datasetId]);

  const applyUpload = useCallback(
    (response: UploadResponse, source: "fashion" | "skincare" | null) => {
      setUpload(response, source);
      setDraft({ files: response.files.map((file) => file.suggestedMapping) });
      setProgress(null);
      setQuality(null);
      setRunning(false);
      setError(null);
    },
    [setUpload],
  );

  const loadDemo = async (choice: "fashion" | "skincare") => {
    setBusy("demo");
    setError(null);
    try {
      setPreviews([]);
      const response = await api.demoGenerate({ industry: choice });
      applyUpload(response, choice);
      toast(`${choice === "fashion" ? "Fashion" : "Skincare"} demo dataset ready`, "success");
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(null);
    }
  };

  const handleFiles = async (files: File[]) => {
    setBusy("upload");
    setError(null);
    try {
      const previewResults = await Promise.all(
        files.slice(0, 3).map((file) => previewFile(file).catch(() => null)),
      );
      setPreviews(previewResults.filter((item): item is LocalPreview => item !== null));
      const response = await api.upload(files);
      applyUpload(response, null);
      toast(`Uploaded ${response.files.length} file(s)`, "success");
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(null);
    }
  };

  const confirmMapping = async () => {
    if (!datasetId || !draft) return;
    setSavingMapping(true);
    setError(null);
    try {
      const response = await api.mapSchema(datasetId, draft);
      setMapping(response.mapping, true);
      toast("Schema mapping confirmed", "success");
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setSavingMapping(false);
    }
  };

  const runAnalysis = async () => {
    if (!datasetId) return;
    setError(null);
    try {
      setQuality(null);
      const response = await api.analyze(datasetId);
      if (response.status === "running") {
        setProgress({ status: "running", step: "Cleaning", percent: 1, message: "Starting analysis" });
        setRunning(true);
        toast("Analysis started — progress updates every second", "info");
      }
    } catch (err) {
      setError(messageOf(err));
      setRunning(false);
    }
  };

  const resetAll = () => {
    reset();
    setPreviews([]);
    setDraft(null);
    setProgress(null);
    setQuality(null);
    setRunning(false);
    setError(null);
    toast("Workspace cleared", "info");
  };

  if (!mounted) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-4 w-96" />
        <Skeleton className="h-56 w-full" />
      </div>
    );
  }

  const analysed = progress?.status === "done" || Boolean(quality);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Upload & Data Quality"
        description="Bring in orders, deliveries, complaints, reviews, inventory and sales. Confirm how columns map to the canonical schema, then let the engine clean and analyse."
        actions={
          datasetId ? (
            <button type="button" className="btn-secondary" onClick={resetAll}>
              <RotateCcw className="h-4 w-4" aria-hidden="true" />
              Start over
            </button>
          ) : null
        }
      />

      {error ? (
        <div role="alert" className="flex items-start justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/50 dark:text-red-200">
          <span>{error}</span>
          <button type="button" className="text-xs font-medium underline" onClick={() => setError(null)}>
            Dismiss
          </button>
        </div>
      ) : null}

      <section className="card card-pad space-y-4">
        <SectionTitle
          title="1 · Ingest data"
          hint="Use the seeded demo, or drop your own CSV/Excel files."
          right={
            industry ? (
              <span className="chip bg-teal-50 capitalize text-verified dark:bg-teal-950/40">
                {industry} demo
              </span>
            ) : null
          }
        />
        <DemoButtons busy={busy === "demo"} onLoad={loadDemo} />
        <div className="relative py-1 text-center text-[11px] uppercase tracking-wide text-slate-400">
          or upload your own
        </div>
        <Dropzone disabled={busy !== null} onFiles={handleFiles} />
        {busy === "upload" ? (
          <p className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
            <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
            Uploading and detecting file types…
          </p>
        ) : null}
        {previews.length ? (
          <div className="space-y-3">
            <p className="text-xs font-medium text-slate-500 dark:text-slate-400">Local preview</p>
            {previews.map((preview) => (
              <PreviewTable key={preview.name} preview={preview} />
            ))}
          </div>
        ) : null}
        {upload ? (
          <div className="rounded-xl border border-slate-200 p-4 dark:border-slate-800">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <p className="flex items-center gap-2 text-sm font-medium">
                <Database className="h-4 w-4 text-slate-400" aria-hidden="true" />
                Dataset <span className="font-mono text-xs text-slate-400">{datasetId}</span>
              </p>
              <button type="button" className="btn-secondary py-1.5 text-xs" onClick={() => setBusy(null)}>
                <Table2 className="h-3.5 w-3.5" aria-hidden="true" />
                {upload.files.length} files detected
              </button>
            </div>
            <UploadedFileList upload={upload} />
          </div>
        ) : null}
      </section>

      {upload && draft ? (
        <section className="card card-pad space-y-4">
          <SectionTitle
            title="2 · Column mapping"
            hint="Map each canonical field to your real column. Unmapped fields are allowed."
            right={
              <div className="flex items-center gap-2">
                {mappingConfirmed ? (
                  <span className="chip bg-teal-50 text-verified dark:bg-teal-950/40">
                    <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                    Confirmed
                  </span>
                ) : null}
                <button
                  type="button"
                  className={cn("btn-primary py-1.5 text-xs", mappingConfirmed && "opacity-90")}
                  onClick={confirmMapping}
                  disabled={savingMapping || !datasetId}
                >
                  {savingMapping ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                  {mappingConfirmed ? "Update mapping" : "Confirm mapping"}
                </button>
              </div>
            }
          />
          <MappingEditor upload={upload} mapping={draft} onChange={setDraft} />
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Confidence badges: red below 50%, amber 50–80%, green above 80%. Your confirmed mapping is what every
            detector uses.
          </p>
        </section>
      ) : null}

      <section className="card card-pad space-y-4">
        <SectionTitle
          title="3 · Run the analysis"
          hint="Cleaning → linking datasets → detecting patterns → assessing risks → recommendations."
          right={
            <button
              type="button"
              className="btn-primary"
              onClick={runAnalysis}
              disabled={!datasetId || !mappingConfirmed || running || busy !== null}
            >
              {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              {running ? "Analysing…" : "Run analysis"}
            </button>
          }
        />
        {!datasetId ? (
          <EmptyState
            icon={Database}
            title="No dataset loaded"
            description="Load a demo dataset or upload files. Then confirm the column mapping to unlock the analysis."
          />
        ) : !mappingConfirmed && !running ? (
          <p className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
            Confirm the column mapping above before running the analysis.
          </p>
        ) : (
          <AnalysisStepper progress={progress} running={running} />
        )}
        {analysed && !running ? (
          <div className="flex flex-wrap items-center gap-2 rounded-xl border border-teal-200 bg-teal-50/60 px-4 py-3 text-sm text-teal-900 dark:border-teal-900 dark:bg-teal-950/30 dark:text-teal-200">
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
            <span className="flex-1">Analysis finished. {progress?.message}</span>
            <Link href="/overview" className="btn-primary py-1.5 text-xs">
              Open overview
              <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
            </Link>
            <Link href="/findings" className="btn-secondary py-1.5 text-xs">
              Review findings
            </Link>
          </div>
        ) : null}
      </section>

      {quality ? (
        <section className="card card-pad space-y-4">
          <SectionTitle title="4 · Data quality" hint="Every issue is traceable to concrete rows." />
          <QualityReport quality={quality} />
        </section>
      ) : null}
    </div>
  );
}
