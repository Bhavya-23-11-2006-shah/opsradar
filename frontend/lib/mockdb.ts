"use client";

import actionsMock from "@/mocks/actions.json";
import analyzeMock from "@/mocks/analyze.json";
import demoMock from "@/mocks/demo-generate.json";
import findingMock from "@/mocks/finding.json";
import findingsMock from "@/mocks/findings.json";
import healthMock from "@/mocks/health.json";
import mapSchemaMock from "@/mocks/map-schema.json";
import overviewMock from "@/mocks/overview.json";
import progressMock from "@/mocks/progress.json";
import qualityMock from "@/mocks/quality.json";
import reportMock from "@/mocks/report.json";
import taskMock from "@/mocks/task.json";
import type {
  ActionsResponse,
  ActionLog,
  AnalyzeResponse,
  DecisionRequest,
  DemoRequest,
  Finding,
  FindingsFilters,
  InvestigationTask,
  MapSchemaRequest,
  MapSchemaResponse,
  OverviewFilters,
  OverviewResponse,
  ProgressResponse,
  QualityResponse,
  ReportResponse,
  SchemaMapping,
  Status,
  StatusRequest,
  TaskRequest,
  UploadResponse,
} from "@/types/contract";

export const MOCK_DATASET_ID = "demo-mock";

const STATUS_BY_DECISION: Record<string, Status> = {
  approve: "investigating",
  reject: "rejected",
  escalate: "escalated",
};

const STEPS: ProgressResponse["step"][] = [
  "Cleaning",
  "Linking datasets",
  "Detecting patterns",
  "Assessing risks",
  "Generating recommendations",
];

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

let findings: Finding[] = clone(findingsMock as unknown as Finding[]);
let actions: ActionsResponse = clone(actionsMock as unknown as ActionsResponse);
let mapping: SchemaMapping = clone(mapSchemaMock.mapping as unknown as SchemaMapping);
let analyzingSince: number | null = null;

// Replay the exported decision log so the mock state starts consistent.
for (const entry of actions.log) {
  const finding = findings.find((item) => item.id === entry.findingId);
  if (!finding) continue;
  if (STATUS_BY_DECISION[entry.decision]) {
    finding.status = STATUS_BY_DECISION[entry.decision];
  }
  if (entry.decision === "status_changed") {
    const match = entry.note.match(/Status changed to (\w+)/i);
    if (match) finding.status = match[1].toLowerCase() as Status;
  }
}

function overviewWithLiveKpis(filters: OverviewFilters = {}): OverviewResponse {
  const base = clone(overviewMock as unknown as OverviewResponse);
  const openStatuses = new Set<Status>(["open", "investigating", "escalated"]);
  base.kpis.openIssues = findings.filter((item) => openStatuses.has(item.status)).length;
  base.kpis.criticalRisks = findings.filter(
    (item) => openStatuses.has(item.status) && item.severity === "critical",
  ).length;
  base.kpis.complaintSpikes = findings.filter((item) => item.type === "complaint_spike").length;
  if (filters.from) base.trends = base.trends.filter((point) => point.date >= filters.from!);
  if (filters.to) base.trends = base.trends.filter((point) => point.date <= filters.to!);
  if (filters.product) base.filters.products = [filters.product];
  return base;
}

