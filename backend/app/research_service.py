from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from .project_registry import KNOWN_PROJECTS, find_project_by_alias
from .providers import ProviderManager
from .retrieval import ResearchRetriever
from .schemas import (
    AnswerQuality,
    Citation,
    ClarificationRequest,
    ClarifyResearchRunRequest,
    ComparisonTarget,
    CoverageSummary,
    CreateResearchRunRequest,
    FinalReport,
    ManualSourceImportRequest,
    ReportSection,
    ResearchPlanNode,
    ResearchRun,
    ResearchRunStatus,
    ResearchScope,
    RunStep,
    SourceDocument,
    SourceType,
    StepStatus,
    TargetCoverage,
    WorkspaceResponse,
    new_id,
    utc_now,
)
from .store import PostgresStore

SAMPLE_QUESTIONS = [
    "Qwen、DeepSeek 和 Kimi 哪个更适合作为中文技术研究助手的默认推理后端？",
    "对比 LangGraph、CrewAI 和 AutoGen 在生产级 Agent 编排场景中的差异。",
    "如果团队是 Python 技术栈，PydanticAI、LangGraph 和 Mastra 哪个更适合作为 Agent 平台底座？",
    "评估 LlamaIndex、Haystack 和 LangGraph 在检索增强型企业助手中的适用性。",
]
STAGE_ORDER = ("clarify", "planning", "retrieving", "synthesizing")


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(cleaned)
    return ordered


