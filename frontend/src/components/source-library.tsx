"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { BrandMark } from "@/components/brand-mark";
import { API_BASE } from "@/lib/api";
import { sourceTypeLabel } from "@/lib/i18n";
import type { SourceDocument } from "@/lib/types";

export function SourceLibrary() {
  const [sources, setSources] = useState<SourceDocument[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const response = await fetch(`${API_BASE}/sources`, { cache: "no-store" });
        if (!response.ok) {
          throw new Error("获取来源资料库失败。");
        }
        setSources((await response.json()) as SourceDocument[]);
      } catch (fetchError) {
        setError(fetchError instanceof Error ? fetchError.message : "来源资料库加载失败。");
      }
    }

    void load();
  }, []);

  const normalizedQuery = query.trim().toLowerCase();
  const filteredSources = sources.filter((source) => {
    if (!normalizedQuery) {
      return true;
    }
    const haystack = `${source.title} ${source.domain} ${source.summary} ${source.snippet}`.toLowerCase();
    return haystack.includes(normalizedQuery);
  });

  const docsCount = sources.filter((source) => source.source_type === "official_doc").length;
  const webCount = sources.filter((source) => source.source_type === "web_article").length;
  const repoCount = sources.filter((source) => source.source_type === "github_repo" || source.source_type === "readme").length;

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-6 px-5 py-8 lg:px-8">
      <div className="space-y-4">
        <BrandMark href="/" compact />
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <Link href="/" className="font-mono text-xs uppercase tracking-[0.22em] text-[var(--muted)]">
              返回研究工作台
            </Link>
            <h1 className="mt-3 text-4xl font-semibold text-white">来源资料库</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--muted)]">
              这里汇总了最近几次研究任务中收集到的 GitHub、官方文档和网页资料，方便你回看证据池的质量与覆盖范围。
            </p>
          </div>
          <div className="grid min-w-[260px] gap-3 rounded-[24px] border border-white/10 bg-[var(--panel)] p-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <Stat label="全部来源" value={String(sources.length)} />
              <Stat label="官方文档" value={String(docsCount)} />
              <Stat label="网页资料" value={String(webCount)} />
            </div>
            <Stat label="仓库 / README" value={String(repoCount)} />
          </div>
        </div>
      </div>

      <section className="rounded-[30px] border border-white/10 bg-[var(--panel)] p-5">
        <label className="grid gap-2 text-sm text-[var(--muted)]">
          快速搜索
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="按标题、域名或摘要搜索来源"
            className="rounded-2xl border border-white/12 bg-black/18 px-4 py-3 text-white outline-none"
          />
        </label>
        <p className="mt-3 text-sm text-[var(--muted)]">当前显示 {filteredSources.length} 条来源。</p>
      </section>

      {error ? (
        <div className="rounded-2xl border border-rose-300/20 bg-rose-300/8 px-4 py-3 text-sm text-rose-100">
          {error}
        </div>
      ) : null}

      <section className="grid gap-4">
        {filteredSources.length ? (
          filteredSources.map((source) => (
            <article key={source.id} className="grid gap-3 rounded-[26px] border border-white/10 bg-[var(--panel)] p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <a href={source.url} target="_blank" rel="noreferrer" className="text-lg font-semibold text-white">
                    {source.title}
                  </a>
                  <p className="mt-1 font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--muted)]">
                    {sourceTypeLabel(source.source_type)} · {source.domain} · 质量分 {source.quality_score.toFixed(2)}
                  </p>
                </div>
                <Link
                  href={`/research/${source.run_id}`}
                  className="rounded-full border border-white/14 px-4 py-2 text-sm text-white transition hover:border-white/28"
                >
                  打开对应任务
                </Link>
              </div>
              <p className="text-sm leading-6 text-[var(--muted)]">{source.summary}</p>
              <p className="rounded-2xl border border-white/10 bg-black/18 px-4 py-3 text-sm leading-6 text-white/86">
                {source.snippet}
              </p>
            </article>
          ))
        ) : (
          <div className="rounded-2xl border border-dashed border-white/12 px-4 py-8 text-sm text-[var(--muted)]">
            当前没有匹配的来源数据。
          </div>
        )}
      </section>
    </main>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-black/18 px-4 py-3">
      <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--muted)]">{label}</p>
      <p className="mt-2 text-lg font-semibold text-white">{value}</p>
    </div>
  );
}
