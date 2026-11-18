import { z } from "zod";

export const fileTypeSchema = z.enum([
  "orders",
  "deliveries",
  "complaints",
  "reviews",
  "inventory",
  "sales",
  "unknown",
]);

export const severitySchema = z.enum(["critical", "high", "medium", "low"]);

export const findingTypeSchema = z.enum([
  "recurring_issue",
  "anomaly",
  "delivery_risk",
  "inventory_risk",
  "complaint_spike",
]);

export const statusSchema = z.enum([
  "open",
  "investigating",
  "resolved",
  "escalated",
  "rejected",
]);

export const decisionSchema = z.enum(["approve", "reject", "escalate"]);

export const prioritySchema = z.enum(["urgent", "high", "normal", "low"]);

export const canonicalFieldSchema = z.enum([
  "orderId",
  "productId",
  "customerId",
  "date",
  "promisedDate",
  "deliveredDate",
  "shippedDate",
  "warehouse",
  "city",
  "courier",
  "status",
  "complaintText",
  "category",
  "stock",
  "dailySalesRate",
  "reorderLevel",
  "quantity",
  "amount",
  "productName",
  "rating",
]);

export const fileMappingSchema = z
  .object({
    fileName: z.string(),
    fileType: fileTypeSchema,
    fields: z.record(canonicalFieldSchema, z.string().nullable()),
    confidence: z.record(canonicalFieldSchema, z.number().min(0).max(1)),
  })
  .strict();

export const schemaMappingSchema = z
  .object({
    files: z.array(fileMappingSchema),
  })
  .strict();

export const uploadedFileInfoSchema = z
  .object({
    name: z.string(),
    detectedType: fileTypeSchema,
    rows: z.number().int(),
    columns: z.array(z.string()),
    suggestedMapping: fileMappingSchema,
  })
  .strict();

export const uploadResponseSchema = z
  .object({
    datasetId: z.string(),
    files: z.array(uploadedFileInfoSchema),
  })
  .strict();

export const mapSchemaResponseSchema = z
  .object({
    datasetId: z.string(),
    mapping: schemaMappingSchema,
    confirmed: z.literal(true),
  })
  .strict();

export const progressResponseSchema = z
  .object({
    status: z.enum(["idle", "running", "done", "error"]),
    step: z
      .enum([
        "Cleaning",
        "Linking datasets",
        "Detecting patterns",
        "Assessing risks",
        "Generating recommendations",
      ])
      .nullable(),
    percent: z.number(),
    message: z.string().nullable(),
  })
  .strict();

export const qualityIssueSchema = z
  .object({
    file: z.string(),
    column: z.string().nullable(),
    count: z.number(),
    rowIds: z.array(z.string()),
    note: z.string(),
  })
  .strict();

export const qualityResponseSchema = z
  .object({
    missing: z.array(qualityIssueSchema),
    duplicates: z.array(qualityIssueSchema),
    inconsistent: z.array(qualityIssueSchema),
    healthScore: z.number(),
    summary: z.string(),
  })
  .strict();

export const verifiedFactSchema = z
  .object({
    statement: z.string(),
    metric: z.string(),
    value: z.union([z.number(), z.string()]),
  })
  .strict();

export const aiHypothesisSchema = z
  .object({
    statement: z.string(),
    confidence: z.number().min(0).max(1),
    reasoning: z.string(),
  })
  .strict();

export const evidenceRowSchema = z
  .object({
    source: z.string(),
    rowId: z.string(),
    fields: z.record(z.string(), z.union([z.string(), z.number(), z.null()])),
  })
  .strict();

export const relatedEntitiesSchema = z
  .object({
    products: z.array(z.string()),
    locations: z.array(z.string()),
    couriers: z.array(z.string()),
    orders: z.array(z.string()),
  })
  .strict();

export const recommendationSchema = z
  .object({
    action: z.string(),
    why: z.string(),
    preventive: z.string(),
    priority: prioritySchema,
  })
  .strict();

export const findingSchema = z
  .object({
    id: z.string(),
    title: z.string(),
    type: findingTypeSchema,
    riskScore: z.number().min(0).max(100),
    severity: severitySchema,
    businessImpact: z.string(),
    summary: z.string(),
    verifiedFacts: z.array(verifiedFactSchema),
    aiHypotheses: z.array(aiHypothesisSchema),
    evidenceRows: z.array(evidenceRowSchema),
    relatedEntities: relatedEntitiesSchema,
    recommendation: recommendationSchema,
    status: statusSchema,
    createdAt: z.string(),
  })
  .strict();

export const findingsListSchema = z.array(findingSchema);

export const kpisSchema = z
  .object({
    openIssues: z.number(),
    criticalRisks: z.number(),
    ordersAtRisk: z.number(),
    productsNearStockout: z.number(),
    complaintSpikes: z.number(),
  })
  .strict();

export const overviewResponseSchema = z
  .object({
    kpis: kpisSchema,
    trends: z.array(
      z
        .object({
          date: z.string(),
          complaints: z.number(),
          anomaly: z.boolean(),
        })
        .strict(),
    ),
    categoryBreakdown: z.array(
      z
        .object({
          category: z.string(),
          count: z.number(),
        })
        .strict(),
    ),
    riskDistribution: z.array(
      z
        .object({
          group: z.enum(["courier", "warehouse", "city"]),
          name: z.string(),
          riskScore: z.number(),
        })
        .strict(),
    ),
    topProblemProducts: z.array(
      z
        .object({
          productId: z.string(),
          productName: z.string().nullable(),
          complaints: z.number(),
        })
        .strict(),
    ),
    filters: z
      .object({
        products: z.array(z.string()),
        locations: z.array(z.string()),
        couriers: z.array(z.string()),
        dateMin: z.string().nullable(),
        dateMax: z.string().nullable(),
      })
      .strict(),
  })
  .strict();

export const actionLogSchema = z
  .object({
    id: z.string(),
    findingId: z.string(),
    findingTitle: z.string(),
    decision: z.enum(["approve", "reject", "escalate", "task_created", "status_changed"]),
    note: z.string(),
    actor: z.string(),
    at: z.string(),
  })
  .strict();

export const investigationTaskSchema = z
  .object({
    id: z.string(),
    findingId: z.string(),
    title: z.string(),
    status: statusSchema,
    createdAt: z.string(),
  })
  .strict();

export const actionsResponseSchema = z
  .object({
    log: z.array(actionLogSchema),
    tasks: z.array(investigationTaskSchema),
  })
  .strict();

export const reportResponseSchema = z
  .object({
    markdown: z.string(),
    generatedAt: z.string(),
  })
  .strict();

export const healthResponseSchema = z
  .object({
    ok: z.literal(true),
    contractVersion: z.literal("1"),
    llmMode: z.enum(["llm", "template"]),
  })
  .strict();

export const analyzeResponseSchema = z
  .object({
    status: z.literal("running"),
  })
  .strict();

export const apiErrorBodySchema = z
  .object({
    error: z.string(),
    detail: z.string(),
  })
  .strict();

export const mapSchemaRequestSchema = z
  .object({
    datasetId: z.string(),
    mapping: schemaMappingSchema,
  })
  .strict();

export const decisionRequestSchema = z
  .object({
    decision: decisionSchema,
    note: z.string(),
  })
  .strict();

export const statusRequestSchema = z
  .object({
    status: statusSchema,
  })
  .strict();

export const taskRequestSchema = z
  .object({
    title: z.string(),
  })
  .strict();

export const demoRequestSchema = z
  .object({
    industry: z.enum(["fashion", "skincare"]),
  })
  .strict();
