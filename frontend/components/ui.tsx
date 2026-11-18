"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  Info,
  Loader2,
  Package,
  Repeat,
  TrendingUp,
  Truck,
  X,
  type LucideIcon,
} from "lucide-react";
import { dismissToast, subscribeToasts, type ToastItem } from "@/lib/toast";
import type { FindingType, Severity, Status } from "@/types/contract";

export type Priority = "urgent" | "high" | "normal" | "low";

export function cn(...values: Array<string | false | null | undefined>): string {
  return values.filter(Boolean).join(" ");
}

export function useMounted(): boolean {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return mounted;
}

export function useCountUp(value: number, duration = 700): number {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    let frame = 0;
    const started = performance.now();
    const tick = (now: number) => {
      const progress = Math.min(1, (now - started) / duration);
      setDisplay(Math.round(value * (1 - Math.pow(1 - progress, 3))));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value, duration]);
  return display;
}

export const SEVERITY_STYLES: Record<Severity, string> = {
  critical: "bg-red-50 text-red-700 ring-red-200 dark:bg-red-950/40 dark:text-red-300 dark:ring-red-900",
  high: "bg-orange-50 text-orange-700 ring-orange-200 dark:bg-orange-950/40 dark:text-orange-300 dark:ring-orange-900",
  medium: "bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:ring-amber-900",
  low: "bg-green-50 text-green-700 ring-green-200 dark:bg-green-950/40 dark:text-green-300 dark:ring-green-900",
};

export const SEVERITY_HEX: Record<Severity, string> = {
  critical: "#dc2626",
  high: "#ea580c",
  medium: "#d97706",
  low: "#16a34a",
};

export const STATUS_STYLES: Record<Status, string> = {
  open: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200",
  investigating: "bg-sky-50 text-sky-700 dark:bg-sky-950/50 dark:text-sky-300",
  escalated: "bg-purple-50 text-ai dark:bg-purple-950/40 dark:text-purple-300",
  resolved: "bg-teal-50 text-verified dark:bg-teal-950/40 dark:text-teal-300",
  rejected: "bg-slate-100 text-slate-500 line-through dark:bg-slate-800 dark:text-slate-400",
};

export const TYPE_META: Record<FindingType, { label: string; icon: LucideIcon }> = {
  recurring_issue: { label: "Recurring issue", icon: Repeat },
  anomaly: { label: "Anomaly", icon: Activity },
  delivery_risk: { label: "Delivery risk", icon: Truck },
  inventory_risk: { label: "Inventory risk", icon: Package },
  complaint_spike: { label: "Complaint spike", icon: TrendingUp },
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className={cn("chip capitalize ring-1", SEVERITY_STYLES[severity])}>
      {severity}
    </span>
  );
}

export function StatusChip({ status }: { status: Status }) {
  return (
    <span className={cn("chip capitalize", STATUS_STYLES[status])}>
      {status.replace("_", " ")}
    </span>
  );
}

export function TypeBadge({ type }: { type: FindingType }) {
  const meta = TYPE_META[type];
  const Icon = meta.icon;
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 dark:text-slate-300">
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {meta.label}
    </span>
  );
}

export function PriorityBadge({ priority }: { priority: Priority }) {
  const tone =
    priority === "urgent"
      ? "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300"
      : priority === "high"
        ? "bg-orange-50 text-orange-700 dark:bg-orange-950/40 dark:text-orange-300"
        : priority === "normal"
          ? "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300"
          : "bg-green-50 text-green-700 dark:bg-green-950/40 dark:text-green-300";
  return <span className={cn("chip capitalize", tone)}>{priority} priority</span>;
}

