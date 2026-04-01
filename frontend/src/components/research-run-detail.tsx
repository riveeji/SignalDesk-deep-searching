"use client";

import Link from "next/link";
import { useDeferredValue, useEffect, useState, useTransition } from "react";

import { BrandMark } from "@/components/brand-mark";
import { ResearchRunVisuals } from "@/components/research-run-visuals";
import { API_BASE, splitCsvLike } from "@/lib/api";
import {
  coverageBucketLabel,
  evidenceStatusLabel,
  sourceTypeLabel,
  stageNameLabel,
  statusLabel,
  stepStatusLabel,
} from "@/lib/i18n";
import type { ResearchPlanNode, ResearchRunDetailResponse, RunStep, SourceDocument } from "@/lib/types";

type ResearchRunDetailProps = {
  runId: string;
};

const DEFAULT_SCOPE_NOTE = "优先关注中文推理质量、上下文长度、接入复杂度、成本和稳定性。";
const DEFAULT_TARGETS = "";
const DEFAULT_DIMENSIONS = "";

export function ResearchRunDetail({ runId }: ResearchRunDetailProps) {
  const [detail, setDetail] = useState<ResearchRunDetailResponse | null>(null);
  const [steps, setSteps] = useState<RunStep[]>([]);
  const [sources, setSources] = useState<SourceDocument[]>([]);
  const [scopeNote, setScopeNote] = useState(DEFAULT_SCOPE_NOTE);
  const [selectedTargets, setSelectedTargets] = useState(DEFAULT_TARGETS);
  const [selectedDimensions, setSelectedDimensions] = useState(DEFAULT_DIMENSIONS);
  const [manualSourceInput, setManualSourceInput] = useState("");
  const [manualTargetName, setManualTargetName] = useState("");
  const [manualSourceNote, setManualSourceNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const deferredSteps = useDeferredValue(steps);

  useEffect(() => {
    async function refresh() {
      try {
        const [detailResponse, stepResponse, sourceResponse] = await Promise.all([
          fetch(`${API_BASE}/research-runs/${runId}`, { cache: "no-store" }),
          fetch(`${API_BASE}/research-runs/${runId}/steps`, { cache: "no-store" }),
          fetch(`${API_BASE}/research-runs/${runId}/sources`, { cache: "no-store" }),
        ]);

        if (!detailResponse.ok) {
          throw new Error("获取研究任务详情失败。");
        }
        setDetail((await detailResponse.json()) as ResearchRunDetailResponse);
        setSteps(stepResponse.ok ? ((await stepResponse.json()) as RunStep[]) : []);
        setSources(sourceResponse.ok ? ((await sourceResponse.json()) as SourceDocument[]) : []);
      } catch (fetchError) {
        setError(fetchError instanceof Error ? fetchError.message : "研究任务加载失败。");
      }
    }

    void refresh();
    const timer = window.setInterval(() => {
      void refresh();
    }, 4000);
    return () => window.clearInterval(timer);
  }, [runId]);

  useEffect(() => {
    const clarification = detail?.run.clarification_request;
    if (clarification) {
      if (clarification.suggested_targets.length) {
        setSelectedTargets(clarification.suggested_targets.join(", "));
      }
      if (clarification.suggested_dimensions.length) {
        setSelectedDimensions(clarification.suggested_dimensions.join(", "));
      }
      return;
    }

    const scope = detail?.run.scope;
    if (scope) {
      setSelectedTargets(scope.comparison_targets.map((target) => target.name).join(", "));
      setSelectedDimensions(scope.comparison_dimensions.join(", "));
    }
  }, [detail]);

  function submitClarification() {
    startTransition(async () => {
      setError(null);
      const response = await fetch(`${API_BASE}/research-runs/${runId}/clarify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scope_note: scopeNote,
          selected_targets: splitCsvLike(selectedTargets),
          comparison_dimensions: splitCsvLike(selectedDimensions),
        }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { detail?: string };
        setError(payload.detail ?? "提交补充范围失败。");
      }
    });
  }

  function retryStep(stepName: string) {
    startTransition(async () => {
      setError(null);
      const response = await fetch(`${API_BASE}/research-runs/${runId}/retry-step`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ step_name: stepName }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { detail?: string };
        setError(payload.detail ?? "重试阶段失败。");
      }
    });
  }

  function cancelRun() {
    startTransition(async () => {
      setError(null);
      const response = await fetch(`${API_BASE}/research-runs/${runId}/cancel`, {
        method: "POST",
      });
      if (!response.ok) {
        setError("取消任务失败。");
      }
    });
  }

  function toggleSource(sourceId: string, include: boolean) {
    startTransition(async () => {
      setError(null);
      const response = await fetch(`${API_BASE}/research-runs/${runId}/sources/${sourceId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ include }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { detail?: string };
        setError(payload.detail ?? "更新来源状态失败。");
      }
    });
  }

  function importManualSource() {
    startTransition(async () => {
      setError(null);
      const raw = manualSourceInput.trim();
      if (!raw) {
        setError("请先输入 URL、DOI、BibTeX 或标题。");
        return;
      }
      const payload = buildManualSourcePayload(raw, manualTargetName.trim(), manualSourceNote.trim());
      const response = await fetch(`${API_BASE}/research-runs/${runId}/sources/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { detail?: string };
        setError(payload.detail ?? "导入来源失败。");
        return;
      }
      setManualSourceInput("");
      setManualSourceNote("");
    });
  }

  const run = detail?.run;
  const retryBaseStep = run?.last_completed_step === "synthesizing" ? "synthesizing" : "retrieving";
  const canRetryStages = Boolean(run?.scope) && run?.status !== "waiting_human" && run?.status !== "clarifying";

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 px-5 py-8 lg:px-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-4">
          <BrandMark href="/" compact />
          <div>
            <Link href="/" className="font-mono text-xs uppercase tracking-[0.22em] text-[var(--muted)]">
              返回研究工作台
            </Link>
            <h1 className="mt-3 max-w-4xl text-4xl font-semibold text-white">{run?.title ?? runId}</h1>
            <p className="mt-2 text-sm leading-6 text-[var(--muted)]">{run?.summary ?? "正在加载任务..."}</p>
            {run ? (
              <p className="mt-2 text-xs text-[var(--accent-soft)]">
                {run.provider_label} · {run.model_name}
              </p>
            ) : null}
          </div>
        </div>
        <div className="flex flex-wrap gap-3">
          {run?.report_ready ? (
            <Link
              href={`/research/${runId}/report`}
              className="rounded-full bg-[linear-gradient(90deg,#ffd58f,#7fd4ff)] px-4 py-2 text-sm font-semibold text-slate-950"
            >
              打开最终报告
            </Link>
          ) : null}
          {canRetryStages ? (
            <button
              type="button"
              onClick={() => retryStep(retryBaseStep)}
              disabled={isPending}
              className="rounded-full border border-white/14 px-4 py-2 text-sm text-white transition hover:border-white/28"
            >
              重试最近阶段
            </button>
          ) : null}
          <button
            type="button"
            onClick={cancelRun}
            disabled={isPending}
            className="rounded-full border border-rose-300/20 px-4 py-2 text-sm text-rose-100 transition hover:border-rose-300/36"
          >
            取消任务
          </button>
        </div>
      </div>

      {error ? (
        <div className="rounded-2xl border border-rose-300/20 bg-rose-300/8 px-4 py-3 text-sm text-rose-100">
          {error}
        </div>
      ) : null}

      <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="grid gap-4">
          <section className="grid gap-4 rounded-[30px] border border-white/10 bg-[var(--panel)] p-6">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              <Metric label="状态" value={run ? statusLabel(run.status) : "--"} />
              <Metric label="推理后端" value={run?.provider_label ?? "--"} />
              <Metric label="候选项" value={String(run?.target_count ?? 0)} />
              <Metric label="来源条数" value={String(run?.source_count ?? 0)} />
              <Metric label="引用条数" value={String(run?.citation_count ?? 0)} />
            </div>
            {run?.scope ? <ScopeCard scope={run.scope} /> : null}
            {run?.coverage_summary ? <CoverageCard coverage={run.coverage_summary} /> : null}
          </section>

          {run ? <ResearchRunVisuals run={run} planNodes={detail?.plan_nodes ?? []} steps={steps} sources={sources} /> : null}

          {run?.clarification_request ? (
            <section className="grid gap-4 rounded-[30px] border border-amber-300/20 bg-amber-300/8 p-6">
              <div>
                <p className="font-mono text-xs uppercase tracking-[0.22em] text-amber-100/80">等待人工补充</p>
                <h2 className="mt-2 text-2xl font-semibold text-white">请收紧研究范围</h2>
                <p className="mt-2 text-sm leading-6 text-amber-50/90">
                  {run.clarification_request.note ?? "当前范围还不够收敛，先补充候选项和维度。"}
                </p>
              </div>
              <div className="grid gap-2 text-sm text-amber-50/90">
                {run.clarification_request.questions.map((question) => (
                  <div key={question} className="rounded-2xl border border-white/12 bg-black/14 px-4 py-3">
                    {question}
                  </div>
                ))}
              </div>
              <label className="grid gap-2 text-sm text-amber-50/80">
                补充说明
                <textarea
                  className="min-h-24 rounded-2xl border border-white/12 bg-black/20 px-4 py-3 text-white"
                  value={scopeNote}
                  onChange={(event) => setScopeNote(event.target.value)}
                />
              </label>
              <div className="grid gap-4 md:grid-cols-2">
                <label className="grid gap-2 text-sm text-amber-50/80">
                  候选项
                  <input
                    className="rounded-2xl border border-white/12 bg-black/20 px-4 py-3 text-white"
                    value={selectedTargets}
                    onChange={(event) => setSelectedTargets(event.target.value)}
                  />
                </label>
                <label className="grid gap-2 text-sm text-amber-50/80">
                  比较维度
                  <input
                    className="rounded-2xl border border-white/12 bg-black/20 px-4 py-3 text-white"
                    value={selectedDimensions}
                    onChange={(event) => setSelectedDimensions(event.target.value)}
                  />
                </label>
              </div>
              <button
                type="button"
                onClick={submitClarification}
                disabled={isPending}
                className="rounded-full bg-[linear-gradient(90deg,#ffd58f,#f59e0b)] px-5 py-3 font-semibold text-slate-950 disabled:opacity-70"
              >
                {isPending ? "正在提交..." : "提交范围并继续执行"}
              </button>
            </section>
          ) : null}

          <section className="grid gap-3 rounded-[30px] border border-white/10 bg-[var(--panel)] p-6">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold text-white">研究计划</h2>
                <p className="mt-2 text-sm text-[var(--muted)]">计划树和运行轨迹分开存储，便于回放与重试。</p>
              </div>
              {canRetryStages ? (
                <button
                  type="button"
                  onClick={() => retryStep("planning")}
                  disabled={isPending}
                  className="rounded-full border border-white/14 px-4 py-2 text-sm text-white transition hover:border-white/28"
                >
                  重新规划
                </button>
              ) : null}
            </div>
            {detail?.plan_nodes.length ? (
              detail.plan_nodes.map((node) => <PlanNodeCard key={node.id} node={node} />)
            ) : (
              <EmptyState label="当前还没有计划节点，可能仍停留在澄清阶段。" />
            )}
          </section>
        </div>

        <div className="grid gap-4">
          <section className="grid gap-3 rounded-[30px] border border-white/10 bg-[var(--panel)] p-6">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold text-white">来源证据</h2>
                <p className="mt-2 text-sm text-[var(--muted)]">你可以排除弱来源，系统会自动重新综合报告。</p>
              </div>
              {canRetryStages ? (
                <button
                  type="button"
                  onClick={() => retryStep("retrieving")}
                  disabled={isPending}
                  className="rounded-full border border-white/14 px-4 py-2 text-sm text-white transition hover:border-white/28"
                >
                  重新检索
                </button>
              ) : null}
            </div>
            <div className="grid gap-3 rounded-[22px] border border-white/10 bg-black/18 p-4">
              <div className="grid gap-2 md:grid-cols-[1fr_220px]">
                <textarea
                  className="min-h-28 rounded-2xl border border-white/12 bg-black/20 px-4 py-3 text-sm text-white"
                  value={manualSourceInput}
                  onChange={(event) => setManualSourceInput(event.target.value)}
                  placeholder="粘贴 Google Scholar / 知网链接、DOI、BibTeX，或者直接输入论文标题"
                />
                <div className="grid gap-3">
                  <input
                    className="rounded-2xl border border-white/12 bg-black/20 px-4 py-3 text-sm text-white"
                    value={manualTargetName}
                    onChange={(event) => setManualTargetName(event.target.value)}
                    placeholder="绑定候选项，可选"
                  />
                  <input
                    className="rounded-2xl border border-white/12 bg-black/20 px-4 py-3 text-sm text-white"
                    value={manualSourceNote}
                    onChange={(event) => setManualSourceNote(event.target.value)}
                    placeholder="导入说明，可选"
                  />
                  <button
                    type="button"
                    onClick={importManualSource}
                    disabled={isPending}
                    className="rounded-full border border-white/14 px-4 py-3 text-sm text-white transition hover:border-white/28"
                  >
                    导入手动来源
                  </button>
                </div>
              </div>
              <p className="text-sm text-[var(--muted)]">
                默认不自动抓取 Google Scholar / CNKI。这里支持你手动导入链接、DOI、BibTeX 或标题，再进入同一套引用与重综合流程。
              </p>
            </div>
            {sources.length ? (
              sources.map((source) => (
                <article key={source.id} className="grid gap-3 rounded-[22px] border border-white/10 bg-black/18 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <a href={source.url} target="_blank" rel="noreferrer" className="text-base font-semibold text-white">
                        {source.title}
                      </a>
                      <p className="mt-1 font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--muted)]">
                        {sourceTypeLabel(source.source_type)} · {source.domain} · 质量分 {source.quality_score.toFixed(2)}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => toggleSource(source.id, !source.included)}
                      disabled={isPending}
                      className={`rounded-full px-3 py-1 font-mono text-xs uppercase tracking-[0.18em] ${
                        source.included
                          ? "border border-emerald-300/20 bg-emerald-300/10 text-emerald-100"
                          : "border border-white/12 bg-white/4 text-[var(--muted)]"
                      }`}
                    >
                      {source.included ? "已纳入" : "已排除"}
                    </button>
                  </div>
                  <p className="text-sm leading-6 text-[var(--muted)]">{source.summary}</p>
                  <p className="rounded-2xl border border-white/10 bg-white/4 px-4 py-3 text-sm leading-6 text-white/84">
                    {source.snippet}
                  </p>
                </article>
              ))
            ) : (
              <EmptyState label="还没有来源数据，检索阶段可能尚未完成。" />
            )}
          </section>

          <section className="grid gap-3 rounded-[30px] border border-white/10 bg-[var(--panel)] p-6">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold text-white">执行轨迹</h2>
                <p className="mt-2 text-sm text-[var(--muted)]">按阶段保留输入摘要、输出摘要和状态，便于回放与定位问题。</p>
              </div>
              {canRetryStages ? (
                <button
                  type="button"
                  onClick={() => retryStep("synthesizing")}
                  disabled={isPending}
                  className="rounded-full border border-white/14 px-4 py-2 text-sm text-white transition hover:border-white/28"
                >
                  重新综合
                </button>
              ) : null}
            </div>
            <div className="grid max-h-[680px] gap-3 overflow-y-auto pr-1">
              {deferredSteps.length ? (
                deferredSteps.map((step) => <StepCard key={step.id} step={step} />)
              ) : (
                <EmptyState label="还没有步骤记录。" />
              )}
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-black/18 px-4 py-4">
      <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--muted)]">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

function ScopeCard({ scope }: { scope: NonNullable<ResearchRunDetailResponse["run"]["scope"]> }) {
  return (
    <div className="grid gap-4 rounded-[24px] border border-white/10 bg-black/18 p-5">
      <div>
        <p className="font-mono text-xs uppercase tracking-[0.22em] text-[var(--accent-soft)]">已锁定范围</p>
        <h2 className="mt-2 text-2xl font-semibold text-white">{scope.clarified_question}</h2>
        <p className="mt-3 text-sm leading-6 text-[var(--muted)]">{scope.research_goal}</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <InfoPills title="候选项" values={scope.comparison_targets.map((target) => target.name)} />
        <InfoPills title="比较维度" values={scope.comparison_dimensions} />
      </div>
    </div>
  );
}

function InfoPills({ title, values }: { title: string; values: string[] }) {
  return (
    <div className="grid gap-2">
      <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--muted)]">{title}</p>
      <div className="flex flex-wrap gap-2">
        {values.map((value) => (
          <span key={value} className="rounded-full border border-white/10 px-3 py-1 text-sm text-white/88">
            {value}
          </span>
        ))}
      </div>
    </div>
  );
}

function CoverageCard({
  coverage,
}: {
  coverage: NonNullable<ResearchRunDetailResponse["run"]["coverage_summary"]>;
}) {
  return (
    <div className="grid gap-4 rounded-[24px] border border-white/10 bg-black/18 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.22em] text-[var(--accent-soft)]">证据覆盖</p>
          <h2 className="mt-2 text-2xl font-semibold text-white">
            已覆盖 {coverage.covered_target_count}/{coverage.target_count} 个候选项
          </h2>
        </div>
        <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-white/80">
          {coverage.balanced ? "覆盖已均衡" : "覆盖仍不均衡"}
        </span>
      </div>

      <div className="grid gap-3">
        {coverage.target_coverages.map((target) => (
          <article key={target.target_name} className="grid gap-3 rounded-[20px] border border-white/10 bg-white/[0.03] p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <strong className="text-white">{target.target_name}</strong>
                <p className="mt-1 text-sm text-[var(--muted)]">{evidenceStatusLabel(target.evidence_status)}</p>
              </div>
              <span className="font-mono text-xs text-[var(--muted)]">质量 {target.average_quality_score.toFixed(2)}</span>
            </div>

            <div className="grid gap-3 sm:grid-cols-4">
              <MiniStat label="官方" value={String(target.official_doc_count)} />
              <MiniStat label="仓库" value={String(target.repo_signal_count)} />
              <MiniStat label="外部" value={String(target.external_article_count)} />
              <MiniStat label="学术" value={String(target.academic_count)} />
            </div>

            {target.missing_buckets.length ? (
              <p className="text-sm text-amber-100/84">
                缺失：{target.missing_buckets.map((bucket) => coverageBucketLabel(bucket)).join("、")}
              </p>
            ) : null}
          </article>
        ))}
      </div>

      {coverage.notes.length ? (
        <div className="grid gap-2 rounded-[20px] border border-amber-300/16 bg-amber-300/8 p-4 text-sm text-amber-50/92">
          {coverage.notes.map((note) => (
            <p key={note}>{note}</p>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-black/16 px-3 py-3">
      <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--muted)]">{label}</p>
      <p className="mt-2 text-lg font-semibold text-white">{value}</p>
    </div>
  );
}

function buildManualSourcePayload(raw: string, targetName: string, note: string) {
  const payload: Record<string, string | boolean> = { include: true };
  if (targetName) {
    payload.target_name = targetName;
  }
  if (note) {
    payload.note = note;
  }

  const trimmed = raw.trim();
  if (/^@[\w-]+\s*\{/i.test(trimmed)) {
    payload.bibtex = trimmed;
    return payload;
  }
  if (/^https?:\/\//i.test(trimmed)) {
    payload.url = trimmed;
    return payload;
  }
  if (/^(https?:\/\/doi\.org\/)?10\.\d{4,9}\/\S+$/i.test(trimmed)) {
    payload.doi = trimmed;
    return payload;
  }
  payload.title = trimmed;
  return payload;
}

function PlanNodeCard({ node }: { node: ResearchPlanNode }) {
  return (
    <div className="rounded-[22px] border border-white/10 bg-black/18 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <strong className="text-white">{node.label}</strong>
        <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--muted)]">层级 {node.depth}</span>
      </div>
      <p className="mt-2 text-sm leading-6 text-[var(--muted)]">{node.description}</p>
      {node.query ? (
        <p className="mt-3 rounded-2xl border border-white/10 bg-white/4 px-4 py-3 font-mono text-xs text-white/88">
          {node.query}
        </p>
      ) : null}
    </div>
  );
}

function StepCard({ step }: { step: RunStep }) {
  return (
    <div className="rounded-[22px] border border-white/10 bg-black/18 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--muted)]">{stageNameLabel(step.name)}</p>
          <h3 className="mt-1 text-base font-semibold text-white">{step.label}</h3>
        </div>
        <span className={`rounded-full px-3 py-1 font-mono text-[11px] uppercase tracking-[0.18em] ${stepStatusClass(step.status)}`}>
          {stepStatusLabel(step.status)}
        </span>
      </div>
      <p className="mt-3 text-sm leading-6 text-[var(--muted)]">{step.summary}</p>
      {step.tool_name ? (
        <p className="mt-3 font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--accent-soft)]">
          工具：{step.tool_name}
        </p>
      ) : null}
      {step.prompt_excerpt ? (
        <p className="mt-3 rounded-2xl border border-white/10 bg-white/4 px-4 py-3 text-sm leading-6 text-white/84">
          {step.prompt_excerpt}
        </p>
      ) : null}
      {step.input_summary ? (
        <p className="mt-3 text-sm text-white/82">
          <strong>输入：</strong>
          {step.input_summary}
        </p>
      ) : null}
      {step.output_summary ? (
        <p className="mt-2 text-sm text-white/82">
          <strong>输出：</strong>
          {step.output_summary}
        </p>
      ) : null}
      <p className="mt-3 font-mono text-[11px] text-[var(--muted)]">{new Date(step.created_at).toLocaleString("zh-CN")}</p>
    </div>
  );
}

function stepStatusClass(status: RunStep["status"]) {
  if (status === "succeeded") {
    return "border border-emerald-300/20 bg-emerald-300/10 text-emerald-100";
  }
  if (status === "warning") {
    return "border border-amber-300/20 bg-amber-300/10 text-amber-100";
  }
  if (status === "failed") {
    return "border border-rose-300/20 bg-rose-300/10 text-rose-100";
  }
  return "border border-sky-300/20 bg-sky-300/10 text-sky-100";
}

function EmptyState({ label }: { label: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-white/12 px-4 py-8 text-sm text-[var(--muted)]">
      {label}
    </div>
  );
}