class ResearchService:
    def __init__(self, *, store: PostgresStore, provider_manager: ProviderManager, retriever: ResearchRetriever) -> None:
        self._store = store
        self._provider_manager = provider_manager
        self._retriever = retriever

    async def workspace(self) -> WorkspaceResponse:
        return WorkspaceResponse(runs=await self._store.list_runs(), sample_questions=SAMPLE_QUESTIONS)

    async def create_run(self, request: CreateResearchRunRequest) -> ResearchRun:
        preset = self._provider_manager.describe(request.provider_id)
        run = ResearchRun(
            title=request.title or self._title_from_question(request.question),
            question=request.question.strip(),
            context=request.context,
            provider_id=preset.id,
            provider_label=preset.label,
            model_name=preset.model or "heuristic-fallback",
            requested_targets=request.comparison_targets or [],
            requested_dimensions=request.comparison_dimensions or [],
            requested_must_include=request.must_include or [],
            summary="已进入队列，等待开始研究。",
        )
        saved = await self._store.save_run(run)
        await self._launch(saved.id, start_stage="clarify")
        return saved

    async def continue_after_clarification(self, run_id: str, request: ClarifyResearchRunRequest) -> ResearchRun | None:
        run = await self._store.get_run(run_id)
        if not run:
            return None
        if request.scope_note:
            run.context = "\n".join(part for part in [run.context, request.scope_note.strip()] if part).strip()
        if request.selected_targets:
            run.requested_targets = request.selected_targets
        if request.comparison_dimensions:
            run.requested_dimensions = request.comparison_dimensions
        run.summary = "已收到补充信息，正在重新锁定范围并继续研究。"
        run.status = ResearchRunStatus.CLARIFYING
        run.latest_error = None
        run.finished_at = None
        run.clarification_request = None
        run.last_completed_step = None
        run.scope = None
        run.target_count = 0
        run.source_count = 0
        run.citation_count = 0
        run.report_ready = False
        run.coverage_summary = None
        await self._store.replace_run(run)
        await self._store.clear_run_outputs(
            run_id,
            clear_plan=True,
            clear_sources=True,
            clear_citations=True,
            clear_report=True,
        )
        await self._launch(run_id, start_stage="clarify")
        return await self._store.get_run(run_id)

    async def retry_from_step(self, run_id: str, step_name: str | None) -> ResearchRun | None:
        run = await self._store.get_run(run_id)
        if not run:
            return None
        stage = (step_name or run.last_completed_step or "retrieving").strip().lower()
        if stage not in STAGE_ORDER:
            stage = "retrieving"
        if stage != "clarify" and not run.scope:
            run.status = ResearchRunStatus.WAITING_HUMAN
            run.summary = "请先补充研究范围，范围锁定后才能继续执行。"
            run.latest_error = None
            run.finished_at = None
            run.clarification_request = run.clarification_request or ClarificationRequest(
                questions=[
                    "这次研究的对象是什么？如果是对比题，请至少给出两个候选项。",
                    "你最看重哪些维度？例如中文推理、成本、稳定性或上下文长度。",
                ],
                suggested_targets=run.requested_targets,
                suggested_dimensions=run.requested_dimensions,
                note="当前研究范围还没有锁定，系统不会跳过澄清阶段。",
            )
            await self._store.replace_run(run)
            return await self._store.get_run(run_id)
        if stage == "clarify":
            run.scope = None
            run.clarification_request = None
            run.target_count = 0
            run.last_completed_step = None
            run.coverage_summary = None
            await self._store.clear_run_outputs(run_id, clear_plan=True, clear_sources=True, clear_citations=True, clear_report=True)
        elif stage == "planning":
            run.last_completed_step = "clarify"
            run.coverage_summary = None
            await self._store.clear_run_outputs(run_id, clear_plan=True, clear_sources=True, clear_citations=True, clear_report=True)
        elif stage == "retrieving":
            run.last_completed_step = "planning"
            run.coverage_summary = None
            await self._store.clear_run_outputs(run_id, clear_plan=False, clear_sources=True, clear_citations=True, clear_report=True)
        else:
            run.last_completed_step = "retrieving"
            await self._store.clear_run_outputs(run_id, clear_plan=False, clear_sources=False, clear_citations=True, clear_report=True)
        run.status = self._status_for_stage(stage)
        run.summary = f"正在从 {self._stage_label(stage)} 阶段重新执行。"
        run.latest_error = None
        run.finished_at = None
        await self._store.replace_run(run)
        await self._launch(run_id, start_stage=stage)
        return await self._store.get_run(run_id)

    async def toggle_source(self, run_id: str, source_id: str, include: bool) -> SourceDocument | None:
        run = await self._store.get_run(run_id)
        if not run:
            return None
        sources = await self._store.list_sources(run_id)
        target = next((source for source in sources if source.id == source_id), None)
        if not target:
            return None
        target.included = include
        await self._store.replace_sources(run_id, [target if source.id == source_id else source for source in sources])
        await self.retry_from_step(run_id, "synthesizing")
        return target

    async def import_manual_sources(
        self,
        run_id: str,
        request: ManualSourceImportRequest,
    ) -> list[SourceDocument] | None:
        run = await self._store.get_run(run_id)
        if not run:
            return None

        imported = await self._retriever.import_manual_sources(request, scope=run.scope)
        if not imported:
            return []

        existing_sources = await self._store.list_sources(run_id)
        merged_sources = [source.model_copy(deep=True) for source in existing_sources]
        imported_for_run: list[SourceDocument] = []

        for source in imported:
            imported_source = source.model_copy(update={"run_id": run_id, "included": request.include})
            imported_for_run.append(imported_source)
            existing_index = next(
                (index for index, existing in enumerate(merged_sources) if existing.url.casefold() == imported_source.url.casefold()),
                None,
            )
            if existing_index is None:
                merged_sources.append(imported_source)
            else:
                existing = merged_sources[existing_index]
                merged_sources[existing_index] = imported_source if imported_source.quality_score >= existing.quality_score else existing.model_copy(
                    update={
                        "tags": list(dict.fromkeys([*existing.tags, *imported_source.tags])),
                        "metadata": {**imported_source.metadata, **existing.metadata},
                        "included": existing.included or imported_source.included,
                    }
                )

        await self._store.replace_sources(run_id, merged_sources)
        if run.scope:
            run.coverage_summary = self._build_coverage_summary(run.scope, merged_sources)
            await self._store.replace_run(run)
            await self.retry_from_step(run_id, "synthesizing")
        return imported_for_run

    async def process_run(self, run_id: str, *, start_stage: str = "clarify") -> None:
        run = await self._store.get_run(run_id)
        if not run:
            return
        if not run.started_at:
            run.started_at = utc_now()
            await self._store.replace_run(run)
        provider = self._provider_manager.resolve(run.provider_id)
        try:
            for stage in STAGE_ORDER[STAGE_ORDER.index(start_stage) :]:
                current = await self._store.get_run(run_id)
                if not current or current.status == ResearchRunStatus.CANCELLED:
                    return
                if stage == "clarify":
                    current = await self._clarify(current, provider)
                    if current.status == ResearchRunStatus.WAITING_HUMAN:
                        return
                elif stage == "planning":
                    current = await self._plan(current, provider)
                elif stage == "retrieving":
                    current = await self._retrieve(current)
                elif stage == "synthesizing":
                    current = await self._synthesize(current, provider)
            completed = await self._store.get_run(run_id)
            if completed:
                completed.status = ResearchRunStatus.SUCCEEDED
                completed.summary = "研究完成，最终报告已生成。"
                completed.finished_at = utc_now()
                completed.last_completed_step = "synthesizing"
                await self._store.replace_run(completed)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            failed = await self._store.get_run(run_id)
            if failed:
                failed.status = ResearchRunStatus.FAILED
                failed.summary = "研究流程执行失败。"
                failed.latest_error = str(exc)
                failed.finished_at = utc_now()
                await self._store.replace_run(failed)
                await self._save_step(
                    run_id,
                    "error",
                    "流程异常",
                    StepStatus.FAILED,
                    "研究流程在报告完成前中断。",
                    output_summary=str(exc),
                    metadata={"provider": failed.provider_id, "model": failed.model_name},
                )
        finally:
            await self._store.pop_task(run_id)

    async def _clarify(self, run: ResearchRun, provider) -> ResearchRun:
        run.status = ResearchRunStatus.CLARIFYING
        run.summary = "正在澄清研究问题与比较范围。"
        await self._store.replace_run(run)
        started_at = utc_now()
        clarified = await provider.clarify(
            question=run.question,
            context=run.context,
            selected_targets=run.requested_targets,
            comparison_dimensions=run.requested_dimensions,
            must_include=run.requested_must_include,
        )
        targets = self._targets_from_names(clarified.get("suggested_targets") or run.requested_targets)
        scope = ResearchScope(
            original_question=run.question,
            clarified_question=clarified.get("clarified_question") or run.question,
            research_goal=clarified.get("research_goal") or "输出一份可用于技术决策的结构化研究报告。",
            comparison_targets=targets,
            comparison_dimensions=clarified.get("comparison_dimensions") or run.requested_dimensions,
            deliverable="结构化技术选型报告",
            constraints=clarified.get("constraints") or [],
            must_include=clarified.get("must_include") or run.requested_must_include,
            context=run.context,
            user_scope_note=run.context,
        )
        questions = clarified.get("clarification_questions") or []
        allow_single = self._allows_single_target_scope(run, scope)
        if len(scope.comparison_targets) < 2 and not allow_single:
            questions = questions or [
                "请至少给出 2 个候选项，方便系统输出真正的横向比较。",
                "这次最看重的是生产稳定性、调试能力、类型安全，还是多智能体协作？",
            ]
        elif allow_single:
            questions = []
        if questions:
            run.scope = scope
            run.target_count = len(scope.comparison_targets)
            run.clarification_request = ClarificationRequest(
                questions=questions,
                suggested_targets=clarified.get("suggested_targets") or [project.name for project in KNOWN_PROJECTS[:4]],
                suggested_dimensions=scope.comparison_dimensions,
                note=clarified.get("note") or "当前问题范围还不够收敛，建议先补充范围再继续检索来源。",
            )
            run.status = ResearchRunStatus.WAITING_HUMAN
            run.summary = "等待你补充研究范围。"
            run.last_completed_step = "clarify"
            await self._store.replace_run(run)
            await self._save_step(
                run.id,
                "clarify",
                "澄清研究范围",
                StepStatus.WARNING,
                "当前问题需要补充范围后才能继续执行。",
                input_summary=run.question,
                output_summary="已生成澄清问题。",
                started_at=started_at,
                metadata={"question_count": len(questions), "provider": provider.id, "model": run.model_name},
            )
            return run
        run.scope = scope
        run.target_count = len(scope.comparison_targets)
        run.clarification_request = None
        run.summary = "研究范围已锁定。"
        run.last_completed_step = "clarify"
        await self._store.replace_run(run)
        await self._save_step(
            run.id,
            "clarify",
            "澄清研究范围",
            StepStatus.SUCCEEDED,
            f"已锁定 {len(scope.comparison_targets)} 个候选项与核心比较维度。",
            input_summary=run.question,
            output_summary="、".join(target.name for target in scope.comparison_targets),
            started_at=started_at,
            metadata={
                "target_count": len(scope.comparison_targets),
                "dimension_count": len(scope.comparison_dimensions),
                "provider": provider.id,
                "model": run.model_name,
            },
        )
        return run

    def _allows_single_target_scope(self, run: ResearchRun, scope: ResearchScope) -> bool:
        if len(scope.comparison_targets) != 1:
            return False
        lowered = run.question.lower()
        if _contains_any(lowered, ("对比", "比较", "vs", "versus", "哪个好", "哪种", "哪些", "compare ")):
            return False
        if run.requested_dimensions or run.context:
            return True
        return _contains_any(
            lowered,
            ("适不适合", "是否适合", "适合作为", "是否可以作为", "值不值得", "能不能", "可不可以", "适用性", "评估", "默认推理后端"),
        )

    async def _plan(self, run: ResearchRun, provider) -> ResearchRun:
        if not run.scope:
            raise RuntimeError("缺少研究范围，无法生成研究计划。")
        run.status = ResearchRunStatus.PLANNING
        run.summary = "正在生成研究计划。"
        await self._store.replace_run(run)
        started_at = utc_now()
        nodes = [
            ResearchPlanNode(
                run_id=run.id,
                label=str(node.get("label") or f"研究节点 {index + 1}"),
                description=str(node.get("description") or ""),
                query=node.get("query"),
                rationale=node.get("rationale"),
                depth=int(node.get("depth") or 0),
            )
            for index, node in enumerate(await provider.plan(run.scope))
        ]
        await self._store.save_plan_nodes(run.id, nodes)
        run.summary = "研究计划已生成。"
        run.last_completed_step = "planning"
        await self._store.replace_run(run)
        await self._save_step(
            run.id,
            "planning",
            "生成研究计划",
            StepStatus.SUCCEEDED,
            f"已生成 {len(nodes)} 个研究节点。",
            input_summary=run.scope.clarified_question,
            output_summary="、".join(node.label for node in nodes[:4]),
            started_at=started_at,
            metadata={"plan_node_count": len(nodes), "provider": provider.id, "model": run.model_name},
        )
        return run

    async def _retrieve(self, run: ResearchRun) -> ResearchRun:
        if not run.scope:
            raise RuntimeError("缺少研究范围，无法开始检索来源。")
        run.status = ResearchRunStatus.RETRIEVING
        run.summary = "正在收集 GitHub、官方文档、外部网页和学术元数据。"
        await self._store.replace_run(run)
        started_at = utc_now()
        sources = [source.model_copy(update={"run_id": run.id}) for source in await self._retriever.collect_sources(run.scope)]
        await self._store.replace_sources(run.id, sources)
        coverage = self._build_coverage_summary(run.scope, sources)
        run.coverage_summary = coverage
        run.source_count = len(sources)
        run.last_completed_step = "retrieving"
        if coverage.balanced:
            run.summary = f"已收集 {len(sources)} 条来源，{coverage.covered_target_count}/{coverage.target_count} 个候选项达到基础覆盖。"
        elif coverage.missing_targets:
            run.summary = f"已收集 {len(sources)} 条来源，但 {'、'.join(coverage.missing_targets)} 的证据仍明显不足。"
        else:
            run.summary = f"已收集 {len(sources)} 条来源，但候选项之间的证据覆盖仍不均衡。"
        await self._store.replace_run(run)
        await self._save_step(
            run.id,
            "retrieving",
            "收集研究来源",
            StepStatus.SUCCEEDED,
            f"已收集 {len(sources)} 条来源，并完成候选项覆盖统计。",
            input_summary="、".join(target.name for target in run.scope.comparison_targets),
            output_summary="、".join(source.title for source in sources[:5]),
            started_at=started_at,
            metadata={
                "source_count": len(sources),
                "included_count": sum(1 for source in sources if source.included),
                "covered_target_count": coverage.covered_target_count,
                "target_count": coverage.target_count,
                "balanced": coverage.balanced,
                "provider": run.provider_id,
                "model": run.model_name,
            },
        )
        return run

    async def _synthesize(self, run: ResearchRun, provider) -> ResearchRun:
        if not run.scope:
            raise RuntimeError("缺少研究范围，无法生成报告。")
        run.status = ResearchRunStatus.SYNTHESIZING
        run.summary = "正在综合来源、校验覆盖情况并生成最终报告。"
        await self._store.replace_run(run)
        started_at = utc_now()
        sources = await self._store.list_sources(run.id)
        coverage = self._build_coverage_summary(run.scope, sources)
        run.coverage_summary = coverage
        raw_payload = await provider.synthesize(run.scope, sources)
        quality = self._build_answer_quality(run, raw_payload, coverage, sources)
        payload = self._apply_quality_guardrails(raw_payload, coverage, quality)
        citations = self._build_citations(run.id, payload.get("sections") or [], sources)
        await self._store.replace_citations(run.id, citations)
        report = self._build_report(run, payload, citations, coverage, quality)
        await self._store.save_report(report)
        run.citation_count = len(citations)
        run.report_ready = True
        run.last_completed_step = "synthesizing"
        run.summary = "报告已生成，但当前证据不足，系统已主动降级推荐。" if quality.verdict != "grounded" else "最终报告已生成，并附带引用链与覆盖评估。"
        await self._store.replace_run(run)
        await self._save_step(
            run.id,
            "synthesizing",
            "生成最终报告",
            StepStatus.SUCCEEDED,
            "已完成综合分析，并给出结论可信度与覆盖反馈。",
            input_summary=f"{sum(1 for source in sources if source.included)} 条纳入来源",
            output_summary=report.recommendation,
            started_at=started_at,
            metadata={
                "citation_count": len(citations),
                "report_ready": True,
                "verdict": quality.verdict,
                "recommendation_confidence": quality.recommendation_confidence,
                "question_alignment": quality.question_alignment,
                "provider": provider.id,
                "model": run.model_name,
            },
        )
        return run

    async def _save_step(self, run_id: str, name: str, label: str, status: StepStatus, summary: str, *, input_summary: str | None = None, output_summary: str | None = None, started_at: datetime | None = None, metadata: dict[str, Any] | None = None) -> None:
        await self._store.save_step(
            RunStep(
                run_id=run_id,
                name=name,
                label=label,
                status=status,
                summary=summary,
                input_summary=input_summary,
                output_summary=output_summary,
                started_at=started_at or utc_now(),
                finished_at=utc_now(),
                metadata=metadata or {},
            )
        )

    async def _launch(self, run_id: str, *, start_stage: str) -> None:
        existing = await self._store.pop_task(run_id)
        if existing:
            existing.cancel()
        await self._store.bind_task(run_id, asyncio.create_task(self.process_run(run_id, start_stage=start_stage)))

    def _targets_from_names(self, names: list[str] | None) -> list[ComparisonTarget]:
        targets: list[ComparisonTarget] = []
        seen: set[str] = set()
        for name in names or []:
            descriptor = find_project_by_alias(name) or next(
                (project for project in KNOWN_PROJECTS if project.name.casefold() == name.strip().casefold()),
                None,
            )
            if descriptor:
                key = descriptor.name.casefold()
                if key in seen:
                    continue
                seen.add(key)
                targets.append(
                    ComparisonTarget(
                        name=descriptor.name,
                        repo_full_name=descriptor.repo_full_name,
                        docs_url=descriptor.docs_url,
                        homepage_url=descriptor.homepage_url,
                        rationale="当前研究范围中显式选择的对象。",
                    )
                )
                continue
            cleaned = name.strip()
            if cleaned and cleaned.casefold() not in seen:
                seen.add(cleaned.casefold())
                targets.append(ComparisonTarget(name=cleaned, rationale="当前研究范围中显式选择的对象。"))
        return targets

    def _build_citations(self, run_id: str, section_specs: list[dict[str, Any]], sources: list[SourceDocument]) -> list[Citation]:
        source_by_id = {source.id: source for source in sources}
        citations: list[Citation] = []
        for section in section_specs:
            slug = str(section.get("slug") or new_id("section"))
            for source_id in section.get("citation_source_ids") or []:
                source = source_by_id.get(source_id)
                if source:
                    citations.append(
                        Citation(
                            run_id=run_id,
                            source_id=source.id,
                            section_slug=slug,
                            claim=_short_claim(section.get("body") or ""),
                            excerpt=source.snippet,
                            title=source.title,
                            url=source.url,
                        )
                    )
        return citations

    def _build_report(self, run: ResearchRun, payload: dict[str, Any], citations: list[Citation], coverage: CoverageSummary, quality: AnswerQuality) -> FinalReport:
        by_source: dict[str, list[str]] = {}
        for citation in citations:
            by_source.setdefault(citation.source_id, []).append(citation.id)
        sections: list[ReportSection] = []
        for section in payload.get("sections") or []:
            citation_ids: list[str] = []
            for source_id in section.get("citation_source_ids") or []:
                citation_ids.extend(by_source.get(source_id, []))
            sections.append(
                ReportSection(
                    slug=str(section.get("slug") or new_id("section")),
                    title=str(section.get("title") or "章节"),
                    body=str(section.get("body") or ""),
                    citation_ids=citation_ids,
                )
            )
        report = FinalReport(
            run_id=run.id,
            question_restatement=str(payload.get("question_restatement") or run.question),
            executive_summary=str(payload.get("executive_summary") or ""),
            candidate_names=list(payload.get("candidate_names") or [target.name for target in (run.scope.comparison_targets if run.scope else [])]),
            comparison_dimensions=list(payload.get("comparison_dimensions") or (run.scope.comparison_dimensions if run.scope else [])),
            comparison_table=[{str(key): str(value) for key, value in row.items()} for row in payload.get("comparison_table") or []],
            recommendation=str(payload.get("recommendation") or ""),
            risks_and_unknowns=[str(item) for item in payload.get("risks_and_unknowns") or []],
            open_questions=[str(item) for item in payload.get("open_questions") or []],
            sections=sections,
            verdict=quality.verdict,
            recommendation_confidence=quality.recommendation_confidence,
            missing_evidence=quality.missing_evidence,
            question_alignment_notes=quality.question_alignment_notes,
            coverage_summary=coverage,
            answer_quality=quality,
            markdown="",
        )
        report.markdown = self._report_to_markdown(report, citations)
        return report

    def _report_to_markdown(self, report: FinalReport, citations: list[Citation]) -> str:
        lookup = {citation.id: citation for citation in citations}
        lines = ["# 深度研究报告", "", "## 问题重述", report.question_restatement, "", "## 执行摘要", report.executive_summary]
        lines.extend(
            [
                "",
                "## 结论摘要",
                f"- 结论状态：{self._verdict_label(report.verdict)}",
                f"- 推荐置信度：{self._confidence_label(report.recommendation_confidence)}",
            ]
        )
        if report.missing_evidence:
            lines.extend(f"- 缺失证据：{item}" for item in report.missing_evidence)
        if report.question_alignment_notes:
            lines.extend(f"- 对题说明：{item}" for item in report.question_alignment_notes)
        if report.answer_quality:
            lines.extend(
                [
                    "",
                    "## 回答质量",
                    f"- 结论状态：{self._verdict_label(report.answer_quality.verdict)}",
                    f"- 推荐置信度：{self._confidence_label(report.answer_quality.recommendation_confidence)}",
                    f"- 对题程度：{self._alignment_label(report.answer_quality.question_alignment)}",
                ]
            )
            lines.extend(f"- 关注项：{item}" for item in report.answer_quality.issues)
            lines.extend(f"- 说明：{item}" for item in report.answer_quality.notes)
            lines.extend(f"- 缺失证据：{item}" for item in report.answer_quality.missing_evidence)
            lines.extend(f"- 对题说明：{item}" for item in report.answer_quality.question_alignment_notes)
        lines.extend(["", "## 候选项"])
        lines.extend(f"- {candidate}" for candidate in report.candidate_names)
        lines.extend(["", "## 比较维度"])
        lines.extend(f"- {dimension}" for dimension in report.comparison_dimensions)
        if report.coverage_summary:
            lines.extend(
                [
                    "",
                    "## 覆盖情况",
                    f"- 总来源：{report.coverage_summary.total_sources}，覆盖候选项：{report.coverage_summary.covered_target_count}/{report.coverage_summary.target_count}，覆盖均衡：{'是' if report.coverage_summary.balanced else '否'}",
                ]
            )
            for target in report.coverage_summary.target_coverages:
                lines.append(
                    f"- {target.target_name}：{self._evidence_status_label(target.evidence_status)}，官方 {target.official_doc_count} / 仓库 {target.repo_signal_count} / 外部 {target.external_article_count} / 学术 {target.academic_count}"
                )
                if target.missing_buckets:
                    lines.append(f"  - 缺失：{'、'.join(self._bucket_label(bucket) for bucket in target.missing_buckets)}")
            lines.extend(f"- 备注：{note}" for note in report.coverage_summary.notes)
        if report.comparison_table:
            headers = list(report.comparison_table[0].keys())
            lines.extend(["", "## 横向比较表", "", "| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"])
            for row in report.comparison_table:
                lines.append("| " + " | ".join(row.get(header, "") for header in headers) + " |")
        lines.extend(["", "## 推荐结论", report.recommendation, "", "## 风险与未知项"])
        lines.extend(f"- {item}" for item in report.risks_and_unknowns)
        lines.extend(["", "## 待验证问题"])
        lines.extend(f"- {item}" for item in report.open_questions)
        for section in report.sections:
            lines.extend(["", f"## {section.title}", section.body])
            if section.citation_ids:
                lines.append("")
                lines.append("引用来源：")
                for citation_id in section.citation_ids:
                    citation = lookup.get(citation_id)
                    if citation:
                        lines.append(f"- [{citation.title}]({citation.url})")
        lines.extend(["", "## 参考来源"])
        lines.extend(f"- {citation.title}: {citation.url}" for citation in citations)
        return "\n".join(lines).strip() + "\n"

    def _build_coverage_summary(self, scope: ResearchScope, sources: list[SourceDocument]) -> CoverageSummary:
        included = [source for source in sources if source.included]
        type_counts: dict[str, int] = {}
        for source in included:
            type_counts[source.source_type.value] = type_counts.get(source.source_type.value, 0) + 1
        coverages: list[TargetCoverage] = []
        missing_targets: list[str] = []
        notes: list[str] = []
        covered = 0
        for target in scope.comparison_targets:
            bucket = [source for source in included if self._source_matches_target(source, target)]
            official = sum(1 for source in bucket if source.source_type == SourceType.OFFICIAL_DOC)
            repo = sum(1 for source in bucket if source.source_type in {SourceType.GITHUB_REPO, SourceType.README})
            external = sum(1 for source in bucket if source.source_type == SourceType.WEB_ARTICLE)
            academic = sum(
                1
                for source in bucket
                if source.source_type in {SourceType.SCHOLAR_PAPER, SourceType.ACADEMIC_METADATA, SourceType.MANUAL_IMPORT}
            )
            missing: list[str] = []
            if official == 0:
                missing.append("official_doc")
            if repo == 0:
                missing.append("repo_signal")
            if external + academic == 0:
                missing.append("external_validation")
            if not bucket:
                status = "missing"
                missing_targets.append(target.name)
                notes.append(f"{target.name} 当前没有纳入可用来源。")
            elif not missing:
                status = "complete"
                covered += 1
            else:
                status = "partial"
                notes.append(f"{target.name} 尚未补齐 {'、'.join(self._bucket_label(name) for name in missing)}。")
            coverages.append(
                TargetCoverage(
                    target_name=target.name,
                    official_doc_count=official,
                    repo_signal_count=repo,
                    external_article_count=external,
                    academic_count=academic,
                    total_sources=len(bucket),
                    average_quality_score=round(sum(source.quality_score for source in bucket) / len(bucket), 3) if bucket else 0.0,
                    missing_buckets=missing,
                    evidence_status=status,
                    source_ids=[source.id for source in bucket],
                )
            )
        return CoverageSummary(
            total_sources=len(included),
            target_count=len(scope.comparison_targets),
            covered_target_count=covered,
            balanced=bool(coverages) and covered == len(coverages),
            source_type_counts=type_counts,
            target_coverages=coverages,
            missing_targets=missing_targets,
            notes=_dedupe(notes),
        )

    def _build_answer_quality(self, run: ResearchRun, payload: dict[str, Any], coverage: CoverageSummary, sources: list[SourceDocument]) -> AnswerQuality:
        targets = [target.name for target in (run.scope.comparison_targets if run.scope else [])]
        recommendation = str(payload.get("recommendation") or "").lower()
        included = [source for source in sources if source.included]
        verdict = "grounded"
        confidence = "medium"
        alignment = "aligned"
        issues: list[str] = []
        notes: list[str] = []
        missing_evidence: list[str] = []
        question_alignment_notes: list[str] = []
        if len(included) < max(4, len(targets) * 2):
            verdict = "insufficient_evidence"
            confidence = "low"
            issues.append("纳入来源数量偏少，无法支撑稳定结论。")
        partial_targets = [target.target_name for target in coverage.target_coverages if target.evidence_status == "partial"]
        if coverage.missing_targets:
            missing_evidence.extend(f"{target} 缺少基础来源覆盖" for target in coverage.missing_targets)
        for target in coverage.target_coverages:
            if target.evidence_status == "partial" and target.missing_buckets:
                missing_evidence.append(f"{target.target_name} 缺少 {'、'.join(self._bucket_label(bucket) for bucket in target.missing_buckets)}")
        if coverage.missing_targets:
            verdict = "insufficient_evidence"
            confidence = "low"
            issues.append(f"这些候选项几乎没有证据覆盖：{'、'.join(coverage.missing_targets)}。")
        elif partial_targets:
            confidence = "low" if len(targets) > 1 else "medium"
            issues.append(f"这些候选项的证据桶仍不完整：{'、'.join(partial_targets)}。")
        if len(targets) > 1 and not coverage.balanced:
            verdict = "insufficient_evidence"
            confidence = "low"
            issues.append("多候选问题的证据覆盖不均衡，系统不应直接给出确定性排序。")
        if len(targets) > 1 and not coverage.balanced:
            question_alignment_notes.append("这是多候选比较题，只有候选项覆盖均衡时才能给确定性推荐。")
        mentioned = [name for name in targets if name.lower() in recommendation]
        if targets and len(targets) > 1 and not mentioned:
            alignment = "needs_review"
            confidence = "low"
            issues.append("推荐结论没有明确回到候选项本身，存在答非所问风险。")
            question_alignment_notes.append("推荐结论没有明确落到候选项本身，存在偏题风险。")
        elif len(targets) > 1 and len(mentioned) == 1:
            alignment = "partially_aligned"
            notes.append(f"当前推荐主要围绕 {mentioned[0]} 展开。")
            question_alignment_notes.append(f"当前推荐主要围绕 {mentioned[0]} 展开。")
        elif len(targets) == 1 and targets[0].lower() not in recommendation:
            alignment = "partially_aligned"
            notes.append("单目标评估的结论没有直接点名目标对象。")
            question_alignment_notes.append("当前回答没有直接点名用户正在评估的对象。")
        if verdict == "grounded" and coverage.balanced and len(included) >= max(6, len(targets) * 3):
            confidence = "high"
            notes.append("候选项覆盖较完整，且每个候选项都具备多类证据。")
            question_alignment_notes.append("候选项覆盖完整，结论直接围绕原问题生成。")
        elif verdict == "grounded":
            notes.append("当前可以给出结论，但仍建议继续补充外部验证来源。")
            question_alignment_notes.append("当前回答已经回到原问题，但仍建议继续补充外部验证。")
        return AnswerQuality(
            verdict=verdict,
            recommendation_confidence=confidence,
            question_alignment=alignment,
            issues=_dedupe(issues),
            notes=_dedupe(notes),
            missing_evidence=_dedupe(missing_evidence),
            question_alignment_notes=_dedupe(question_alignment_notes),
        )

    def _apply_quality_guardrails(self, payload: dict[str, Any], coverage: CoverageSummary, quality: AnswerQuality) -> dict[str, Any]:
        guarded = dict(payload)
        risks = [str(item) for item in guarded.get("risks_and_unknowns") or []]
        open_questions = [str(item) for item in guarded.get("open_questions") or []]
        sections = [dict(section) for section in guarded.get("sections") or []]
        if quality.verdict != "grounded":
            missing = [
                f"{target.target_name} 缺少 {'、'.join(self._bucket_label(bucket) for bucket in target.missing_buckets)}"
                for target in coverage.target_coverages
                if target.missing_buckets
            ]
            guarded["recommendation"] = "当前公开证据覆盖不足，系统暂不建议给出确定性推荐。" + (f" 需要优先补齐：{'；'.join(missing)}。" if missing else "")
            prefix = "当前结论已降级为“证据不足”，以下内容更适合作为继续研究的方向，而不是最终拍板依据。"
            summary = str(guarded.get("executive_summary") or "")
            guarded["executive_summary"] = prefix if not summary else f"{prefix} {summary}"
            risks.extend(quality.issues)
            open_questions.extend(coverage.notes)
            for section in sections:
                if str(section.get("slug")) == "recommendation":
                    section["body"] = guarded["recommendation"]
                if str(section.get("slug")) == "risks-and-unknowns":
                    section["body"] = "\n".join(f"- {item}" for item in _dedupe(risks))
        guarded["risks_and_unknowns"] = _dedupe(risks)
        guarded["open_questions"] = _dedupe(open_questions)
        guarded["sections"] = sections
        return guarded

    def _source_matches_target(self, source: SourceDocument, target: ComparisonTarget) -> bool:
        target_name = str(source.metadata.get("target_name") or "").casefold()
        if target_name == target.name.casefold():
            return True
        repo_name = (target.repo_full_name or "").split("/")[-1].casefold()
        haystacks = [target_name, *[tag.casefold() for tag in source.tags], source.title.casefold(), source.summary.casefold(), source.snippet.casefold()]
        expected = target.name.casefold()
        return any(expected in text or (repo_name and repo_name in text) for text in haystacks if text)

    def _bucket_label(self, bucket: str) -> str:
        return {"official_doc": "官方文档", "repo_signal": "仓库信号", "external_validation": "外部或学术验证"}.get(bucket, bucket)

    def _verdict_label(self, verdict: str) -> str:
        return {"grounded": "可支撑结论", "insufficient_evidence": "证据不足", "needs_clarification": "需要继续澄清"}.get(verdict, verdict)

    def _confidence_label(self, confidence: str) -> str:
        return {"high": "高", "medium": "中", "low": "低"}.get(confidence, confidence)

    def _alignment_label(self, alignment: str) -> str:
        return {"aligned": "对题", "partially_aligned": "部分对题", "needs_review": "可能偏题"}.get(alignment, alignment)

    def _evidence_status_label(self, status: str) -> str:
        return {"complete": "覆盖完整", "partial": "覆盖不完整", "missing": "几乎无有效证据"}.get(status, status)

    def _status_for_stage(self, stage: str) -> ResearchRunStatus:
        return {"clarify": ResearchRunStatus.CLARIFYING, "planning": ResearchRunStatus.PLANNING, "retrieving": ResearchRunStatus.RETRIEVING, "synthesizing": ResearchRunStatus.SYNTHESIZING}.get(stage, ResearchRunStatus.QUEUED)

    def _stage_label(self, stage: str) -> str:
        return {"clarify": "澄清", "planning": "规划", "retrieving": "检索", "synthesizing": "综合"}.get(stage, stage)

    def _title_from_question(self, question: str) -> str:
        stripped = question.strip().rstrip("？?。.!！")
        return stripped[:78] if len(stripped) > 78 else stripped


def _short_claim(body: str) -> str:
    cleaned = " ".join(body.strip().split())
    return cleaned[:180] + ("..." if len(cleaned) > 180 else "")
