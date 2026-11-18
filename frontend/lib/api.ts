"use client";

import type { ZodTypeAny } from "zod";

import { mockdb } from "@/lib/mockdb";
import { normalizePayload } from "@/lib/normalize";
import {
  actionsResponseSchema,
  analyzeResponseSchema,
  findingSchema,
  findingsListSchema,
  healthResponseSchema,
  investigationTaskSchema,
  mapSchemaResponseSchema,
  overviewResponseSchema,
  progressResponseSchema,
  qualityResponseSchema,
  reportResponseSchema,
  uploadResponseSchema,
} from "@/lib/schemas";
import { toast } from "@/lib/toast";
import type {
  ActionsResponse,
  AnalyzeResponse,
  DecisionRequest,
  DemoRequest,
  Finding,
  FindingsFilters,
  HealthResponse,
  InvestigationTask,
  MapSchemaRequest,
  MapSchemaResponse,
  OverviewFilters,
  OverviewResponse,
  ProgressResponse,
  QualityResponse,
  ReportResponse,
  SchemaMapping,
  StatusRequest,
  TaskRequest,
  UploadResponse,
} from "@/types/contract";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === "true";

export class ContractError extends Error {
  constructor(
    public endpoint: string,
    public issues: string[],
  ) {
    super(`Contract mismatch on ${endpoint}`);
    this.name = "ContractError";
  }
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

function validate<T>(endpoint: string, schema: ZodTypeAny, payload: unknown): T {
  const normalized = normalizePayload(schema, payload);
  const parsed = schema.safeParse(normalized);
  if (!parsed.success) {
    const issues = parsed.error.issues.map(
      (issue) => `${issue.path.join(".") || "<root>"}: ${issue.message}`,
    );
    // eslint-disable-next-line no-console
    console.error(`Contract mismatch on ${endpoint}`, issues, payload);
    toast(`Contract mismatch on ${endpoint}`, "error");
    throw new ContractError(endpoint, issues);
  }
  return parsed.data as T;
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

async function request<T>(
  endpoint: string,
  schema: ZodTypeAny,
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(init.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(init.headers ?? {}),
    },
    cache: "no-store",
  });
  const payload = await readJson(response);
  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? String((payload as { detail: unknown }).detail)
        : `HTTP ${response.status}`;
    toast(`Request failed: ${endpoint}`, "error");
    throw new ApiError(response.status, detail);
  }
  return validate<T>(endpoint, schema, payload);
}

async function mockResponse<T>(
  endpoint: string,
  schema: ZodTypeAny,
  loader: () => unknown,
): Promise<T> {
  await new Promise((resolve) => setTimeout(resolve, 120));
  return validate<T>(endpoint, schema, loader());
}

