"""Pydantic v2 mirrors of the frozen CONTRACT v1.

Every model serialises with camelCase aliases and forbids unknown fields, so a
contract drift fails loudly instead of silently reaching the frontend.
"""

from __future__ import annotations

from typing import Annotated, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


def to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail)


class ContractModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


FileType = Literal["orders", "deliveries", "complaints", "reviews", "inventory", "sales", "unknown"]
Severity = Literal["critical", "high", "medium", "low"]
FindingType = Literal[
    "recurring_issue",
    "anomaly",
    "delivery_risk",
    "inventory_risk",
    "complaint_spike",
]
Status = Literal["open", "investigating", "resolved", "escalated", "rejected"]
Decision = Literal["approve", "reject", "escalate"]
CanonicalField = Literal[
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
]
Priority = Literal["urgent", "high", "normal", "low"]
ProgressStatus = Literal["idle", "running", "done", "error"]
ProgressStep = Literal[
    "Cleaning",
    "Linking datasets",
    "Detecting patterns",
    "Assessing risks",
    "Generating recommendations",
]
RiskGroup = Literal["courier", "warehouse", "city"]
Industry = Literal["fashion", "skincare"]
ActionKind = Literal["approve", "reject", "escalate", "task_created", "status_changed"]

FieldValue = str | int | float | None
Confidence = Annotated[float, Field(ge=0, le=1)]


class FileMapping(ContractModel):
    file_name: str
    file_type: FileType
    fields: Dict[CanonicalField, Optional[str]] = Field(default_factory=dict)
    confidence: Dict[CanonicalField, Confidence] = Field(default_factory=dict)


class SchemaMapping(ContractModel):
    files: List[FileMapping] = Field(default_factory=list)


class UploadedFile(ContractModel):
    name: str
    detected_type: FileType
    rows: int
    columns: List[str] = Field(default_factory=list)
    suggested_mapping: FileMapping


class UploadResponse(ContractModel):
    dataset_id: str
    files: List[UploadedFile] = Field(default_factory=list)


class MapSchemaRequest(ContractModel):
    dataset_id: str
    mapping: SchemaMapping


class MapSchemaResponse(ContractModel):
    dataset_id: str
    mapping: SchemaMapping
    confirmed: Literal[True] = True


class ProgressResponse(ContractModel):
    status: ProgressStatus
    step: Optional[ProgressStep] = None
    percent: float = 0.0
    message: Optional[str] = None


class QualityIssue(ContractModel):
    file: str
    column: Optional[str] = None
    count: int
    row_ids: List[str] = Field(default_factory=list)
    note: str


class QualityResponse(ContractModel):
    missing: List[QualityIssue] = Field(default_factory=list)
    duplicates: List[QualityIssue] = Field(default_factory=list)
    inconsistent: List[QualityIssue] = Field(default_factory=list)
    health_score: float
    summary: str


class VerifiedFact(ContractModel):
    statement: str
    metric: str
    value: str | float | int


class AiHypothesis(ContractModel):
    statement: str
    confidence: float = Field(ge=0, le=1)
    reasoning: str


class EvidenceRow(ContractModel):
    source: str
    row_id: str
    fields: Dict[str, FieldValue] = Field(default_factory=dict)


class RelatedEntities(ContractModel):
    products: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    couriers: List[str] = Field(default_factory=list)
    orders: List[str] = Field(default_factory=list)


class Recommendation(ContractModel):
    action: str
    why: str
    preventive: str
    priority: Priority


class Finding(ContractModel):
    id: str
    title: str
    type: FindingType
    risk_score: float = Field(ge=0, le=100)
    severity: Severity
    business_impact: str
    summary: str
    verified_facts: List[VerifiedFact] = Field(default_factory=list)
    ai_hypotheses: List[AiHypothesis] = Field(default_factory=list)
    evidence_rows: List[EvidenceRow] = Field(default_factory=list)
    related_entities: RelatedEntities
    recommendation: Recommendation
    status: Status
    created_at: str


class Kpis(ContractModel):
    open_issues: int
    critical_risks: int
    orders_at_risk: int
    products_near_stockout: int
    complaint_spikes: int


class TrendPoint(ContractModel):
    date: str
    complaints: int
    anomaly: bool


class CategoryCount(ContractModel):
    category: str
    count: int


class RiskGroupScore(ContractModel):
    group: RiskGroup
    name: str
    risk_score: float


class ProblemProduct(ContractModel):
    product_id: str
    product_name: Optional[str] = None
    complaints: int


class FilterOptions(ContractModel):
    products: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    couriers: List[str] = Field(default_factory=list)
    date_min: Optional[str] = None
    date_max: Optional[str] = None


class OverviewResponse(ContractModel):
    kpis: Kpis
    trends: List[TrendPoint] = Field(default_factory=list)
    category_breakdown: List[CategoryCount] = Field(default_factory=list)
    risk_distribution: List[RiskGroupScore] = Field(default_factory=list)
    top_problem_products: List[ProblemProduct] = Field(default_factory=list)
    filters: FilterOptions


class DecisionRequest(ContractModel):
    decision: Decision
    note: str


class StatusRequest(ContractModel):
    status: Status


class TaskRequest(ContractModel):
    title: str


class ActionLog(ContractModel):
    id: str
    finding_id: str
    finding_title: str
    decision: ActionKind
    note: str
    actor: str
    at: str


class InvestigationTask(ContractModel):
    id: str
    finding_id: str
    title: str
    status: Status
    created_at: str


class ActionsResponse(ContractModel):
    log: List[ActionLog] = Field(default_factory=list)
    tasks: List[InvestigationTask] = Field(default_factory=list)


class ReportResponse(ContractModel):
    markdown: str
    generated_at: str


class DemoRequest(ContractModel):
    industry: Industry


class HealthResponse(ContractModel):
    ok: Literal[True] = True
    contract_version: Literal["1"] = "1"
    llm_mode: Literal["llm", "template"]


class AnalyzeResponse(ContractModel):
    status: Literal["running"] = "running"


class ErrorResponse(ContractModel):
    error: str
    detail: str


DECISION_STATUS: Dict[str, Status] = {
    "approve": "investigating",
    "reject": "rejected",
    "escalate": "escalated",
}
