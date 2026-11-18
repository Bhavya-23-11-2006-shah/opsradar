"use client";

import { useRef, useState, type DragEvent } from "react";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  FileSpreadsheet,
  Loader2,
  ShieldCheck,
  Sparkles,
  UploadCloud,
} from "lucide-react";

import { Skeleton, cn, useMounted } from "@/components/ui";
import { CANONICAL_FIELDS, FILE_TYPE_LABELS, ANALYSIS_STEPS, confidenceTone } from "@/lib/constants";
import type { LocalPreview } from "@/lib/preview";
import type {
  QualityIssue,
  QualityResponse,
  ProgressResponse,
  SchemaMapping,
  UploadResponse,
} from "@/types/contract";

export function Dropzone({
  disabled,
  onFiles,
}: {
  disabled?: boolean;
  onFiles: (files: File[]) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const accept = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    if (disabled) return;
    const files = Array.from(event.dataTransfer.files).filter((file) =>
      /\.(csv|xlsx|xls)$/i.test(file.name),
    );
    if (files.length) onFiles(files);
  };

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="Upload CSV or Excel files"
      aria-disabled={disabled}
      onClick={() => !disabled && inputRef.current?.click()}
      onKeyDown={(event) => {
        if ((event.key === "Enter" || event.key === " ") && !disabled) {
          event.preventDefault();
          inputRef.current?.click();
        }
      }}
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={accept}
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed px-6 py-10 text-center transition",
        dragging
          ? "border-teal-400 bg-teal-50/60 dark:border-teal-600 dark:bg-teal-950/20"
          : "border-slate-200 bg-slate-50/60 hover:border-slate-300 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-950/40 dark:hover:border-slate-600",
        disabled && "cursor-not-allowed opacity-70",
      )}
    >
      <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-slate-500 shadow-sm dark:bg-slate-900 dark:text-slate-300">
        <UploadCloud className="h-6 w-6" aria-hidden="true" />
      </span>
      <div>
        <p className="text-sm font-medium">Drag &amp; drop CSV or Excel files</p>
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
          Orders, deliveries, complaints, reviews, inventory and sales. Field name is “files”.
        </p>
      </div>
      <span className="btn-secondary pointer-events-none">Choose files</span>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".csv,.xlsx,.xls"
        className="hidden"
        onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          if (files.length) onFiles(files);
          event.target.value = "";
        }}
      />
    </div>
  );
}

