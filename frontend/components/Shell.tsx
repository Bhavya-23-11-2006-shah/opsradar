"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  Code2,
  FileText,
  LayoutDashboard,
  Menu,
  Moon,
  Radar,
  Sun,
  Trello,
  UploadCloud,
  X,
} from "lucide-react";

import { Toaster, cn, useMounted } from "@/components/ui";
import { useAppStore } from "@/store/useAppStore";

const NAV = [
  { href: "/", label: "Upload & Data Quality", icon: UploadCloud },
  { href: "/overview", label: "Overview", icon: LayoutDashboard },
  { href: "/findings", label: "Findings", icon: AlertTriangle },
  { href: "/tracker", label: "Action Tracker", icon: Trello },
  { href: "/report", label: "Management Report", icon: FileText },
];

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const theme = useAppStore((state) => state.theme);
  const toggleTheme = useAppStore((state) => state.toggleTheme);
  const mounted = useMounted();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  return (
    <div className="min-h-screen">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-slate-900 focus:px-4 focus:py-2 focus:text-white"
      >
        Skip to content
      </a>

      <div className="no-print fixed inset-x-0 top-0 z-30 flex h-14 items-center justify-between border-b border-slate-200 bg-white/90 px-4 backdrop-blur dark:border-slate-800 dark:bg-slate-950/90 lg:hidden">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900">
            <Radar className="h-4 w-4" />
          </span>
          OpsRadar
        </Link>
        <button
          type="button"
          className="btn-ghost px-2"
          aria-label={menuOpen ? "Close navigation" : "Open navigation"}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((open) => !open)}
        >
          {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {menuOpen ? (
        <button
          type="button"
          aria-label="Close navigation overlay"
          className="no-print fixed inset-0 z-30 bg-slate-900/30 lg:hidden"
          onClick={() => setMenuOpen(false)}
        />
      ) : null}

      <aside
        className={cn(
          "no-print fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-slate-200 bg-white transition-transform dark:border-slate-800 dark:bg-slate-900 lg:translate-x-0",
          menuOpen ? "translate-x-0 pt-14 lg:pt-0" : "-translate-x-full",
        )}
      >
        <div className="hidden items-center gap-3 px-5 py-6 lg:flex">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-900 text-white shadow-lift dark:bg-slate-100 dark:text-slate-900">
            <Radar className="h-5 w-5" />
          </span>
          <div>
            <p className="text-base font-semibold tracking-tight">OpsRadar</p>
            <p className="text-xs text-slate-500 dark:text-slate-400">Operational intelligence</p>
          </div>
        </div>

        <div className="flex items-center gap-3 px-5 pt-4 lg:hidden">
          <span className="text-sm font-semibold">Navigation</span>
        </div>

        <nav aria-label="Primary" className="flex-1 space-y-1 px-3 py-4">
          {NAV.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn("nav-link", active && "nav-link-active")}
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="space-y-2 border-t border-slate-200 px-3 py-4 dark:border-slate-800">
          <Link href="/dev/contract" className="nav-link text-xs">
            <Code2 className="h-4 w-4" aria-hidden="true" />
            Contract self-test
          </Link>
          <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2 text-xs text-slate-500 dark:bg-slate-950 dark:text-slate-400">
            <span>Contract v1</span>
            {mounted ? (
              <button
                type="button"
                onClick={toggleTheme}
                className="btn-ghost px-2 py-1"
                aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
              >
                {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </button>
            ) : (
              <span className="h-6 w-6" />
            )}
          </div>
        </div>
      </aside>

      <div className="lg:pl-72">
        <header className="no-print sticky top-14 z-20 hidden h-16 items-center justify-between border-b border-slate-200 bg-white/80 px-8 backdrop-blur dark:border-slate-800 dark:bg-slate-950/80 lg:flex">
          <p className="text-sm text-slate-500 dark:text-slate-400">
            AI-powered operational intelligence &amp; early warning
          </p>
          <div className="flex items-center gap-3">
            <span className="chip bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
              Early warning
            </span>
            <span className="chip bg-teal-50 text-verified dark:bg-teal-950/50">
              Evidence first
            </span>
          </div>
        </header>

        <main id="main" className="mx-auto w-full max-w-[1400px] px-4 pb-16 pt-20 sm:px-6 lg:px-8 lg:pt-10">
          {children}
        </main>
      </div>

      <Toaster />
    </div>
  );
}
