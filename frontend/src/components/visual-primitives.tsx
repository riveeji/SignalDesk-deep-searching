"use client";

import { useEffect, useId, useState } from "react";
import type { ReactNode, RefObject } from "react";

export type BarDatum = {
  label: string;
  value: number;
};

type MermaidPanelProps = {
  title: string;
  description: string;
  chart: string;
  actions?: ReactNode;
  containerRef?: RefObject<HTMLDivElement | null>;
  onSvgChange?: (svg: string) => void;
};

export function MermaidPanel({
  title,
  description,
  chart,
  actions,
  containerRef,
  onSvgChange,
}: MermaidPanelProps) {
  const [svg, setSvg] = useState("");
  const [error, setError] = useState<string | null>(null);
  const diagramId = useId().replace(/[:]/g, "-");

  useEffect(() => {
    let active = true;

    async function renderDiagram() {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          theme: "dark",
          securityLevel: "loose",
          fontFamily: "ui-sans-serif, system-ui, sans-serif",
        });
        const { svg: rendered } = await mermaid.render(diagramId, chart);
        if (!active) {
          return;
        }
        setSvg(rendered);
        setError(null);
        onSvgChange?.(rendered);
      } catch (renderError) {
        if (!active) {
          return;
        }
        setSvg("");
        onSvgChange?.("");
        setError(renderError instanceof Error ? renderError.message : "图解生成失败。");
      }
    }

    void renderDiagram();
    return () => {
      active = false;
    };
  }, [chart, diagramId, onSvgChange]);

  return (
    <div className="rounded-[26px] border border-white/10 bg-black/18 p-4">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-white">{title}</h3>
          <p className="mt-1 text-sm leading-6 text-[var(--muted)]">{description}</p>
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </div>
      {error ? (
        <div className="rounded-2xl border border-rose-300/20 bg-rose-300/8 px-4 py-3 text-sm text-rose-100">{error}</div>
      ) : (
        <div
          ref={containerRef}
          className="overflow-x-auto rounded-[22px] border border-white/10 bg-[#050814] px-4 py-3"
          dangerouslySetInnerHTML={{
            __html: svg || "<div class='py-10 text-sm text-white/70'>正在生成图解...</div>",
          }}
        />
      )}
    </div>
  );
}

type BarCardProps = {
  title: string;
  caption: string;
  data: BarDatum[];
};

export function BarCard({ title, caption, data }: BarCardProps) {
  const maxValue = Math.max(...data.map((item) => item.value), 1);

  return (
    <div className="rounded-[26px] border border-white/10 bg-black/18 p-4">
      <h3 className="text-lg font-semibold text-white">{title}</h3>
      <p className="mt-1 text-sm leading-6 text-[var(--muted)]">{caption}</p>
      <div className="mt-4 grid gap-3">
        {data.map((item) => (
          <div key={item.label} className="grid gap-2">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="text-white/90">{item.label}</span>
              <span className="font-mono text-xs uppercase tracking-[0.16em] text-[var(--muted)]">{item.value}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-white/8">
              <div
                className="h-full rounded-full bg-[linear-gradient(90deg,#ffd58f,#7fd4ff)]"
                style={{ width: `${Math.max((item.value / maxValue) * 100, item.value > 0 ? 10 : 0)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