export function UploadedFileList({ upload }: { upload: UploadResponse }) {
  return (
    <ul className="divide-y divide-slate-100 dark:divide-slate-800" aria-label="Uploaded files">
      {upload.files.map((file) => (
        <li key={file.name} className="flex flex-col gap-2 py-3 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-start gap-3">
            <FileSpreadsheet className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{file.name}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {file.rows.toLocaleString()} rows · {file.columns.length} columns
              </p>
            </div>
          </div>
          <span className="chip w-fit bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
            {FILE_TYPE_LABELS[file.detectedType]}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function PreviewTable({ preview }: { preview: LocalPreview }) {
  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-800">
      <div className="flex items-center justify-between border-b border-slate-100 px-3 py-2 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
        <span className="truncate font-medium text-slate-600 dark:text-slate-300">
          Local preview · {preview.name}
        </span>
        <span>{preview.totalRows.toLocaleString()} rows</span>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-xs">
          <thead className="bg-slate-50 uppercase tracking-wide text-slate-500 dark:bg-slate-900 dark:text-slate-400">
            <tr>
              {preview.columns.slice(0, 8).map((column) => (
                <th key={column} className="whitespace-nowrap px-3 py-2 font-medium">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {preview.rows.map((row, index) => (
              <tr key={index}>
                {preview.columns.slice(0, 8).map((column) => (
                  <td key={column} className="max-w-[220px] truncate px-3 py-1.5 text-slate-600 dark:text-slate-300">
                    {row[column]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function MappingEditor({
  upload,
  mapping,
  onChange,
}: {
  upload: UploadResponse;
  mapping: SchemaMapping;
  onChange: (mapping: SchemaMapping) => void;
}) {
  const [activeIndex, setActiveIndex] = useState(0);
  const safeIndex = Math.min(activeIndex, mapping.files.length - 1);
  const file = mapping.files[safeIndex];
  const source = upload.files.find((entry) => entry.name === file?.fileName);
  const columns = source?.columns ?? [];
  const suggested = upload.files[safeIndex]?.suggestedMapping;

  if (!file) return null;

  const update = (key: string, value: string) => {
    const next = mapping.files.map((entry, index) =>
      index === safeIndex
        ? {
            ...entry,
            fields: { ...entry.fields, [key]: value === "" ? null : value },
            confidence: {
              ...entry.confidence,
              [key]: value === "" ? 0 : suggested?.fields[key as keyof typeof suggested.fields] === value ? (suggested?.confidence[key as keyof typeof suggested.confidence] ?? 1) : 1,
            },
          }
        : entry,
    );
    onChange({ files: next });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Files to map">
        {mapping.files.map((entry, index) => (
          <button
            key={entry.fileName}
            type="button"
            role="tab"
            aria-selected={index === safeIndex}
            onClick={() => setActiveIndex(index)}
            className={cn(
              "chip border",
              index === safeIndex
                ? "border-slate-900 bg-slate-900 text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-900"
                : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300",
            )}
          >
            {entry.fileName}
          </button>
        ))}
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {CANONICAL_FIELDS.map((field) => {
          const value = file.fields[field.key] ?? "";
          const confidence = file.confidence[field.key];
          return (
            <div key={field.key} className="rounded-xl border border-slate-200 p-3 dark:border-slate-800">
              <div className="mb-1.5 flex items-center justify-between gap-2">
                <label htmlFor={`map-${field.key}`} className="text-xs font-medium">
                  {field.label}
                </label>
                <span className={cn("chip px-2 py-0.5 text-[10px]", confidenceTone(confidence))}>
                  {confidence === undefined ? "not mapped" : `${Math.round(confidence * 100)}%`}
                </span>
              </div>
              <select
                id={`map-${field.key}`}
                className="field py-1.5 text-xs"
                value={value}
                onChange={(event) => update(field.key, event.target.value)}
              >
                <option value="">Not mapped</option>
                {columns.map((column) => (
                  <option key={column} value={column}>
                    {column}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-[10px] text-slate-400 dark:text-slate-500">{field.hint}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function HealthRing({ score }: { score: number }) {
  const mounted = useMounted();
  const radius = 34;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - Math.max(0, Math.min(100, score)) / 100);
  const color = score >= 80 ? "#0d9488" : score >= 60 ? "#d97706" : "#dc2626";
  return (
    <div className="relative h-24 w-24" role="img" aria-label={`Data health ${score} out of 100`}>
      <svg viewBox="0 0 84 84" className="h-full w-full -rotate-90">
        <circle cx="42" cy="42" r={radius} fill="none" strokeWidth="8" className="stroke-slate-100 dark:stroke-slate-800" />
        {mounted ? (
          <circle
            cx="42"
            cy="42"
            r={radius}
            fill="none"
            strokeWidth="8"
            strokeLinecap="round"
            stroke={color}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
          />
        ) : null}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-lg font-semibold tabular-nums">{score.toFixed(0)}</span>
        <span className="text-[9px] uppercase tracking-wide text-slate-500">health</span>
      </div>
    </div>
  );
}

function IssueList({ issues }: { issues: QualityIssue[] }) {
  if (issues.length === 0) {
    return <p className="text-xs text-slate-500 dark:text-slate-400">No issues found.</p>;
  }
  return (
    <div className="space-y-2">
      {issues.map((issue) => (
        <details key={`${issue.file}-${issue.column}-${issue.note}`} className="rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-950/60">
          <summary className="flex cursor-pointer items-center justify-between gap-2 text-xs text-slate-600 dark:text-slate-300">
            <span className="truncate">
              <span className="font-medium">{issue.file}</span>
              {issue.column ? ` · ${issue.column}` : ""}
            </span>
            <span className="chip bg-white text-slate-600 dark:bg-slate-800 dark:text-slate-300">{issue.count}</span>
          </summary>
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">{issue.note}</p>
          {issue.rowIds.length ? (
            <p className="mt-2 flex flex-wrap gap-1">
              {issue.rowIds.slice(0, 8).map((rowId) => (
                <span key={rowId} className="chip bg-slate-200/70 font-mono text-[10px] text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                  {rowId}
                </span>
              ))}
              {issue.rowIds.length > 8 ? (
                <span className="text-[10px] text-slate-400">+{issue.rowIds.length - 8} more</span>
              ) : null}
            </p>
          ) : null}
        </details>
      ))}
    </div>
  );
}

export function QualityReport({ quality }: { quality: QualityResponse }) {
  const groups = [
    { key: "missing", label: "Missing values", issues: quality.missing, icon: AlertTriangle },
    { key: "duplicates", label: "Duplicates", issues: quality.duplicates, icon: AlertTriangle },
    { key: "inconsistent", label: "Inconsistencies", issues: quality.inconsistent, icon: ShieldCheck },
  ] as const;

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <HealthRing score={quality.healthScore} />
        <p className="max-w-2xl text-sm text-slate-600 dark:text-slate-300">{quality.summary}</p>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        {groups.map((group) => {
          const Icon = group.icon;
          const total = group.issues.reduce((sum, issue) => sum + issue.count, 0);
          return (
            <div key={group.key} className="rounded-xl border border-slate-200 p-3 dark:border-slate-800">
              <div className="mb-2 flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-xs font-medium">
                  <Icon className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
                  {group.label}
                </span>
                <span className="chip bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300">{total}</span>
              </div>
              <IssueList issues={group.issues} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function AnalysisStepper({
  progress,
  running,
}: {
  progress: ProgressResponse | null;
  running: boolean;
}) {
  const currentIndex = progress?.step ? ANALYSIS_STEPS.indexOf(progress.step) : progress?.status === "done" ? ANALYSIS_STEPS.length : -1;
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
        <span>{progress?.message ?? "Ready to analyse"}</span>
        <span className="tabular-nums">{Math.round(progress?.percent ?? 0)}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
        <div
          className={cn("h-full rounded-full transition-all duration-500", progress?.status === "error" ? "bg-critical" : "bg-teal-600")}
          style={{ width: `${Math.max(progress?.percent ?? 0, running ? 2 : 0)}%` }}
        />
      </div>
      <ol className="grid gap-2 sm:grid-cols-5">
        {ANALYSIS_STEPS.map((step, index) => {
          const done = progress?.status === "done" || index < currentIndex;
          const active = running && index === currentIndex;
          return (
            <li
              key={step}
              className={cn(
                "flex items-center gap-2 rounded-xl border px-3 py-2 text-xs",
                done
                  ? "border-teal-200 bg-teal-50 text-teal-800 dark:border-teal-900 dark:bg-teal-950/30 dark:text-teal-200"
                  : active
                    ? "border-slate-900 bg-slate-900 text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-900"
                    : "border-slate-200 text-slate-500 dark:border-slate-800 dark:text-slate-400",
              )}
            >
              {done ? (
                <Check className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              ) : active ? (
                <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" aria-hidden="true" />
              ) : (
                <span className="h-3.5 w-3.5 shrink-0 rounded-full border border-current" aria-hidden="true" />
              )}
              <span className="truncate">{step}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export function DemoButtons({
  busy,
  onLoad,
}: {
  busy: boolean;
  onLoad: (industry: "fashion" | "skincare") => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      <button type="button" className="btn-primary" disabled={busy} onClick={() => onLoad("fashion")}>
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
        Load fashion demo
      </button>
      <button type="button" className="btn-secondary" disabled={busy} onClick={() => onLoad("skincare")}>
        <Sparkles className="h-4 w-4" aria-hidden="true" />
        Load skincare demo
      </button>
    </div>
  );
}

export function MappingSkeleton() {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 6 }).map((_, index) => (
        <div key={index} className="rounded-xl border border-slate-200 p-3 dark:border-slate-800">
          <Skeleton className="mb-2 h-3 w-20" />
          <Skeleton className="h-8 w-full" />
        </div>
      ))}
    </div>
  );
}
