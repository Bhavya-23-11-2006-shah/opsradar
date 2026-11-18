"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { Finding, SchemaMapping, UploadResponse } from "@/types/contract";

interface AppState {
  datasetId: string | null;
  industry: "fashion" | "skincare" | null;
  upload: UploadResponse | null;
  mapping: SchemaMapping | null;
  mappingConfirmed: boolean;
  findings: Finding[];
  theme: "light" | "dark";
  setUpload: (upload: UploadResponse, industry: "fashion" | "skincare" | null) => void;
  setMapping: (mapping: SchemaMapping, confirmed: boolean) => void;
  setFindings: (findings: Finding[]) => void;
  upsertFinding: (finding: Finding) => void;
  patchFindingStatus: (id: string, status: Finding["status"]) => void;
  setTheme: (theme: "light" | "dark") => void;
  toggleTheme: () => void;
  reset: () => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      datasetId: null,
      industry: null,
      upload: null,
      mapping: null,
      mappingConfirmed: false,
      findings: [],
      theme: "light",
      setUpload: (upload, industry) =>
        set({
          upload,
          datasetId: upload.datasetId,
          industry,
          mapping: null,
          mappingConfirmed: false,
          findings: [],
        }),
      setMapping: (mapping, confirmed) => set({ mapping, mappingConfirmed: confirmed }),
      setFindings: (findings) => set({ findings }),
      upsertFinding: (finding) =>
        set({
          findings: get().findings.map((item) => (item.id === finding.id ? finding : item)),
        }),
      patchFindingStatus: (id, status) =>
        set({
          findings: get().findings.map((item) => (item.id === id ? { ...item, status } : item)),
        }),
      setTheme: (theme) => set({ theme }),
      toggleTheme: () => set({ theme: get().theme === "dark" ? "light" : "dark" }),
      reset: () =>
        set({
          datasetId: null,
          industry: null,
          upload: null,
          mapping: null,
          mappingConfirmed: false,
          findings: [],
        }),
    }),
    {
      name: "opsradar-v1",
      partialize: (state) => ({
        datasetId: state.datasetId,
        industry: state.industry,
        upload: state.upload,
        mapping: state.mapping,
        mappingConfirmed: state.mappingConfirmed,
        findings: state.findings,
        theme: state.theme,
      }),
    },
  ),
);
