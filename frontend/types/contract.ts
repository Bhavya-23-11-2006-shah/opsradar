// CONTRACT v1 (FROZEN). Do not rename, add or remove fields.

export type FileType =
  | "orders"
  | "deliveries"
  | "complaints"
  | "reviews"
  | "inventory"
  | "sales"
  | "unknown";

export type Severity = "critical" | "high" | "medium" | "low";

export type FindingType =
  | "recurring_issue"
  | "anomaly"
  | "delivery_risk"
  | "inventory_risk"
  | "complaint_spike";

export type Status = "open" | "investigating" | "resolved" | "escalated" | "rejected";

export type Decision = "approve" | "reject" | "escalate";

export type CanonicalField =
  | "orderId"
  | "productId"
  | "customerId"
  | "date"
  | "promisedDate"
  | "deliveredDate"
  | "shippedDate"
  | "warehouse"
  | "city"
  | "courier"
  | "status"
  | "complaintText"
  | "category"
  | "stock"
  | "dailySalesRate"
  | "reorderLevel"
  | "quantity"
  | "amount"
  | "productName"
  | "rating";

export interface FileMapping {
  fileName: string;
  fileType: FileType;
  fields: Partial<Record<CanonicalField, string | null>>;
  confidence: Partial<Record<CanonicalField, number>>;
}

export interface SchemaMapping {
  files: FileMapping[];
}

export interface UploadedFileInfo {
  name: string;
  detectedType: FileType;
  rows: number;
  columns: string[];
  suggestedMapping: FileMapping;
}

export interface UploadResponse {
  datasetId: string;
  files: UploadedFileInfo[];
}

export interface MapSchemaRequest {
  datasetId: string;
  mapping: SchemaMapping;
}

export interface MapSchemaResponse {
  datasetId: string;
  mapping: SchemaMapping;
  confirmed: true;
}

export interface ProgressResponse {
  status: "idle" | "running" | "done" | "error";
  step:
    | "Cleaning"
    | "Linking datasets"
    | "Detecting patterns"
    | "Assessing risks"
    | "Generating recommendations"
    | null;
  percent: number;
  message: string | null;
}

export interface QualityIssue {
  file: string;
  column: string | null;
  count: number;
  rowIds: string[];
  note: string;
}

export interface QualityResponse {
  missing: QualityIssue[];
  duplicates: QualityIssue[];
  inconsistent: QualityIssue[];
  healthScore: number;
  summary: string;
}

export interface VerifiedFact {
  statement: string;
  metric: string;
  value: number | string;
}

export interface AiHypothesis {
  statement: string;
  confidence: number;
  reasoning: string;
}

export interface EvidenceRow {
  source: string;
  rowId: string;
  fields: Record<string, string | number | null>;
}

export interface Finding {
  id: string;
  title: string;
  type: FindingType;
  riskScore: number;
  severity: Severity;
  businessImpact: string;
  summary: string;
  verifiedFacts: VerifiedFact[];
  aiHypotheses: AiHypothesis[];
  evidenceRows: EvidenceRow[];
  relatedEntities: {
    products: string[];
    locations: string[];
    couriers: string[];
    orders: string[];
  };
  recommendation: {
    action: string;
    why: string;
    preventive: string;
    priority: "urgent" | "high" | "normal" | "low";
  };
  status: Status;
  createdAt: string;
}

export interface OverviewResponse {
  kpis: {
    openIssues: number;
    criticalRisks: number;
    ordersAtRisk: number;
    productsNearStockout: number;
    complaintSpikes: number;
  };
  trends: { date: string; complaints: number; anomaly: boolean }[];
  categoryBreakdown: { category: string; count: number }[];
  riskDistribution: { group: "courier" | "warehouse" | "city"; name: string; riskScore: number }[];
  topProblemProducts: { productId: string; productName: string | null; complaints: number }[];
  filters: {
    products: string[];
    locations: string[];
    couriers: string[];
    dateMin: string | null;
    dateMax: string | null;
  };
}

export interface DecisionRequest {
  decision: Decision;
  note: string;
}

export interface StatusRequest {
  status: Status;
}

export interface TaskRequest {
  title: string;
}

export interface ActionLog {
  id: string;
  findingId: string;
  findingTitle: string;
  decision: Decision | "task_created" | "status_changed";
  note: string;
  actor: string;
  at: string;
}

export interface InvestigationTask {
  id: string;
  findingId: string;
  title: string;
  status: Status;
  createdAt: string;
}

export interface ActionsResponse {
  log: ActionLog[];
  tasks: InvestigationTask[];
}

export interface ReportResponse {
  markdown: string;
  generatedAt: string;
}

export interface DemoRequest {
  industry: "fashion" | "skincare";
}

export interface HealthResponse {
  ok: true;
  contractVersion: "1";
  llmMode: "llm" | "template";
}

export interface AnalyzeResponse {
  status: "running";
}

export interface OverviewFilters {
  from?: string;
  to?: string;
  product?: string;
  location?: string;
  courier?: string;
}

export interface FindingsFilters {
  type?: FindingType | "";
  severity?: Severity | "";
  status?: Status | "";
  search?: string;
}

export interface ApiErrorBody {
  error: string;
  detail: string;
}
