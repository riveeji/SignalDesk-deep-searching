from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


class ResearchRunStatus(str, Enum):
    QUEUED = "queued"
    CLARIFYING = "clarifying"
    WAITING_HUMAN = "waiting_human"
    PLANNING = "planning"
    RETRIEVING = "retrieving"
    READING = "reading"
    SYNTHESIZING = "synthesizing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    WARNING = "warning"
    FAILED = "failed"


class SourceType(str, Enum):
    GITHUB_REPO = "github_repo"
    README = "readme"
    OFFICIAL_DOC = "official_doc"
    WEB_ARTICLE = "web_article"
    SCHOLAR_PAPER = "scholar_paper"
    ACADEMIC_METADATA = "academic_metadata"
    MANUAL_IMPORT = "manual_import"


class ComparisonTarget(BaseModel):
    name: str
    repo_full_name: str | None = None
    docs_url: str | None = None
    homepage_url: str | None = None
    rationale: str | None = None


class ClarificationRequest(BaseModel):
    questions: list[str] = Field(default_factory=list)
    suggested_targets: list[str] = Field(default_factory=list)
    suggested_dimensions: list[str] = Field(default_factory=list)
    note: str | None = None


class ResearchScope(BaseModel):
    original_question: str
    clarified_question: str
    research_goal: str
    comparison_targets: list[ComparisonTarget] = Field(default_factory=list)
    comparison_dimensions: list[str] = Field(default_factory=list)
    deliverable: str = "Structured technology selection report"
    constraints: list[str] = Field(default_factory=list)
    must_include: list[str] = Field(default_factory=list)
    context: str | None = None
    user_scope_note: str | None = None


class ResearchPlanNode(BaseModel):
    id: str = Field(default_factory=lambda: new_id("plan"))
    run_id: str
    label: str
    description: str
    query: str | None = None
    rationale: str | None = None
    status: StepStatus = StepStatus.PENDING
    depth: int = 0
    parent_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class RunStep(BaseModel):
    id: str = Field(default_factory=lambda: new_id("step"))
    run_id: str
    name: str
    label: str
    status: StepStatus
    summary: str
    tool_name: str | None = None
    prompt_excerpt: str | None = None
    input_summary: str | None = None
    output_summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)


class SourceDocument(BaseModel):
    id: str = Field(default_factory=lambda: new_id("source"))
    run_id: str
    title: str
    url: str
    domain: str
    source_type: SourceType
    summary: str
    snippet: str
    quality_score: float = 0.0
    included: bool = True
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class Citation(BaseModel):
    id: str = Field(default_factory=lambda: new_id("cite"))
    run_id: str
    source_id: str
    section_slug: str
    claim: str
    excerpt: str
    title: str
    url: str
    created_at: datetime = Field(default_factory=utc_now)


class ReportSection(BaseModel):
    slug: str
    title: str
    body: str
    citation_ids: list[str] = Field(default_factory=list)


class TargetCoverage(BaseModel):
    target_name: str
    official_doc_count: int = 0
    repo_signal_count: int = 0
    external_article_count: int = 0
    academic_count: int = 0
    total_sources: int = 0
    average_quality_score: float = 0.0
    missing_buckets: list[str] = Field(default_factory=list)
    evidence_status: str = "missing"
    source_ids: list[str] = Field(default_factory=list)


class CoverageSummary(BaseModel):
    total_sources: int = 0
    target_count: int = 0
    covered_target_count: int = 0
    balanced: bool = False
    source_type_counts: dict[str, int] = Field(default_factory=dict)
    target_coverages: list[TargetCoverage] = Field(default_factory=list)
    missing_targets: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class AnswerQuality(BaseModel):
    verdict: str = "grounded"
    recommendation_confidence: str = "medium"
    question_alignment: str = "aligned"
    issues: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    question_alignment_notes: list[str] = Field(default_factory=list)


class FinalReport(BaseModel):
    run_id: str
    question_restatement: str
    executive_summary: str
    candidate_names: list[str] = Field(default_factory=list)
    comparison_dimensions: list[str] = Field(default_factory=list)
    comparison_table: list[dict[str, str]] = Field(default_factory=list)
    recommendation: str
    risks_and_unknowns: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    sections: list[ReportSection] = Field(default_factory=list)
    verdict: str = "grounded"
    recommendation_confidence: str = "medium"
    missing_evidence: list[str] = Field(default_factory=list)
    question_alignment_notes: list[str] = Field(default_factory=list)
    coverage_summary: CoverageSummary | None = None
    answer_quality: AnswerQuality | None = None
    markdown: str
    created_at: datetime = Field(default_factory=utc_now)


class ResearchRun(BaseModel):
    id: str = Field(default_factory=lambda: new_id("research"))
    title: str
    question: str
    context: str | None = None
    provider_id: str = "heuristic"
    provider_label: str = "启发式回退"
    model_name: str = "heuristic-fallback"
    requested_targets: list[str] = Field(default_factory=list)
    requested_dimensions: list[str] = Field(default_factory=list)
    requested_must_include: list[str] = Field(default_factory=list)
    status: ResearchRunStatus = ResearchRunStatus.QUEUED
    summary: str = "已进入队列。"
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    latest_error: str | None = None
    scope: ResearchScope | None = None
    clarification_request: ClarificationRequest | None = None
    target_count: int = 0
    source_count: int = 0
    citation_count: int = 0
    report_ready: bool = False
    coverage_summary: CoverageSummary | None = None
    last_completed_step: str | None = None


class ResearchRunDetail(BaseModel):
    run: ResearchRun
    plan_nodes: list[ResearchPlanNode] = Field(default_factory=list)


class CreateResearchRunRequest(BaseModel):
    question: str
    title: str | None = None
    context: str | None = None
    provider_id: str | None = None
    comparison_targets: list[str] | None = None
    comparison_dimensions: list[str] | None = None
    must_include: list[str] | None = None


class ClarifyResearchRunRequest(BaseModel):
    scope_note: str | None = None
    selected_targets: list[str] | None = None
    comparison_dimensions: list[str] | None = None


class RetryStepRequest(BaseModel):
    step_name: str | None = None


class SourceToggleRequest(BaseModel):
    include: bool


class ManualSourceImportRequest(BaseModel):
    target_name: str | None = None
    title: str | None = None
    url: str | None = None
    doi: str | None = None
    bibtex: str | None = None
    note: str | None = None
    include: bool = True


class ProviderOption(BaseModel):
    id: str
    label: str
    vendor: str
    kind: str
    enabled: bool
    model: str | None = None
    base_url: str | None = None
    is_default: bool = False


class SearchProviderStatus(BaseModel):
    id: str
    label: str
    kind: str
    enabled: bool
    note: str | None = None


class HealthResponse(BaseModel):
    status: str
    database: str
    provider: str
    language: str
    model: str
    temperature: float
    web_results_per_target: int
    report_audience: str
    providers: list[ProviderOption] = Field(default_factory=list)
    search_providers: list[SearchProviderStatus] = Field(default_factory=list)


class WorkspaceResponse(BaseModel):
    runs: list[ResearchRun]
    sample_questions: list[str]