export function RiskMeter({ score, severity }: { score: number; severity: Severity }) {
  return (
    <div className="flex items-center gap-2" aria-label={`Risk score ${score} out of 100`}>
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${Math.max(2, Math.min(100, score))}%`, backgroundColor: SEVERITY_HEX[severity] }}
        />
      </div>
      <span className="text-xs font-semibold tabular-nums">{score}</span>
    </div>
  );
}

export function RiskGauge({ score, severity }: { score: number; severity: Severity }) {
  const radius = 46;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - Math.min(100, Math.max(0, score)) / 100);
  return (
    <div className="relative h-32 w-32" role="img" aria-label={`Risk score ${score} out of 100`}>
      <svg viewBox="0 0 112 112" className="h-full w-full -rotate-90">
        <circle cx="56" cy="56" r={radius} fill="none" strokeWidth="10" className="stroke-slate-100 dark:stroke-slate-800" />
        <circle
          cx="56"
          cy="56"
          r={radius}
          fill="none"
          strokeWidth="10"
          strokeLinecap="round"
          stroke={SEVERITY_HEX[severity]}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-semibold tabular-nums">{Math.round(score)}</span>
        <span className="text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400">risk score</span>
      </div>
    </div>
  );
}

export function ConfidenceBar({ value }: { value: number }) {
  const percent = Math.round(Math.min(1, Math.max(0, value)) * 100);
  return (
    <div className="space-y-1">
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-purple-100 dark:bg-purple-950/50">
        <div className="h-full rounded-full bg-ai" style={{ width: `${percent}%` }} />
      </div>
      <p className="text-[11px] text-slate-500 dark:text-slate-400">{percent}% confidence</p>
    </div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
        {description ? (
          <p className="mt-1 max-w-2xl text-sm text-slate-500 dark:text-slate-400">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function SectionTitle({
  title,
  hint,
  right,
}: {
  title: string;
  hint?: string;
  right?: ReactNode;
}) {
  return (
    <div className="mb-3 flex items-end justify-between gap-3">
      <div>
        <h2 className="text-base font-semibold">{title}</h2>
        {hint ? <p className="text-xs text-slate-500 dark:text-slate-400">{hint}</p> : null}
      </div>
      {right}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} aria-hidden="true" />;
}

export function CardsSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="card card-pad space-y-3">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-8 w-16" />
          <Skeleton className="h-2 w-full" />
        </div>
      ))}
    </div>
  );
}

export function EmptyState({
  icon: Icon = Info,
  title,
  description,
  action,
}: {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="card card-pad flex flex-col items-center justify-center gap-3 py-12 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400">
        <Icon className="h-6 w-6" aria-hidden="true" />
      </span>
      <div>
        <p className="font-medium">{title}</p>
        {description ? (
          <p className="mt-1 max-w-md text-sm text-slate-500 dark:text-slate-400">{description}</p>
        ) : null}
      </div>
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="card card-pad flex flex-col items-center justify-center gap-3 py-10 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-red-50 text-critical dark:bg-red-950/40">
        <AlertCircle className="h-6 w-6" aria-hidden="true" />
      </span>
      <div>
        <p className="font-medium">Something went wrong</p>
        <p className="mt-1 max-w-lg text-sm text-slate-500 dark:text-slate-400">{message}</p>
      </div>
      {onRetry ? (
        <button type="button" className="btn-primary" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  );
}

export function LoadingCard({ label = "Loading" }: { label?: string }) {
  return (
    <div className="card card-pad flex items-center justify-center gap-2 py-14 text-sm text-slate-500 dark:text-slate-400">
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      {label}…
    </div>
  );
}

export function NoDataset({ children }: { children?: ReactNode }) {
  return (
    <EmptyState
      title="No dataset loaded yet"
      description="Load the demo data or upload your own CSV/Excel files to start the analysis."
      action={
        <Link href="/" className="btn-primary">
          Go to upload
        </Link>
      }
    />
  );
}

export function LinkButton({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link href={href} className="btn-secondary">
      {children}
    </Link>
  );
}

export function Toaster() {
  const [items, setItems] = useState<ToastItem[]>([]);
  useEffect(() => subscribeToasts(setItems), []);

  if (items.length === 0) return null;

  return (
    <div className="no-print fixed bottom-4 right-4 z-50 flex w-full max-w-sm flex-col gap-2" role="status" aria-live="polite">
      {items.map((item) => {
        const Icon =
          item.tone === "error"
            ? AlertCircle
            : item.tone === "success"
              ? CheckCircle2
              : item.tone === "warning"
                ? AlertCircle
                : Info;
        return (
          <div
            key={item.id}
            className={cn(
              "flex items-start gap-3 rounded-xl border px-4 py-3 text-sm shadow-lift",
              item.tone === "error"
                ? "border-red-200 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950/70 dark:text-red-200"
                : item.tone === "success"
                  ? "border-teal-200 bg-teal-50 text-teal-800 dark:border-teal-900 dark:bg-teal-950/70 dark:text-teal-200"
                  : "border-slate-200 bg-white text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200",
            )}
          >
            <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <span className="flex-1">{item.message}</span>
            <button type="button" aria-label="Dismiss notification" onClick={() => dismissToast(item.id)}>
              <X className="h-4 w-4 opacity-60" aria-hidden="true" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
