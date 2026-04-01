"use client";

import { useEffect, useState, useTransition } from "react";

import { BrandMark } from "@/components/brand-mark";
import { StarfieldBackdrop } from "@/components/starfield-backdrop";
import { API_BASE } from "@/lib/api";
import type { HealthResponse } from "@/lib/types";

const INITIAL_QUESTION = "如果团队是 Python 技术栈，想做可观测、可接管、适合生产环境的 Agent 系统，LangGraph、PydanticAI 和 Mastra 哪个更适合作为底座？";

export function ResearchWorkspace() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [question, setQuestion] = useState(INITIAL_QUESTION);
  const [providerId, setProviderId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    async function load() {
      try {
        const response = await fetch(`${API_BASE}/health`, { cache: "no-store" });
        if (!response.ok) {
          throw new Error("系统状态加载失败。");
        }
        const payload = (await response.json()) as HealthResponse;
        setHealth(payload);
        setProviderId(payload.provider);
      } catch (fetchError) {
        setError(fetchError instanceof Error ? fetchError.message : "页面加载失败。");
      }
    }

    void load();
  }, []);

  function launchResearchRun() {
    startTransition(async () => {
      setError(null);
      const normalizedQuestion = question.replace(/\s+/g, " ").trim();
      if (normalizedQuestion.length < 12) {
        setError("问题再具体一点，至少让系统知道你想研究什么。");
        return;
      }

      const response = await fetch(`${API_BASE}/research-runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: normalizedQuestion.slice(0, 48),
          question: normalizedQuestion,
          provider_id: providerId || undefined,
        }),
      });

      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { detail?: string };
        setError(payload.detail ?? "创建研究任务失败。");
        return;
      }

      const run = (await response.json()) as { id: string };
      window.location.href = `/research/${run.id}`;
    });
  }

  const providerLabel = health ? (health.provider === "deepseek" ? "DeepSeek" : "启发式回退") : "正在检查模型配置";
  const providerHint = !health
    ? "正在连接后端。"
    : health.provider === "deepseek"
      ? `${health.model} 已连接`
      : "DeepSeek 未连接，当前使用回退模式";

  return (
    <main className="relative isolate min-h-screen overflow-hidden">
      <StarfieldBackdrop />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(255,213,143,0.12),transparent_28%),radial-gradient(circle_at_78%_20%,rgba(127,212,255,0.12),transparent_26%),linear-gradient(180deg,rgba(9,11,18,0.76),rgba(8,10,18,0.88))]" />

      <section className="relative mx-auto flex min-h-screen w-full max-w-5xl flex-col justify-center px-5 py-10 lg:px-8">
        <div className="mx-auto flex w-full max-w-3xl flex-col items-center gap-8 text-center">
          <BrandMark href="/" compact />

          <div className="space-y-4">
            <p className="font-mono text-[11px] uppercase tracking-[0.34em] text-[var(--accent-soft)]">Deep Research Search</p>
            <h1 className="font-[family:var(--font-editorial)] text-4xl font-semibold tracking-tight text-white md:text-6xl">
              把问题丢进来
            </h1>
            <p className="mx-auto max-w-xl text-sm leading-7 text-[var(--muted)] md:text-base">
              先找证据，再下结论。
            </p>
          </div>

          <div className="w-full rounded-[34px] border border-white/12 bg-[linear-gradient(180deg,rgba(11,14,24,0.78),rgba(10,13,22,0.6))] p-4 shadow-[0_28px_100px_rgba(0,0,0,0.42)] backdrop-blur-2xl md:p-5">
            <label className="grid gap-4">
              <textarea
                className="min-h-32 rounded-[26px] border border-white/10 bg-black/22 px-5 py-5 text-base leading-8 text-white outline-none placeholder:text-white/22 md:min-h-36 md:px-6 md:py-5 md:text-[20px]"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="例如：LangGraph、PydanticAI 和 Mastra 在 Python 生产环境里谁更适合作为 Agent 底座？"
              />
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <p className="text-sm text-[var(--muted)]">
                  <span className="text-white">{providerLabel}</span>
                  <span className="mx-2 text-white/18">·</span>
                  {providerHint}
                </p>
                <button
                  type="button"
                  onClick={launchResearchRun}
                  disabled={isPending}
                  className="rounded-full bg-[linear-gradient(90deg,#ffd58f,#7fd4ff)] px-6 py-3 text-sm font-semibold text-slate-950 transition hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {isPending ? "正在开始研究..." : "开始研究"}
                </button>
              </div>
            </label>
          </div>

          {error ? (
            <div className="w-full rounded-2xl border border-rose-300/20 bg-rose-300/8 px-4 py-3 text-sm text-rose-100">
              {error}
            </div>
          ) : null}
        </div>
      </section>
    </main>
  );
}
