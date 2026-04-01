"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { BrandMark } from "@/components/brand-mark";
import { ReportVisuals } from "@/components/report-visuals";
import { API_BASE } from "@/lib/api";
import {
  alignmentLabel,
  confidenceLabel,
  coverageBucketLabel,
  evidenceStatusLabel,
  verdictLabel,
} from "@/lib/i18n";
import type { Citation, ReportResponse } from "@/lib/types";

type ReportViewProps = {
  runId: string;
};

export function ReportView({ runId }: ReportViewProps) {
  const [data, setData] = useState<ReportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const response = await fetch(`${API_BASE}/research-runs/${runId}/report`, { cache: "no-store" });
        if (!response.ok) {
          throw new Error("报告尚未生成完成。");
        }
        setData((await response.json()) as ReportResponse);
      } catch (fetchError) {
        setError(fetchError instanceof Error ? fetchError.message : "报告加载失败。");
      }
    }

    void load();
  }, [runId]);

  const citationById = useMemo(() => {
    const map = new Map<string, Citation>();
    for (const citation of data?.citations ?? []) {
      map.set(citation.id, citation);
    }
    return map;
  }, [data]);

  if (error) {
    return (
      <main className="mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-6 px-5 py-8 lg:px-8">
        <BrandMark href="/" compact />
        <Link href={`/research/${runId}`} className="font-mono text-xs uppercase tracking-[0.22em] text-[var(--muted)]">
          返回任务详情
        </Link>
        <div className="rounded-2xl border border-rose-300/20 bg-rose-300/8 px-4 py-3 text-sm text-rose-100">{error}</div>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-6 px-5 py-8 lg:px-8">
        <BrandMark href="/" compact />
        <div className="rounded-2xl border border-white/10 bg-[var(--panel)] px-4 py-8 text-sm text-[var(--muted)]">正在加载最终报告...</div>
      </main>
    );
  }

  const { report, citations } = data;

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-6 px-5 py-8 lg:px-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-4">
          <BrandMark href="/" compact />
          <div>
            <Link href={`/research/${runId}`} className="font-mono text-xs uppercase tracking-[0.22em] text-[var(--muted)]">
              返回任务详情
            </Link>
            <h1 className="mt-3 text-4xl font-semibold text-white">最终研究报告</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--muted)]">{report.question_restatement}</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-3">
          <a href={`${API_BASE}/research-runs/${runId}/report/markdown`} className="rounded-full border border-white/14 px-4 py-2 text-sm text-white transition hover:border-white/28">
            导出 Markdown
          </a>
          <a href={`${API_BASE}/research-runs/${runId}/report/pdf`} className="rounded-full bg-[linear-gradient(90deg,#ffd58f,#7fd4ff)] px-4 py-2 text-sm font-semibold text-slate-950">
            导出 PDF
          </a>
        </div>
      </div>

      <QualityPanel report={report} />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="候选项" value={String(report.candidate_names.length)} />
        <Metric label="比较维度" value={String(report.comparison_dimensions.length)} />
        <Metric label="报告章节" value={String(report.sections.length)} />
        <Metric label="引用数量" value={String(citations.length)} />
      </div>

      <ReportVisuals report={report} citations={citations} />

      <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div className="grid gap-6 rounded-[32px] border border-white/10 bg-[var(--panel)] p-6 lg:p-8">
          <article className="grid gap-4 rounded-[26px] border border-white/10 bg-black/16 p-5">
            <p className="font-mono text-xs uppercase tracking-[0.24em] text-[var(--accent-soft)]">执行摘要</p>
            <p className="text-lg leading-8 text-white/92">{report.executive_summary}</p>
          </article>

          {report.coverage_summary?.target_coverages?.length ? (
            <section className="grid gap-3">
              <h2 className="text-2xl font-semibold text-white">候选项覆盖矩阵</h2>
              <div className="grid gap-3">
                {report.coverage_summary.target_coverages.map((target) => (
                  <article key={target.target_name} className="grid gap-3 rounded-[24px] border border-white/10 bg-black/16 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <h3 className="text-lg font-semibold text-white">{target.target_name}</h3>
                        <p className="text-sm text-[var(--muted)]">{evidenceStatusLabel(target.evidence_status)}</p>
                      </div>
                      <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-white/80">
                        平均质量 {target.average_quality_score.toFixed(2)}
                      </span>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-4">
                      <Stat label="官方" value={String(target.official_doc_count)} />
                      <Stat label="仓库" value={String(target.repo_signal_count)} />
                      <Stat label="外部" value={String(target.external_article_count)} />
                      <Stat label="学术" value={String(target.academic_count)} />
                    </div>
                    {target.missing_buckets.length ? (
                      <p className="text-sm text-amber-100/84">
                        缺失：{target.missing_buckets.map((bucket) => coverageBucketLabel(bucket)).join("、")}
                      </p>
                    ) : null}
                  </article>
                ))}
              </div>
            </section>
          ) : null}

          {report.comparison_table.length ? (
            <section className="grid gap-3">
              <h2 className="text-2xl font-semibold text-white">横向比较表</h2>
              <div className="overflow-x-auto rounded-[24px] border border-white/10">
                <table className="min-w-full border-collapse text-left text-sm text-[var(--muted)]">
                  <thead className="bg-black/24 text-white">
                    <tr>
                      {Object.keys(report.comparison_table[0]).map((header) => (
                        <th key={header} className="border-b border-white/10 px-4 py-3 font-medium">{header}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {report.comparison_table.map((row, index) => (
                      <tr key={`row-${index}`} className="border-b border-white/6 last:border-b-0">
                        {Object.keys(report.comparison_table[0]).map((header) => (
                          <td key={`${index}-${header}`} className="px-4 py-3 align-top">{row[header]}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ) : null}

          <section className="grid gap-3 rounded-[26px] border border-emerald-300/14 bg-emerald-300/6 p-5">
            <p className="font-mono text-xs uppercase tracking-[0.22em] text-emerald-100/80">推荐结论</p>
            <p className="text-lg leading-8 text-white">{report.recommendation}</p>
          </section>

          <section className="grid gap-4">
            {report.sections.map((section) => (
              <article key={section.slug} className="grid gap-4 rounded-[26px] border border-white/10 bg-black/16 p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h2 className="text-2xl font-semibold text-white">{section.title}</h2>
                  {section.citation_ids.length ? (
                    <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-[var(--muted)]">
                      {section.citation_ids.length} 条引用
                    </span>
                  ) : null}
                </div>
                <p className="whitespace-pre-line text-sm leading-7 text-[var(--muted)]">{section.body}</p>
                {section.citation_ids.length ? (
                  <div className="grid gap-2">
                    <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--accent-soft)]">引用来源</p>
                    {section.citation_ids.map((citationId) => {
                      const citation = citationById.get(citationId);
                      return citation ? <CitationCard key={citation.id} citation={citation} /> : null;
                    })}
                  </div>
                ) : null}
              </article>
            ))}
          </section>
        </div>

        <aside className="grid gap-4 self-start lg:sticky lg:top-6">
          <SideBlock title="风险与未知项" items={report.risks_and_unknowns} />
          <SideBlock title="待验证问题" items={report.open_questions} />
        </aside>
      </section>
    </main>
  );
}

function QualityPanel({ report }: { report: ReportResponse["report"] }) {
  const quality = report.answer_quality;
  const coverage = report.coverage_summary;
  if (!quality && !coverage) {
    return null;
  }

  return (
    <section className="grid gap-4 rounded-[30px] border border-white/10 bg-[var(--panel)] p-5 lg:p-6">
      <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="grid gap-3 rounded-[24px] border border-white/10 bg-black/16 p-4">
          <p className="font-mono text-xs uppercase tracking-[0.24em] text-[var(--accent-soft)]">回答质量</p>
          {quality ? (
            <>
              <Stat label="结论状态" value={verdictLabel(quality.verdict)} />
              <Stat label="推荐置信度" value={confidenceLabel(quality.recommendation_confidence)} />
              <Stat label="对题程度" value={alignmentLabel(quality.question_alignment)} />
            </>
          ) : null}
        </div>
        <div className="grid gap-3 rounded-[24px] border border-white/10 bg-black/16 p-4">
          <p className="font-mono text-xs uppercase tracking-[0.24em] text-[var(--accent-soft)]">覆盖概览</p>
          {coverage ? (
            <>
              <p className="text-sm text-white/90">
                已覆盖 {coverage.covered_target_count}/{coverage.target_count} 个候选项，当前{coverage.balanced ? "达到基础均衡覆盖" : "尚未达到均衡覆盖"}。
              </p>
              {coverage.notes.length ? (
                <ul className="grid gap-2 text-sm text-[var(--muted)]">
                  {coverage.notes.slice(0, 4).map((note) => (
                    <li key={note}>• {note}</li>
                  ))}
                </ul>
              ) : null}
            </>
          ) : null}
        </div>
      </div>
      {quality?.issues.length ? (
        <div className="grid gap-2 rounded-[24px] border border-amber-300/16 bg-amber-300/8 p-4">
          <p className="font-mono text-xs uppercase tracking-[0.22em] text-amber-100/90">当前风险</p>
          {quality.issues.map((issue) => (
            <p key={issue} className="text-sm text-amber-50/92">{issue}</p>
          ))}
        </div>
      ) : null}
      {quality?.missing_evidence?.length ? (
        <div className="grid gap-2 rounded-[24px] border border-white/10 bg-black/16 p-4">
          <p className="font-mono text-xs uppercase tracking-[0.22em] text-[var(--accent-soft)]">缺失证据</p>
          {quality.missing_evidence.map((item) => (
            <p key={item} className="text-sm text-[var(--muted)]">{item}</p>
          ))}
        </div>
      ) : null}
      {quality?.question_alignment_notes?.length ? (
        <div className="grid gap-2 rounded-[24px] border border-white/10 bg-black/16 p-4">
          <p className="font-mono text-xs uppercase tracking-[0.22em] text-[var(--accent-soft)]">对题说明</p>
          {quality.question_alignment_notes.map((item) => (
            <p key={item} className="text-sm text-[var(--muted)]">{item}</p>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[24px] border border-white/10 bg-[var(--panel)] px-5 py-4">
      <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--muted)]">{label}</p>
      <p className="mt-3 text-3xl font-semibold text-white">{value}</p>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-2xl border border-white/8 bg-white/[0.03] px-3 py-2">
      <span className="text-sm text-[var(--muted)]">{label}</span>
      <span className="text-sm font-semibold text-white">{value}</span>
    </div>
  );
}

function SideBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-[26px] border border-white/10 bg-[var(--panel)] p-5">
      <h2 className="text-xl font-semibold text-white">{title}</h2>
      <div className="mt-4 grid gap-2">
        {items.length ? items.map((item) => (
          <div key={item} className="rounded-2xl border border-white/10 bg-black/16 px-4 py-3 text-sm text-[var(--muted)]">
            {item}
          </div>
        )) : <div className="rounded-2xl border border-white/10 bg-black/16 px-4 py-3 text-sm text-[var(--muted)]">暂无</div>}
      </div>
    </div>
  );
}

function CitationCard({ citation }: { citation: Citation }) {
  return (
    <a href={citation.url} target="_blank" rel="noreferrer" className="rounded-2xl border border-white/10 bg-black/16 px-4 py-3 transition hover:border-white/24">
      <div className="text-sm font-medium text-white">{citation.title}</div>
      <p className="mt-2 text-sm leading-6 text-[var(--muted)]">{citation.excerpt}</p>
    </a>
  );
}
