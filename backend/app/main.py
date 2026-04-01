from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

from .providers import build_provider_manager
from .research_service import ResearchService
from .retrieval import ResearchRetriever
from .schemas import (
    ClarifyResearchRunRequest,
    Citation,
    CreateResearchRunRequest,
    FinalReport,
    HealthResponse,
    ManualSourceImportRequest,
    ProviderOption,
    ResearchRun,
    ResearchRunDetail,
    ResearchRunStatus,
    RetryStepRequest,
    RunStep,
    SourceDocument,
    SourceToggleRequest,
    WorkspaceResponse,
    utc_now,
)
from .settings import load_settings
from .store import PostgresStore

if os.name == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

ROOT = Path(__file__).resolve().parents[1]
settings = load_settings()
provider_manager = build_provider_manager(settings)
retriever = ResearchRetriever(settings)

store = PostgresStore(ROOT / "runtime" / "artifacts", settings.database_url)
service = ResearchService(
    store=store,
    provider_manager=provider_manager,
    retriever=retriever,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await store.initialize()
    try:
        yield
    finally:
        await store.close()


app = FastAPI(title="深度研究智能体 API", version="0.3.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.frontend_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    default_provider = settings.default_provider
    return HealthResponse(
        status="ok",
        database="postgresql",
        provider=default_provider.id,
        language=settings.output_language,
        model=settings.model_label,
        temperature=settings.llm_temperature,
        web_results_per_target=settings.web_results_per_target,
        report_audience=settings.report_audience,
        providers=[
            ProviderOption(
                id=preset.id,
                label=preset.label,
                vendor=preset.vendor,
                kind=preset.kind,
                enabled=preset.enabled,
                model=preset.model,
                base_url=preset.base_url,
                is_default=preset.id == default_provider.id,
            )
            for preset in provider_manager.list_presets()
        ],
        search_providers=retriever.list_search_providers(),
    )


@app.get("/workspace", response_model=WorkspaceResponse)
async def workspace() -> WorkspaceResponse:
    return await service.workspace()


@app.get("/research-runs", response_model=list[ResearchRun])
async def list_research_runs() -> list[ResearchRun]:
    return await store.list_runs()


@app.post("/research-runs", response_model=ResearchRun, status_code=201)
async def create_research_run(request: CreateResearchRunRequest) -> ResearchRun:
    if len(request.question.strip()) < 12:
        raise HTTPException(status_code=400, detail="研究问题太短，无法触发有效的深度研究流程。")
    return await service.create_run(request)


@app.get("/research-runs/{run_id}", response_model=ResearchRunDetail)
async def get_research_run(run_id: str) -> ResearchRunDetail:
    run = await store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="未找到对应的研究任务。")
    return ResearchRunDetail(run=run, plan_nodes=await store.list_plan_nodes(run_id))


@app.get("/research-runs/{run_id}/steps", response_model=list[RunStep])
async def get_research_steps(run_id: str) -> list[RunStep]:
    run = await store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="未找到对应的研究任务。")
    return await store.list_steps(run_id)


@app.get("/research-runs/{run_id}/sources", response_model=list[SourceDocument])
async def get_research_sources(run_id: str) -> list[SourceDocument]:
    run = await store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="未找到对应的研究任务。")
    return await store.list_sources(run_id)


@app.post("/research-runs/{run_id}/sources/import", response_model=list[SourceDocument])
async def import_manual_sources(run_id: str, request: ManualSourceImportRequest) -> list[SourceDocument]:
    imported = await service.import_manual_sources(run_id, request)
    if imported is None:
        raise HTTPException(status_code=404, detail="未找到对应的研究任务。")
    if not imported:
        raise HTTPException(status_code=400, detail="没有从输入中解析出可导入的来源。")
    return imported


@app.post("/research-runs/{run_id}/sources/{source_id}", response_model=SourceDocument)
async def toggle_source(run_id: str, source_id: str, request: SourceToggleRequest) -> SourceDocument:
    source = await service.toggle_source(run_id, source_id, request.include)
    if not source:
        raise HTTPException(status_code=404, detail="未找到对应来源。")
    refreshed = await store.list_sources(run_id)
    return next(item for item in refreshed if item.id == source_id)


@app.get("/sources", response_model=list[SourceDocument])
async def list_recent_sources() -> list[SourceDocument]:
    return await store.list_all_sources(limit=80)


