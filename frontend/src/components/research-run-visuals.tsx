"use client";

import { useMemo } from "react";

import { BarCard, type BarDatum, MermaidPanel } from "@/components/visual-primitives";
import { sourceTypeLabel } from "@/lib/i18n";
import type { ResearchPlanNode, ResearchRun, RunStep, SourceDocument, SourceType } from "@/lib/types";

type ResearchRunVisualsProps = {
  run: ResearchRun;
  planNodes: ResearchPlanNode[];
  steps: RunStep[];
  sources: SourceDocument[];
};

const STAGE_ORDER = ["clarifying", "planning", "retrieving", "reading", "synthesizing"] as const;

export function ResearchRunVisuals({ run, planNodes, steps, sources }: ResearchRunVisualsProps) {
  const stageDiagram = useMemo(() => buildStageDiagram(run, steps), [run, steps]);
  const sourceGraph = useMemo(() => buildSourceGraph(sources), [sources]);
  const sourceTypeCoverage = useMemo(() => buildSourceTypeCoverage(sources), [sources]);
  const planDepthCoverage = useMemo(() => buildPlanDepthCoverage(planNodes), [planNodes]);

  return (
    <section className="grid gap-4 rounded-[30px] border border-white/10 bg-[var(--panel)] p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.24em] text-[var(--accent-soft)]">运行图解</p>
          <h2 className="mt-2 text-2xl font-semibold text-white">把流程状态和来源结构压成运行视图</h2>
        </div>
        <p className="max-w-2xl text-sm leading-6 text-[var(--muted)]">
          这里不会重复展示全文信息，只突出当前研究走到了哪一步、来源主要来自哪里、规划树是否足够展开。
        </p>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <MermaidPanel
          title="研究流程图"
          description="从范围澄清到报告产出，节点颜色会随阶段状态变化。"
          chart={stageDiagram}
        />
        <MermaidPanel
          title="来源关系图"
          description="把已纳入来源按类型和域名归组，快速判断证据是否过于单一。"
          chart={sourceGraph}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <BarCard
          title="来源类型分布"
          caption="统计所有已抓取来源的类型数量，方便识别研究是否过度依赖某一种材料。"
          data={sourceTypeCoverage}
        />
        <BarCard
          title="计划层级分布"
          caption="观察研究规划是否停留在浅层节点，还是已经展开到更细的子任务。"
          data={planDepthCoverage}
        />
      </div>
    </section>
  );
}

function buildStageDiagram(run: ResearchRun, steps: RunStep[]) {
  const nodes = [
    { id: "clarifying", label: "范围澄清" },
    { id: "planning", label: "研究规划" },
    { id: "retrieving", label: "来源检索" },
    { id: "reading", label: "证据阅读" },
    { id: "synthesizing", label: "报告综合" },
    { id: "completed", label: run.report_ready ? "报告完成" : "等待完成" },
  ];

  const links = [
    "  clarifying --> planning",
    "  planning --> retrieving",
    "  retrieving --> reading",
    "  reading --> synthesizing",
    "  synthesizing --> completed",
  ];

  const classes = nodes
    .map((node) => `  class ${node.id} ${resolveStageClass(node.id, run, steps)};`)
    .join("\n");

  return [
    "flowchart LR",
    ...nodes.map((node) => `  ${node.id}["${node.label}"]`),
    ...links,
    "  classDef done fill:#163b2b,stroke:#53d79c,color:#e8fff4;",
    "  classDef active fill:#14243f,stroke:#7fd4ff,color:#eef8ff;",
    "  classDef waiting fill:#332814,stroke:#f6c768,color:#fff9eb;",
    "  classDef blocked fill:#381820,stroke:#fb7185,color:#fff0f3;",
    "  classDef idle fill:#121828,stroke:#334155,color:#cbd5e1;",
    classes,
  ].join("\n");
}

