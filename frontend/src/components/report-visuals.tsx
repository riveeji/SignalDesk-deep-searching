"use client";

import { useMemo, useRef, useState } from "react";

import { BarCard, type BarDatum, MermaidPanel } from "@/components/visual-primitives";
import type { Citation, FinalReport } from "@/lib/types";

type ReportVisualsProps = {
  report: FinalReport;
  citations: Citation[];
};

export function ReportVisuals({ report, citations }: ReportVisualsProps) {
  const evidenceCoverage = useMemo(() => buildEvidenceCoverage(report, citations), [report, citations]);
  const sectionCoverage = useMemo(() => buildSectionCoverage(report), [report]);
  const scopeDiagram = useMemo(() => buildScopeDiagram(report), [report]);
  const diagramRef = useRef<HTMLDivElement>(null);
  const [renderedSvg, setRenderedSvg] = useState("");
  const [exportHint, setExportHint] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState(false);

  async function handleExportPng() {
    if (!renderedSvg) {
      setExportHint("图解还没完成渲染，请稍后再试。");
      return;
    }
    setIsExporting(true);
    setExportHint(null);
    try {
      const svg = diagramRef.current?.querySelector("svg")?.outerHTML ?? renderedSvg;
      await downloadSvgAsPng(svg, `${report.run_id}-scope-diagram.png`);
      setExportHint("PNG 已开始下载。");
    } catch (error) {
      setExportHint(error instanceof Error ? error.message : "PNG 导出失败。");
    } finally {
      setIsExporting(false);
    }
  }

  function handleExportMermaid() {
    downloadTextFile(scopeDiagram, `${report.run_id}-scope-diagram.mmd`, "text/plain;charset=utf-8");
    setExportHint("Mermaid 源码已开始下载。");
  }

  return (
    <section className="grid gap-4 rounded-[30px] border border-white/10 bg-[var(--panel)] p-5 lg:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.24em] text-[var(--accent-soft)]">图解总览</p>
          <h2 className="mt-2 text-2xl font-semibold text-white">把研究范围和证据分布压成一眼看懂的图</h2>
        </div>
        <div className="max-w-xl text-sm leading-6 text-[var(--muted)]">
          报告里的关键结构会同步生成流程图和证据覆盖图，方便你快速判断研究是否聚焦、引用是否均衡。
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.3fr_0.7fr]">
        <MermaidPanel
          title="研究范围图"
          description="从问题重述、候选项、比较维度到最终推荐的结构化图解。"
          chart={scopeDiagram}
          containerRef={diagramRef}
          onSvgChange={setRenderedSvg}
          actions={[
            <button
              key="png"
              type="button"
              onClick={handleExportPng}
              disabled={isExporting}
              className="rounded-full border border-white/14 px-3 py-1.5 text-xs text-white transition hover:border-white/24 disabled:opacity-60"
            >
              {isExporting ? "正在导出..." : "导出 PNG"}
            </button>,
            <button
              key="mermaid"
              type="button"
              onClick={handleExportMermaid}
              className="rounded-full border border-white/14 px-3 py-1.5 text-xs text-white transition hover:border-white/24"
            >
              导出 Mermaid 源码
            </button>,
          ]}
        />

        <div className="grid gap-4">
          <BarCard
            title="证据覆盖"
            caption="按候选项统计命中的引用数量，便于判断证据是否集中在单一对象上。"
            data={evidenceCoverage}
          />
          <BarCard
            title="章节引用分布"
            caption="按报告章节统计引用密度，方便识别哪一段的证据支撑更扎实。"
            data={sectionCoverage}
          />
        </div>
      </div>

      {exportHint ? <p className="text-sm text-[var(--accent-soft)]">{exportHint}</p> : null}
    </section>
  );
}