export const mockdb = {
  health() {
    return clone(healthMock);
  },

  demoGenerate(_payload: DemoRequest): UploadResponse {
    const demo = clone(demoMock as unknown as UploadResponse);
    return { ...demo, datasetId: MOCK_DATASET_ID };
  },

  upload(files: File[]): UploadResponse {
    const demo = clone(demoMock as unknown as UploadResponse);
    const names = files.map((file) => file.name);
    const uploaded = demo.files.map((file, index) => ({
      ...file,
      name: names[index] ?? file.name,
    }));
    return { datasetId: MOCK_DATASET_ID, files: uploaded.length ? uploaded : demo.files };
  },

  mapSchema(payload: MapSchemaRequest): MapSchemaResponse {
    mapping = clone(payload.mapping);
    return { datasetId: MOCK_DATASET_ID, mapping, confirmed: true };
  },

  analyze(): AnalyzeResponse {
    analyzingSince = Date.now();
    return clone(analyzeMock as unknown as AnalyzeResponse);
  },

  progress(): ProgressResponse {
    if (analyzingSince === null) {
      return clone(progressMock as unknown as ProgressResponse);
    }
    const elapsed = Date.now() - analyzingSince;
    const total = 6000;
    if (elapsed >= total) {
      analyzingSince = null;
      return {
        status: "done",
        step: null,
        percent: 100,
        message: "Analysis complete in 6.0s (mock mode).",
      };
    }
    const percent = Math.min(99, Math.round((elapsed / total) * 100));
    const step = STEPS[Math.min(STEPS.length - 1, Math.floor(percent / 20))];
    return {
      status: "running",
      step,
      percent,
      message: `Simulating ${step!.toLowerCase()} (mock mode).`,
    };
  },

  quality(): QualityResponse {
    return clone(qualityMock as unknown as QualityResponse);
  },

  overview(filters: OverviewFilters = {}): OverviewResponse {
    return overviewWithLiveKpis(filters);
  },

  findings(filters: FindingsFilters = {}): Finding[] {
    const search = (filters.search ?? "").trim().toLowerCase();
    return clone(
      findings.filter((finding) => {
        if (filters.type && finding.type !== filters.type) return false;
        if (filters.severity && finding.severity !== filters.severity) return false;
        if (filters.status && finding.status !== filters.status) return false;
        if (search) {
          const haystack = [
            finding.title,
            finding.summary,
            finding.businessImpact,
            finding.recommendation.action,
            ...finding.relatedEntities.products,
            ...finding.relatedEntities.locations,
            ...finding.relatedEntities.couriers,
            ...finding.relatedEntities.orders,
          ]
            .join(" ")
            .toLowerCase();
          if (!haystack.includes(search)) return false;
        }
        return true;
      }),
    ).map((finding) => ({ ...finding, evidenceRows: finding.evidenceRows.slice(0, 5) }));
  },

  finding(id: string): Finding {
    const finding = findings.find((item) => item.id === id);
    if (!finding) throw new Error(`Unknown finding ${id}`);
    return clone(finding);
  },

  decide(id: string, payload: DecisionRequest): Finding {
    const finding = findings.find((item) => item.id === id);
    if (!finding) throw new Error(`Unknown finding ${id}`);
    finding.status = STATUS_BY_DECISION[payload.decision] ?? finding.status;
    const action: ActionLog = {
      id: `act-mock-${Date.now()}`,
      findingId: finding.id,
      findingTitle: finding.title,
      decision: payload.decision,
      note: payload.note,
      actor: "Ops manager",
      at: new Date().toISOString(),
    };
    actions.log = [action, ...actions.log];
    return clone(finding);
  },

  patchStatus(id: string, payload: StatusRequest): Finding {
    const finding = findings.find((item) => item.id === id);
    if (!finding) throw new Error(`Unknown finding ${id}`);
    finding.status = payload.status;
    actions.log = [
      {
        id: `act-mock-${Date.now()}`,
        findingId: finding.id,
        findingTitle: finding.title,
        decision: "status_changed",
        note: `Status changed to ${payload.status}.`,
        actor: "Ops manager",
        at: new Date().toISOString(),
      },
      ...actions.log,
    ];
    return clone(finding);
  },

  createTask(id: string, payload: TaskRequest): InvestigationTask {
    const finding = findings.find((item) => item.id === id);
    if (!finding) throw new Error(`Unknown finding ${id}`);
    const task = clone(taskMock as unknown as InvestigationTask);
    const created: InvestigationTask = {
      ...task,
      id: `task-mock-${Date.now()}`,
      findingId: finding.id,
      title: payload.title,
      status: "open",
      createdAt: new Date().toISOString(),
    };
    actions.tasks = [created, ...actions.tasks];
    actions.log = [
      {
        id: `act-mock-${Date.now()}`,
        findingId: finding.id,
        findingTitle: finding.title,
        decision: "task_created",
        note: payload.title,
        actor: "Ops manager",
        at: created.createdAt,
      },
      ...actions.log,
    ];
    return clone(created);
  },

  actions(): ActionsResponse {
    return clone(actions);
  },

  report(): ReportResponse {
    const report = clone(reportMock as unknown as ReportResponse);
    return { ...report, generatedAt: new Date().toISOString() };
  },
};

// Keep the exported detail fixture referenced so its shape stays validated in dev tools.
export const mockDetailFixture = findingMock;