function resolveStageClass(stageId: string, run: ResearchRun, steps: RunStep[]) {
  if (stageId === "completed") {
    if (run.status === "succeeded") {
      return "done";
    }
    if (run.status === "failed" || run.status === "cancelled") {
      return "blocked";
    }
    return "idle";
  }

  const stageSteps = steps.filter((step) => step.name === stageId);
  if (stageSteps.some((step) => step.status === "failed")) {
    return "blocked";
  }
  if (stageSteps.some((step) => step.status === "warning")) {
    return "waiting";
  }
  if (run.status === "waiting_human" && stageId === "clarifying") {
    return "waiting";
  }
  if (run.status === stageId || stageSteps.some((step) => step.status === "running")) {
    return "active";
  }
  if (stageSteps.some((step) => step.status === "succeeded")) {
    return "done";
  }

  const currentStageIndex = STAGE_ORDER.indexOf((run.last_completed_step as (typeof STAGE_ORDER)[number] | null) ?? "clarifying");
  const stageIndex = STAGE_ORDER.indexOf(stageId as (typeof STAGE_ORDER)[number]);
  if (currentStageIndex >= 0 && stageIndex >= 0 && stageIndex < currentStageIndex) {
    return "done";
  }

  return "idle";
}

function buildSourceGraph(sources: SourceDocument[]) {
  const includedSources = sources.filter((source) => source.included);
  const typeBuckets = new Map<SourceType, SourceDocument[]>();
  for (const source of includedSources) {
    const bucket = typeBuckets.get(source.source_type) ?? [];
    bucket.push(source);
    typeBuckets.set(source.source_type, bucket);
  }

  const typeNodes = Array.from(typeBuckets.entries());
  if (!typeNodes.length) {
    return [
      "flowchart TD",
      '  empty["尚未抓到有效来源"]',
      '  hint["完成检索后这里会出现来源关系图"]',
      "  empty --> hint",
    ].join("\n");
  }

  const lines = ["flowchart TD", `  root["已纳入来源 ${includedSources.length}"]`];
  typeNodes.forEach(([sourceType, typeSources], typeIndex) => {
    const typeId = `type${typeIndex}`;
    lines.push(`  ${typeId}["${escapeMermaidLabel(`${sourceTypeLabel(sourceType)} (${typeSources.length})`)}"]`);
    lines.push(`  root --> ${typeId}`);

    const domainCounts = new Map<string, number>();
    for (const source of typeSources) {
      domainCounts.set(source.domain, (domainCounts.get(source.domain) ?? 0) + 1);
    }

    Array.from(domainCounts.entries())
      .sort((left, right) => right[1] - left[1])
      .slice(0, 4)
      .forEach(([domain, count], domainIndex) => {
        const domainId = `${typeId}Domain${domainIndex}`;
        lines.push(`  ${domainId}["${escapeMermaidLabel(`${domain} (${count})`)}"]`);
        lines.push(`  ${typeId} --> ${domainId}`);
      });
  });

  return lines.join("\n");
}

function buildSourceTypeCoverage(sources: SourceDocument[]): BarDatum[] {
  const counts = new Map<string, number>();
  for (const source of sources) {
    const label = sourceTypeLabel(source.source_type);
    counts.set(label, (counts.get(label) ?? 0) + 1);
  }

  if (!counts.size) {
    return [{ label: "尚无来源", value: 0 }];
  }

  return Array.from(counts.entries()).map(([label, value]) => ({ label, value }));
}

function buildPlanDepthCoverage(planNodes: ResearchPlanNode[]): BarDatum[] {
  const counts = new Map<number, number>();
  for (const node of planNodes) {
    counts.set(node.depth, (counts.get(node.depth) ?? 0) + 1);
  }

  if (!counts.size) {
    return [{ label: "尚无节点", value: 0 }];
  }

  return Array.from(counts.entries())
    .sort((left, right) => left[0] - right[0])
    .map(([depth, value]) => ({ label: `层级 ${depth}`, value }));
}

function escapeMermaidLabel(value: string) {
  return value.replace(/"/g, '\\"');
}