@app.get("/research-runs/{run_id}/report")
async def get_report(run_id: str):
    run = await store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="未找到对应的研究任务。")
    report = await store.get_report(run_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告尚未生成完成。")
    citations = await store.list_citations(run_id)
    return {
        "report": report.model_dump(mode="json"),
        "citations": [citation.model_dump(mode="json") for citation in citations],
    }


@app.get("/research-runs/{run_id}/report/markdown")
async def get_report_markdown(run_id: str) -> PlainTextResponse:
    report = await store.get_report(run_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告尚未生成完成。")
    return PlainTextResponse(
        report.markdown,
        headers={"Content-Disposition": f'attachment; filename="{run_id}-report.md"'},
    )


@app.get("/research-runs/{run_id}/report/pdf")
async def get_report_pdf(run_id: str) -> Response:
    report = await store.get_report(run_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告尚未生成完成。")
    citations = await store.list_citations(run_id)
    pdf_bytes = _render_report_pdf(report, citations)
    headers = {"Content-Disposition": f'attachment; filename="{run_id}-report.pdf"'}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@app.post("/research-runs/{run_id}/clarify", response_model=ResearchRun)
async def clarify_research_run(run_id: str, request: ClarifyResearchRunRequest) -> ResearchRun:
    run = await service.continue_after_clarification(run_id, request)
    if not run:
        raise HTTPException(status_code=404, detail="未找到对应的研究任务。")
    return run


@app.post("/research-runs/{run_id}/retry-step", response_model=ResearchRun)
async def retry_research_step(run_id: str, request: RetryStepRequest) -> ResearchRun:
    run = await service.retry_from_step(run_id, request.step_name)
    if not run:
        raise HTTPException(status_code=404, detail="未找到对应的研究任务。")
    return run


@app.post("/research-runs/{run_id}/cancel", response_model=ResearchRun)
async def cancel_research_run(run_id: str) -> ResearchRun:
    run = await store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="未找到对应的研究任务。")
    task = await store.pop_task(run_id)
    if task:
        task.cancel()
    run.status = ResearchRunStatus.CANCELLED
    run.summary = "任务已被手动取消。"
    run.finished_at = run.finished_at or utc_now()
    await store.replace_run(run)
    return run


def _render_report_pdf(report: FinalReport, citations: list[Citation]) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    width, height = A4
    margin_x = 16 * mm
    top_margin = 18 * mm
    bottom_margin = 16 * mm
    card_width = width - margin_x * 2
    cursor_y = height - top_margin

    def new_page() -> None:
        nonlocal cursor_y
        pdf.showPage()
        cursor_y = height - top_margin

    def ensure_space(required_height: float) -> None:
        nonlocal cursor_y
        if cursor_y - required_height < bottom_margin:
            new_page()

    def draw_text_block(
        text: str,
        *,
        font_size: float = 10,
        leading: float = 15,
        color: colors.Color = colors.HexColor("#102030"),
        width_limit: float = card_width,
        indent: float = 0,
    ) -> None:
        nonlocal cursor_y
        if not text:
            return

        lines: list[str] = []
        for raw_line in text.splitlines() or [""]:
            paragraph = raw_line or " "
            lines.extend(_wrap_text(pdf, paragraph, width_limit - indent, font_size))

        ensure_space(len(lines) * leading + 4)
        text_object = pdf.beginText(margin_x + indent, cursor_y)
        text_object.setFont("STSong-Light", font_size)
        text_object.setLeading(leading)
        text_object.setFillColor(color)
        for line in lines:
            text_object.textLine(line)
        pdf.drawText(text_object)
        cursor_y = text_object.getY() - 4

    def draw_heading(title: str, *, font_size: float = 16, spacing_after: float = 8) -> None:
        nonlocal cursor_y
        ensure_space(font_size + spacing_after + 8)
        pdf.setFont("STSong-Light", font_size)
        pdf.setFillColor(colors.HexColor("#0f172a"))
        pdf.drawString(margin_x, cursor_y, title)
        cursor_y -= font_size + spacing_after

    def draw_metric_cards(items: list[tuple[str, str]]) -> None:
        nonlocal cursor_y
        columns = 2
        gap = 6 * mm
        card_height = 18 * mm
        item_width = (card_width - gap) / columns
        rows = (len(items) + columns - 1) // columns
        ensure_space(rows * card_height + (rows - 1) * gap + 4)
        current_y = cursor_y

        for index, (label, value) in enumerate(items):
            row = index // columns
            column = index % columns
            x = margin_x + column * (item_width + gap)
            y = current_y - row * (card_height + gap) - card_height
            pdf.setFillColor(colors.HexColor("#eef4ff"))
            pdf.setStrokeColor(colors.HexColor("#d7e2f1"))
            pdf.roundRect(x, y, item_width, card_height, 8, stroke=1, fill=1)
            pdf.setFont("STSong-Light", 8)
            pdf.setFillColor(colors.HexColor("#64748b"))
            pdf.drawString(x + 10, y + card_height - 16, label)
            pdf.setFont("STSong-Light", 15)
            pdf.setFillColor(colors.HexColor("#0f172a"))
            pdf.drawString(x + 10, y + 9, value)

        cursor_y = current_y - rows * card_height - (rows - 1) * gap - 8

    def draw_bar_chart(title: str, caption: str, data: list[tuple[str, int]]) -> None:
        nonlocal cursor_y
        visible_data = data[:6] if data else [("暂无数据", 0)]
        chart_height = 26 * mm + len(visible_data) * 9 * mm
        ensure_space(chart_height + 8)

        pdf.setFillColor(colors.HexColor("#f8fbff"))
        pdf.setStrokeColor(colors.HexColor("#d7e2f1"))
        pdf.roundRect(margin_x, cursor_y - chart_height, card_width, chart_height, 10, stroke=1, fill=1)

        inner_x = margin_x + 10
        inner_top = cursor_y - 12
        pdf.setFont("STSong-Light", 12)
        pdf.setFillColor(colors.HexColor("#0f172a"))
        pdf.drawString(inner_x, inner_top, title)

        caption_lines = _wrap_text(pdf, caption, card_width - 20, 8)
        pdf.setFont("STSong-Light", 8)
        pdf.setFillColor(colors.HexColor("#64748b"))
        caption_y = inner_top - 12
        for line in caption_lines:
            pdf.drawString(inner_x, caption_y, line)
            caption_y -= 10

        max_value = max((value for _, value in visible_data), default=1) or 1
        bar_start_y = caption_y - 6
        bar_x = inner_x + 62 * mm
        bar_width_max = card_width - (bar_x - margin_x) - 16

        for index, (label, value) in enumerate(visible_data):
            row_y = bar_start_y - index * 9 * mm
            pdf.setFont("STSong-Light", 9)
            pdf.setFillColor(colors.HexColor("#334155"))
            label_lines = _wrap_text(pdf, label, 58 * mm, 9)
            pdf.drawString(inner_x, row_y, label_lines[0] if label_lines else label)
            pdf.setFillColor(colors.HexColor("#e5edf8"))
            pdf.roundRect(bar_x, row_y - 4, bar_width_max, 8, 4, stroke=0, fill=1)
            fill_width = 0 if value <= 0 else max(bar_width_max * (value / max_value), 10)
            pdf.setFillColor(colors.HexColor("#7c9dff"))
            pdf.roundRect(bar_x, row_y - 4, fill_width, 8, 4, stroke=0, fill=1)
            pdf.setFillColor(colors.HexColor("#0f172a"))
            pdf.drawRightString(margin_x + card_width - 10, row_y - 1, str(value))

        cursor_y -= chart_height + 8

    draw_heading("研策台 Deep Research Report", font_size=20, spacing_after=10)
    draw_text_block(report.question_restatement, font_size=11, leading=16, color=colors.HexColor("#334155"))

    draw_metric_cards(
        [
            ("候选项数量", str(len(report.candidate_names))),
            ("比较维度", str(len(report.comparison_dimensions))),
            ("报告章节", str(len(report.sections))),
            ("引用数量", str(len(citations))),
            ("结论状态", _quality_verdict_label(report.verdict)),
            ("推荐置信度", _quality_confidence_label(report.recommendation_confidence)),
        ]
    )

    candidate_coverage = _build_candidate_coverage(report, citations)
    section_coverage = [(section.title, len(section.citation_ids)) for section in report.sections]
    draw_bar_chart("证据覆盖", "按候选项统计引用数量，用来判断证据是否均衡。", candidate_coverage)
    draw_bar_chart("章节引用分布", "按章节统计引用密度，用来判断结论支撑是否扎实。", section_coverage)

    if report.answer_quality:
        draw_heading("回答质量")
        draw_text_block(f"结论状态：{_quality_verdict_label(report.answer_quality.verdict)}")
        draw_text_block(f"推荐置信度：{_quality_confidence_label(report.answer_quality.recommendation_confidence)}")
        draw_text_block(f"对题程度：{_quality_alignment_label(report.answer_quality.question_alignment)}")
        for item in report.answer_quality.issues:
            draw_text_block(f"风险：{item}", font_size=9, leading=14, color=colors.HexColor("#7c2d12"))
        for item in report.answer_quality.notes:
            draw_text_block(f"说明：{item}", font_size=9, leading=14, color=colors.HexColor("#334155"))

    if report.missing_evidence:
        draw_heading("缺失证据")
        for item in report.missing_evidence:
            draw_text_block(f"• {item}", font_size=9, leading=14, color=colors.HexColor("#7c2d12"))

    if report.question_alignment_notes:
        draw_heading("对题说明")
        for item in report.question_alignment_notes:
            draw_text_block(f"• {item}", font_size=9, leading=14, color=colors.HexColor("#334155"))

    draw_heading("执行摘要")
    draw_text_block(report.executive_summary)

    draw_heading("候选项")
    draw_text_block("、".join(report.candidate_names) if report.candidate_names else "未识别出明确候选项。")

    draw_heading("比较维度")
    draw_text_block("、".join(report.comparison_dimensions) if report.comparison_dimensions else "未指定比较维度。")

    if report.comparison_table:
        draw_heading("横向比较")
        for row in report.comparison_table:
            row_text = " | ".join(f"{key}: {value}" for key, value in row.items())
            draw_text_block(row_text, font_size=9, leading=14)

    draw_heading("推荐结论")
    draw_text_block(report.recommendation)

    for section in report.sections:
        draw_heading(section.title)
        draw_text_block(section.body)

    draw_heading("风险与未知项")
    for item in report.risks_and_unknowns or ["暂无补充。"]:
        draw_text_block(f"• {item}", font_size=9, leading=14)

    draw_heading("待验证问题")
    for item in report.open_questions or ["暂无补充。"]:
        draw_text_block(f"• {item}", font_size=9, leading=14)

    draw_heading("引用总表")
    for citation in citations:
        draw_text_block(citation.title, font_size=10, leading=14, color=colors.HexColor("#0f172a"))
        draw_text_block(citation.claim, font_size=9, leading=13, color=colors.HexColor("#334155"), indent=4 * mm)
        draw_text_block(citation.url, font_size=8, leading=12, color=colors.HexColor("#64748b"), indent=4 * mm)
        cursor_y -= 2

    pdf.save()
    buffer.seek(0)
    return buffer.read()


def _wrap_text(pdf: canvas.Canvas, text: str, width_limit: float, font_size: float) -> list[str]:
    if not text:
        return [""]

    lines: list[str] = []
    current = ""
    for char in text:
        candidate = f"{current}{char}"
        if pdf.stringWidth(candidate, "STSong-Light", font_size) <= width_limit or not current:
            current = candidate
            continue
        lines.append(current)
        current = char

    if current:
        lines.append(current)

    return lines or [text]


def _build_candidate_coverage(report: FinalReport, citations: list[Citation]) -> list[tuple[str, int]]:
    candidates = report.candidate_names or ["综合判断"]
    rows: list[tuple[str, int]] = []
    for candidate in candidates:
        lowered = candidate.lower()
        count = sum(
            1
            for citation in citations
            if lowered == "综合判断"
            or lowered in f"{citation.title} {citation.claim} {citation.excerpt}".lower()
        )
        rows.append((candidate, count))
    return rows


def _quality_verdict_label(verdict: str) -> str:
    return {
        "grounded": "可支撑结论",
        "insufficient_evidence": "证据不足",
        "needs_clarification": "需要补充范围",
    }.get(verdict, verdict)


def _quality_confidence_label(confidence: str) -> str:
    return {"high": "高", "medium": "中", "low": "低"}.get(confidence, confidence)


def _quality_alignment_label(alignment: str) -> str:
    return {
        "aligned": "对题",
        "partially_aligned": "部分对题",
        "needs_review": "可能偏题",
    }.get(alignment, alignment)