function query(params: Record<string, string | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, value);
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const api = {
  health(): Promise<HealthResponse> {
    if (USE_MOCK) return mockResponse("GET /api/health", healthResponseSchema, () => mockdb.health());
    return request("GET /api/health", healthResponseSchema, "/api/health");
  },

  demoGenerate(payload: DemoRequest): Promise<UploadResponse> {
    if (USE_MOCK) {
      return mockResponse("POST /api/demo/generate", uploadResponseSchema, () =>
        mockdb.demoGenerate(payload),
      );
    }
    return request("POST /api/demo/generate", uploadResponseSchema, "/api/demo/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  upload(files: File[]): Promise<UploadResponse> {
    const form = new FormData();
    for (const file of files) form.append("files", file, file.name);
    if (USE_MOCK) {
      return mockResponse("POST /api/upload", uploadResponseSchema, () => mockdb.upload(files));
    }
    return request("POST /api/upload", uploadResponseSchema, "/api/upload", {
      method: "POST",
      body: form,
    });
  },

  mapSchema(datasetId: string, mapping: SchemaMapping): Promise<MapSchemaResponse> {
    const payload: MapSchemaRequest = { datasetId, mapping };
    if (USE_MOCK) {
      return mockResponse("POST /api/map-schema", mapSchemaResponseSchema, () =>
        mockdb.mapSchema(payload),
      );
    }
    return request("POST /api/map-schema", mapSchemaResponseSchema, "/api/map-schema", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  analyze(datasetId: string): Promise<AnalyzeResponse> {
    if (USE_MOCK) {
      return mockResponse("POST /api/analyze", analyzeResponseSchema, () => mockdb.analyze());
    }
    return request(
      "POST /api/analyze",
      analyzeResponseSchema,
      `/api/analyze/${encodeURIComponent(datasetId)}`,
      { method: "POST" },
    );
  },

  progress(datasetId: string): Promise<ProgressResponse> {
    if (USE_MOCK) {
      return mockResponse("GET /api/progress", progressResponseSchema, () => mockdb.progress());
    }
    return request(
      "GET /api/progress",
      progressResponseSchema,
      `/api/progress/${encodeURIComponent(datasetId)}`,
    );
  },

  quality(datasetId: string): Promise<QualityResponse> {
    if (USE_MOCK) {
      return mockResponse("GET /api/quality", qualityResponseSchema, () => mockdb.quality());
    }
    return request(
      "GET /api/quality",
      qualityResponseSchema,
      `/api/quality/${encodeURIComponent(datasetId)}`,
    );
  },

  overview(datasetId: string, filters: OverviewFilters = {}): Promise<OverviewResponse> {
    if (USE_MOCK) {
      return mockResponse("GET /api/overview", overviewResponseSchema, () => mockdb.overview(filters));
    }
    return request(
      "GET /api/overview",
      overviewResponseSchema,
      `/api/overview/${encodeURIComponent(datasetId)}${query({
        from: filters.from,
        to: filters.to,
        product: filters.product,
        location: filters.location,
        courier: filters.courier,
      })}`,
    );
  },

  findings(datasetId: string, filters: FindingsFilters = {}): Promise<Finding[]> {
    if (USE_MOCK) {
      return mockResponse("GET /api/findings", findingsListSchema, () => mockdb.findings(filters));
    }
    return request(
      "GET /api/findings",
      findingsListSchema,
      `/api/findings/${encodeURIComponent(datasetId)}${query({
        type: filters.type,
        severity: filters.severity,
        status: filters.status,
        search: filters.search,
      })}`,
    );
  },

  finding(datasetId: string, findingId: string): Promise<Finding> {
    if (USE_MOCK) {
      return mockResponse("GET /api/findings/:findingId", findingSchema, () =>
        mockdb.finding(findingId),
      );
    }
    return request(
      "GET /api/findings/:findingId",
      findingSchema,
      `/api/findings/${encodeURIComponent(datasetId)}/${encodeURIComponent(findingId)}`,
    );
  },

  decide(datasetId: string, findingId: string, payload: DecisionRequest): Promise<Finding> {
    if (USE_MOCK) {
      return mockResponse("POST /api/findings/:findingId/decision", findingSchema, () =>
        mockdb.decide(findingId, payload),
      );
    }
    return request(
      "POST /api/findings/:findingId/decision",
      findingSchema,
      `/api/findings/${encodeURIComponent(datasetId)}/${encodeURIComponent(findingId)}/decision`,
      { method: "POST", body: JSON.stringify(payload) },
    );
  },

  patchStatus(datasetId: string, findingId: string, payload: StatusRequest): Promise<Finding> {
    if (USE_MOCK) {
      return mockResponse("PATCH /api/findings/:findingId/status", findingSchema, () =>
        mockdb.patchStatus(findingId, payload),
      );
    }
    return request(
      "PATCH /api/findings/:findingId/status",
      findingSchema,
      `/api/findings/${encodeURIComponent(datasetId)}/${encodeURIComponent(findingId)}/status`,
      { method: "PATCH", body: JSON.stringify(payload) },
    );
  },

  createTask(datasetId: string, findingId: string, payload: TaskRequest): Promise<InvestigationTask> {
    if (USE_MOCK) {
      return mockResponse("POST /api/findings/:findingId/task", investigationTaskSchema, () =>
        mockdb.createTask(findingId, payload),
      );
    }
    return request(
      "POST /api/findings/:findingId/task",
      investigationTaskSchema,
      `/api/findings/${encodeURIComponent(datasetId)}/${encodeURIComponent(findingId)}/task`,
      { method: "POST", body: JSON.stringify(payload) },
    );
  },

  actions(datasetId: string): Promise<ActionsResponse> {
    if (USE_MOCK) {
      return mockResponse("GET /api/actions", actionsResponseSchema, () => mockdb.actions());
    }
    return request(
      "GET /api/actions",
      actionsResponseSchema,
      `/api/actions/${encodeURIComponent(datasetId)}`,
    );
  },

  report(datasetId: string): Promise<ReportResponse> {
    if (USE_MOCK) {
      return mockResponse("POST /api/report", reportResponseSchema, () => mockdb.report());
    }
    return request(
      "POST /api/report",
      reportResponseSchema,
      `/api/report/${encodeURIComponent(datasetId)}`,
      { method: "POST" },
    );
  },
};
