import type { ResearchRunStatus, RunStep, SourceType } from "@/lib/types";

export function statusLabel(status: ResearchRunStatus): string {
  return {
    queued: "排队中",
    clarifying: "澄清中",
    waiting_human: "等待补充",
    planning: "规划中",
    retrieving: "检索中",
    reading: "阅读中",
    synthesizing: "综合中",
    succeeded: "已完成",
    failed: "失败",
    cancelled: "已取消",
  }[status];
}

export function stepStatusLabel(status: RunStep["status"]): string {
  return {
    pending: "待执行",
    running: "执行中",
    succeeded: "成功",
    warning: "需关注",
    failed: "失败",
  }[status];
}

export function stageNameLabel(name: string): string {
  return {
    clarify: "澄清",
    planning: "规划",
    retrieving: "检索",
    reading: "阅读",
    synthesizing: "综合",
    error: "异常",
  }[name] ?? name;
}

export function sourceTypeLabel(sourceType: SourceType): string {
  return {
    github_repo: "GitHub 仓库",
    readme: "README",
    official_doc: "官方文档",
    web_article: "网页资料",
    scholar_paper: "学术论文",
    academic_metadata: "学术元数据",
    manual_import: "手动导入",
  }[sourceType];
}

export function providerLabel(provider: string): string {
  return {
    heuristic: "启发式回退",
    deepseek: "DeepSeek",
    "openai-compatible": "兼容接口",
  }[provider] ?? provider;
}

export function verdictLabel(verdict: string): string {
  return {
    grounded: "可支撑结论",
    insufficient_evidence: "证据不足",
    needs_clarification: "需要继续澄清",
  }[verdict] ?? verdict;
}

export function confidenceLabel(confidence: string): string {
  return {
    high: "高",
    medium: "中",
    low: "低",
  }[confidence] ?? confidence;
}

export function alignmentLabel(alignment: string): string {
  return {
    aligned: "对题",
    partially_aligned: "部分对题",
    needs_review: "可能偏题",
  }[alignment] ?? alignment;
}

export function evidenceStatusLabel(status: string): string {
  return {
    complete: "覆盖完整",
    partial: "覆盖不完整",
    missing: "几乎无有效证据",
  }[status] ?? status;
}

export function coverageBucketLabel(bucket: string): string {
  return {
    official_doc: "官方文档",
    repo_signal: "仓库信号",
    external_validation: "外部或学术验证",
  }[bucket] ?? bucket;
}
