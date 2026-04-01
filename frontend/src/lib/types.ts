export type ResearchRunStatus =
  | "queued"
  | "clarifying"
  | "waiting_human"
  | "planning"
  | "retrieving"
  | "reading"
  | "synthesizing"
  | "succeeded"
  | "failed"
  | "cancelled";

export type StepStatus = "pending" | "running" | "succeeded" | "warning" | "failed";

export type ComparisonTarget = {
  name: string;
  repo_full_name?: string | null;
  docs_url?: string | null;
  homepage_url?: string | null;
  rationale?: string | null;
};

export type ClarificationRequest = {
  questions: string[];
  suggested_targets: string[];
  suggested_dimensions: string[];
  note?: string | null;
};

export type ResearchScope = {
  original_question: string;
  clarified_question: string;
  research_goal: string;
  comparison_targets: ComparisonTarget[];
  comparison_dimensions: string[];
  deliverable: string;
  constraints: string[];
  must_include: string[];
  context?: string | null;
  user_scope_note?: string | null;
};

export type TargetCoverage = {
  target_name: string;
  official_doc_count: number;
  repo_signal_count: number;
  external_article_count: number;
  academic_count: number;
  total_sources: number;
  average_quality_score: number;
  missing_buckets: string[];
  evidence_status: string;
  source_ids: string[];
};

export type CoverageSummary = {
  total_sources: number;
  target_count: number;
  covered_target_count: number;
  balanced: boolean;
  source_type_counts: Record<string, number>;
  target_coverages: TargetCoverage[];
  missing_targets: string[];
  notes: string[];
};

export type AnswerQuality = {
  verdict: string;
  recommendation_confidence: string;
  question_alignment: string;
  issues: string[];
  notes: string[];
  missing_evidence: string[];
  question_alignment_notes: string[];
};

export type ResearchRun = {
  id: string;
  title: string;
  question: string;
  context?: string | null;
  provider_id: string;
  provider_label: string;
  model_name: string;
  requested_targets: string[];
  requested_dimensions: string[];
  requested_must_include: string[];
  status: ResearchRunStatus;
  summary: string;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  latest_error?: string | null;
  scope?: ResearchScope | null;
  clarification_request?: ClarificationRequest | null;
  target_count: number;
  source_count: number;
  citation_count: number;
  report_ready: boolean;
  coverage_summary?: CoverageSummary | null;
  last_completed_step?: string | null;
};

export type ResearchPlanNode = {
  id: string;
  run_id: string;
  label: string;
  description: string;
  query?: string | null;
  rationale?: string | null;
  status: StepStatus;
  depth: number;
  parent_id?: string | null;
  created_at: string;
};

export type RunStep = {
  id: string;
  run_id: string;
  name: string;
  label: string;
  status: StepStatus;
  summary: string;
  tool_name?: string | null;
  prompt_excerpt?: string | null;
  input_summary?: string | null;
  output_summary?: string | null;
  metadata: Record<string, string | number | boolean | null>;
  started_at: string;
  finished_at?: string | null;
  created_at: string;
};

export type SourceType =
  | "github_repo"
  | "readme"
  | "official_doc"
  | "web_article"
  | "scholar_paper"
  | "academic_metadata"
  | "manual_import";

export type SourceDocument = {
  id: string;
  run_id: string;
  title: string;
  url: string;
  domain: string;
  source_type: SourceType;
  summary: string;
  snippet: string;
  quality_score: number;
  included: boolean;
  tags: string[];
  metadata: Record<string, string | number | boolean | string[] | null>;
  created_at: string;
};

export type Citation = {
  id: string;
  run_id: string;
  source_id: string;
  section_slug: string;
  claim: string;
  excerpt: string;
  title: string;
  url: string;
  created_at: string;
};

export type ReportSection = {
  slug: string;
  title: string;
  body: string;
  citation_ids: string[];
};

export type FinalReport = {
  run_id: string;
  question_restatement: string;
  executive_summary: string;
  candidate_names: string[];
  comparison_dimensions: string[];
  comparison_table: Array<Record<string, string>>;
  recommendation: string;
  risks_and_unknowns: string[];
  open_questions: string[];
  sections: ReportSection[];
  verdict?: string;
  recommendation_confidence?: string;
  missing_evidence?: string[];
  question_alignment_notes?: string[];
  coverage_summary?: CoverageSummary | null;
  answer_quality?: AnswerQuality | null;
  markdown: string;
  created_at: string;
};

export type WorkspacePayload = {
  runs: ResearchRun[];
  sample_questions: string[];
};

export type ResearchRunDetailResponse = {
  run: ResearchRun;
  plan_nodes: ResearchPlanNode[];
};

export type ReportResponse = {
  report: FinalReport;
  citations: Citation[];
};

export type ProviderOption = {
  id: string;
  label: string;
  vendor: string;
  kind: string;
  enabled: boolean;
  model?: string | null;
  base_url?: string | null;
  is_default: boolean;
};

export type SearchProviderStatus = {
  id: string;
  label: string;
  kind: string;
  enabled: boolean;
  note?: string | null;
};

export type ManualSourceImportRequest = {
  target_name?: string | null;
  title?: string | null;
  url?: string | null;
  doi?: string | null;
  bibtex?: string | null;
  note?: string | null;
  include?: boolean;
};

export type HealthResponse = {
  status: string;
  database: string;
  provider: string;
  language: string;
  model: string;
  temperature: number;
  web_results_per_target: number;
  report_audience: string;
  providers: ProviderOption[];
  search_providers: SearchProviderStatus[];
};