function buildEvidenceCoverage(report: FinalReport, citations: Citation[]): BarDatum[] {
  const candidates = report.candidate_names.length ? report.candidate_names : ["综合判断"];

  return candidates.map((candidate) => {
    const lowered = candidate.toLowerCase();
    const value = citations.filter((citation) => {
      const text = `${citation.title} ${citation.claim} ${citation.excerpt}`.toLowerCase();
      return lowered === "综合判断" ? true : text.includes(lowered);
    }).length;
    return { label: candidate, value };
  });
}

function buildSectionCoverage(report: FinalReport): BarDatum[] {
  return report.sections.map((section) => ({
    label: section.title,
    value: section.citation_ids.length,
  }));
}

function buildScopeDiagram(report: FinalReport): string {
  const candidates = report.candidate_names.length ? report.candidate_names : ["综合判断"];
  const dimensions = report.comparison_dimensions.length ? report.comparison_dimensions.slice(0, 6) : ["核心能力", "成本", "落地复杂度"];

  const candidateNodes = candidates
    .map((candidate, index) => `  candidate${index}["${escapeMermaidLabel(candidate)}"]`)
    .join("\n");
  const dimensionNodes = dimensions
    .map((dimension, index) => `  dimension${index}["${escapeMermaidLabel(dimension)}"]`)
    .join("\n");
  const candidateLinks = candidates.map((_, index) => `  candidates --> candidate${index}`).join("\n");
  const dimensionLinks = dimensions.map((_, index) => `  dimensions --> dimension${index}`).join("\n");

  return [
    "flowchart TD",
    `  question["${escapeMermaidLabel(truncate(report.question_restatement, 88))}"]`,
    '  candidates["候选项"]',
    '  dimensions["比较维度"]',
    `  recommendation["${escapeMermaidLabel(truncate(report.recommendation, 72))}"]`,
    "  question --> candidates",
    "  question --> dimensions",
    "  question --> recommendation",
    candidateNodes,
    dimensionNodes,
    candidateLinks,
    dimensionLinks,
  ]
    .filter(Boolean)
    .join("\n");
}

function escapeMermaidLabel(value: string) {
  return value.replace(/"/g, '\\"');
}

function truncate(value: string, limit: number) {
  return value.length <= limit ? value : `${value.slice(0, limit - 1)}…`;
}

function downloadTextFile(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  downloadBlob(blob, filename);
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

async function downloadSvgAsPng(svgMarkup: string, filename: string) {
  const dimensions = getSvgDimensions(svgMarkup);
  const svgBlob = new Blob([svgMarkup], { type: "image/svg+xml;charset=utf-8" });
  const svgUrl = URL.createObjectURL(svgBlob);

  try {
    const image = await loadImage(svgUrl);
    const scale = 2;
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(Math.ceil(dimensions.width * scale), 1200);
    canvas.height = Math.max(Math.ceil(dimensions.height * scale), 720);

    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("当前浏览器不支持 PNG 导出。");
    }

    context.fillStyle = "#050814";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, 0, 0, canvas.width, canvas.height);

    const pngBlob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, "image/png");
    });
    if (!pngBlob) {
      throw new Error("PNG 导出失败。");
    }
    downloadBlob(pngBlob, filename);
  } finally {
    URL.revokeObjectURL(svgUrl);
  }
}

function getSvgDimensions(svgMarkup: string) {
  const documentNode = new DOMParser().parseFromString(svgMarkup, "image/svg+xml");
  const svg = documentNode.documentElement;
  const width = parseSvgUnit(svg.getAttribute("width"));
  const height = parseSvgUnit(svg.getAttribute("height"));
  const viewBox = svg.getAttribute("viewBox")?.split(/\s+/).map((value) => Number(value));

  return {
    width: width || viewBox?.[2] || 1200,
    height: height || viewBox?.[3] || 720,
  };
}

function parseSvgUnit(value: string | null) {
  if (!value) {
    return 0;
  }
  const parsed = Number(value.replace("px", ""));
  return Number.isFinite(parsed) ? parsed : 0;
}

function loadImage(url: string) {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("图解加载失败，无法导出 PNG。"));
    image.src = url;
  });
}
