from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import httpx

from .project_registry import KNOWN_PROJECTS, ProjectDescriptor, find_project_by_alias
from .prompts import (
    build_clarifier_system_prompt,
    build_planner_system_prompt,
    build_synthesizer_system_prompt,
)
from .schemas import ComparisonTarget, ResearchScope, SourceDocument, SourceType
from .settings import AppSettings, ProviderPreset


def _extract_json_payload(raw_text: str) -> Any:
    text = raw_text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(1))


def _unique_preserve_order(values: list[str]) -> list[str]:
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


def _descriptor_to_target(project: ProjectDescriptor, rationale: str | None = None) -> ComparisonTarget:
    return ComparisonTarget(
        name=project.name,
        repo_full_name=project.repo_full_name,
        docs_url=project.docs_url,
        homepage_url=project.homepage_url,
        rationale=rationale,
    )


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


MODEL_TARGET_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Qwen": ("qwen", "tongyi qianwen"),
    "DeepSeek": ("deepseek",),
    "Kimi": ("kimi", "moonshot"),
    "Claude": ("claude",),
    "Gemini": ("gemini",),
    "GPT-4.1": ("gpt-4.1", "gpt 4.1"),
    "GPT-4o": ("gpt-4o", "gpt 4o"),
}


def _is_model_target_name(name: str) -> bool:
    lowered = name.strip().lower()
    return any(alias in lowered for aliases in MODEL_TARGET_KEYWORDS.values() for alias in aliases)


def _is_model_comparison(question: str, selected_targets: list[str] | None = None) -> bool:
    selected = [target for target in selected_targets or [] if target.strip()]
    named_model_targets = _unique_preserve_order(
        _extract_named_targets(question) + [target.strip() for target in selected if _is_model_target_name(target)]
    )
    non_model_projects = [
        target
        for target in selected
        if (descriptor := find_project_by_alias(target)) is not None and not _is_model_target_name(descriptor.name)
    ]
    if len(non_model_projects) >= 2:
        return False
    if len(named_model_targets) >= 2:
        return True
    return _contains_any(
        question,
        (
            "模型",
            "推理后端",
            "基座",
            "上下文窗口",
            "rate limit",
            "pricing",
            "benchmark",
            "api",
            "llm",
            "model",
        ),
    )


def _extract_named_targets(question: str) -> list[str]:
    lowered = question.lower()
    return [name for name, aliases in MODEL_TARGET_KEYWORDS.items() if any(alias in lowered for alias in aliases)]


def _infer_project_suggestions(question: str) -> list[str]:
    named_targets = _extract_named_targets(question)
    if len(named_targets) >= 2:
        return named_targets
    if _is_model_comparison(question):
        if _contains_any(question, ("中文", "cn", "china", "research", "研究")):
            return ["Qwen", "DeepSeek", "Kimi"]
        return ["Claude", "GPT-4.1", "Gemini"]
    if _contains_any(question, ("rag", "retrieval", "embedding", "knowledge base", "检索", "知识库")):
        return ["LlamaIndex", "Haystack", "LangGraph"]
    if _contains_any(question, ("code", "swe", "coding agent", "developer agent", "代码", "研发", "编程")):
        return ["OpenHands", "AutoGen", "LangGraph"]
    if _contains_any(question, ("typed", "schema", "pydantic", "类型", "模式", "校验")):
        return ["PydanticAI", "LangGraph", "Mastra"]
    return ["LangGraph", "CrewAI", "AutoGen", "Mastra"]


def _infer_dimensions(question: str, provided: list[str] | None = None) -> list[str]:
    if provided:
        return _unique_preserve_order(provided)

    if _is_model_comparison(question):
        dimensions = [
            "中文理解与推理质量",
            "长上下文与资料吸收能力",
            "API 接入复杂度与调用成本",
            "吞吐表现与稳定性",
            "限流与配额策略",
            "文档与生态支持",
        ]
    else:
        dimensions = [
            "编排模型与状态管理",
            "记忆与上下文机制",
            "可观测性与调试体验",
            "生产部署与稳定性",
            "文档质量与生态活跃度",
        ]

    if not _is_model_comparison(question) and _contains_any(question, ("typed", "schema", "validation", "python", "类型", "校验", "模型定义")):
        dimensions.append("类型系统与开发体验")
    if not _is_model_comparison(question) and _contains_any(question, ("multi-agent", "autonomous", "collaboration", "多智能体", "协作")):
        dimensions.append("多智能体协作能力")
    if _contains_any(question, ("eval", "test", "regression", "评测", "测试", "回归")):
        dimensions.append("评测与回归验证支持")
    if not _is_model_comparison(question) and _contains_any(question, ("cost", "latency", "成本", "延迟")):
        dimensions.append("运行成本与响应效率")
    if _contains_any(question, ("enterprise", "compliance", "security", "企业", "合规", "安全")):
        dimensions.append("安全治理与企业适配度")
    if not _is_model_comparison(question) and _contains_any(question, ("qwen", "deepseek", "kimi", "claude", "gemini", "gpt", "模型", "推理后端", "llm")):
        dimensions.extend(["中文理解与推理质量", "API 接入复杂度与调用成本"])
    if not _is_model_comparison(question) and _contains_any(question, ("context", "上下文", "long context", "长文", "长上下文")):
        dimensions.append("长上下文与资料吸收能力")
    if not _is_model_comparison(question) and _contains_any(question, ("quota", "rate limit", "限流", "配额")):
        dimensions.append("稳定性与限流策略")

    return _unique_preserve_order(dimensions)


def _detect_targets(question: str, selected_targets: list[str] | None = None) -> list[ComparisonTarget]:
    results: list[ComparisonTarget] = []
    seen: set[str] = set()

    for raw_name in selected_targets or []:
        descriptor = find_project_by_alias(raw_name) or next(
            (project for project in KNOWN_PROJECTS if project.name.casefold() == raw_name.strip().casefold()),
            None,
        )
        if descriptor:
            key = descriptor.name.casefold()
            if key not in seen:
                results.append(_descriptor_to_target(descriptor, rationale="在澄清阶段被显式选中。"))
                seen.add(key)
            continue
        cleaned = raw_name.strip()
        if cleaned and cleaned.casefold() not in seen:
            results.append(ComparisonTarget(name=cleaned, rationale="在澄清阶段被显式选中。"))
            seen.add(cleaned.casefold())

    lowered = question.lower()
    for project in KNOWN_PROJECTS:
        aliases = {project.name.lower(), *project.aliases}
        if any(alias in lowered for alias in aliases):
            key = project.name.casefold()
            if key not in seen:
                results.append(_descriptor_to_target(project, rationale="在原始问题中被直接提及。"))
                seen.add(key)

    for candidate in _extract_named_targets(question):
        key = candidate.casefold()
        if key not in seen:
            results.append(ComparisonTarget(name=candidate, rationale="在原始问题中被直接提及。"))
            seen.add(key)

    return results


def _needs_compare_prefix(question: str) -> bool:
    stripped = question.strip().lower()
    return not (
        stripped.startswith("compare ")
        or stripped.startswith("对比")
        or stripped.startswith("比较")
        or stripped.startswith("评估")
    )


class ResearchProvider(ABC):
    id = "provider"
    label = "Provider"

    @abstractmethod
    async def clarify(
        self,
        *,
        question: str,
        context: str | None,
        selected_targets: list[str] | None,
        comparison_dimensions: list[str] | None,
        must_include: list[str] | None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def plan(self, scope: ResearchScope) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def synthesize(self, scope: ResearchScope, sources: list[SourceDocument]) -> dict[str, Any]:
        raise NotImplementedError


class HeuristicResearchProvider(ResearchProvider):
    id = "heuristic"
    label = "启发式回退"

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    async def clarify(
        self,
        *,
        question: str,
        context: str | None,
        selected_targets: list[str] | None,
        comparison_dimensions: list[str] | None,
        must_include: list[str] | None,
    ) -> dict[str, Any]:
        targets = _detect_targets(question, selected_targets)
        is_model_mode = _is_model_comparison(question, selected_targets)
        suggested_targets = _infer_project_suggestions(question)
        dimensions = _infer_dimensions(question, comparison_dimensions)
        context_note = context.strip() if context else None
        base_must_include = [
            "官方文档质量与学习曲线",
            "面向生产环境的工程权衡",
        ]
        if is_model_mode:
            base_must_include.extend(
                [
                    "上下文窗口、限流与配额策略",
                    "定价方式与接入兼容性",
                ]
            )
        else:
            base_must_include.append("GitHub 仓库活跃度与发布节奏")
        must_include_items = _unique_preserve_order([*(must_include or []), *base_must_include])

        clarification_questions: list[str] = []
        note: str | None = None
        if len(targets) < 2:
            if is_model_mode:
                clarification_questions = [
                    "这次报告要重点比较哪 2 到 4 个模型后端？",
                    "你更看重中文推理质量、长上下文、成本，还是与现有 SDK 的兼容性？",
                ]
                note = "当前问题方向是对的，但候选模型还不够明确，先把比较对象收紧后再继续研究。"
            else:
                clarification_questions = [
                    "这次报告要重点比较哪 2 到 4 个候选项？",
                    "你的优先级更偏向生产稳定性、可观测性、类型安全，还是多智能体灵活性？",
                ]
                note = "当前问题方向是对的，但比较范围还不够收敛，容易让研究结果变成泛泛的信息堆砌。"
        elif not comparison_dimensions:
            note = "候选范围已经明确。系统会先使用默认比较维度继续执行。"

        clarified_question = question.strip()
        if targets and _needs_compare_prefix(question):
            clarified_question = f"围绕“{question.strip().rstrip('？?')}”，对比 {'、'.join(target.name for target in targets)} 的适用性。"

        research_goal = (
            f"为{self._settings.report_audience}输出一份可直接用于技术选型与项目决策的研究报告，"
            "内容需要包含明确结论、工程权衡、风险项以及可追溯来源。"
        )

        return {
            "clarified_question": clarified_question,
            "research_goal": research_goal,
            "comparison_dimensions": dimensions,
            "constraints": [context_note] if context_note else [],
            "must_include": must_include_items,
            "suggested_targets": [target.name for target in targets] or suggested_targets,
            "clarification_questions": clarification_questions,
            "note": note,
        }

    async def plan(self, scope: ResearchScope) -> list[dict[str, Any]]:
        is_model_mode = _is_model_comparison(scope.clarified_question, [target.name for target in scope.comparison_targets])
        nodes: list[dict[str, Any]] = [
            {
                "label": "锁定研究范围",
                "description": "先把目标、约束、交付物和比较维度定住，避免后续检索跑偏成泛泛的资料堆砌。",
                "query": scope.clarified_question,
                "rationale": "深度研究首先要保证问题边界稳定。",
                "depth": 0,
            }
        ]

        for target in scope.comparison_targets:
            if is_model_mode:
                nodes.extend(
                    [
                        {
                            "label": f"整理 {target.name} 的接口与计费信号",
                            "description": f"核对 {target.name} 的 API 入口、上下文窗口、限流策略、计费方式和模型定位。",
                            "query": f"{target.name} API pricing context window rate limit official",
                            "rationale": "模型后端的工程适配度首先取决于接口边界、价格和可用性约束。",
                            "depth": 1,
                        },
                        {
                            "label": f"阅读 {target.name} 官方资料",
                            "description": f"提取 {target.name} 的中文理解、长上下文、工具调用和推荐接入方式等信号。",
                            "query": f"{target.name} official docs reasoning benchmark context window",
                            "rationale": "官方资料最能反映模型定位、推荐场景和接入方式。",
                            "depth": 1,
                        },
                    ]
                )
            else:
                nodes.extend(
                    [
                        {
                            "label": f"分析 {target.name} 的仓库信号",
                            "description": f"检查 {target.name} 的 GitHub 星标、发布节奏、维护活跃度、议题数量与仓库定位。",
                            "query": f"{target.name} GitHub stars releases issues repository activity",
                            "rationale": "仓库活跃度是生态成熟度和维护稳定性的第一层信号。",
                            "depth": 1,
                        },
                        {
                            "label": f"阅读 {target.name} 官方文档",
                            "description": f"提取 {target.name} 的运行模型、上手方式、调试手段和官方推荐的工程实践。",
                            "query": f"{target.name} official docs agent framework",
                            "rationale": "官方文档最能体现产品定位与预期使用方式。",
                            "depth": 1,
                        },
                    ]
                )

        nodes.extend(
            [
                {
                    "label": "横向比较工程权衡",
                    "description": "把候选项映射到同一套维度，形成真正可决策的比较表，而不是单点介绍。",
                    "query": "Chinese LLM model comparison pricing context window API"
                    if is_model_mode
                    else "framework comparison production observability state management",
                    "rationale": "研究报告的价值在于比较，而不是堆积资料。",
                    "depth": 0,
                },
                {
                    "label": "输出最终建议",
                    "description": "基于证据写出推荐结论、备选方案、主要风险和待验证项。",
                    "query": "recommendation",
                    "rationale": "技术选型报告必须有明确建议和风险边界。",
                    "depth": 0,
                },
            ]
        )

        return nodes

    async def synthesize(self, scope: ResearchScope, sources: list[SourceDocument]) -> dict[str, Any]:
        is_model_mode = _is_model_comparison(scope.clarified_question, [target.name for target in scope.comparison_targets])
        entity_label = "候选项" if is_model_mode else "框架"
        included_sources = [source for source in sources if source.included]
        grouped: dict[str, list[SourceDocument]] = defaultdict(list)
        for source in included_sources:
            matched_targets = [tag for tag in source.tags if any(tag == target.name for target in scope.comparison_targets)]
            for matched in matched_targets[:1]:
                grouped[matched].append(source)

        dimension_rows: list[dict[str, str]] = []
        candidate_notes: list[str] = []
        candidate_scores: list[tuple[str, float, str, str, list[str]]] = []

        for target in scope.comparison_targets:
            bucket = grouped.get(target.name, [])
            repo_source = next((source for source in bucket if source.source_type is SourceType.GITHUB_REPO), None)
            docs_source = next((source for source in bucket if source.source_type is SourceType.OFFICIAL_DOC), None)
            readme_source = next((source for source in bucket if source.source_type is SourceType.README), None)
            web_sources = [source for source in bucket if source.source_type is SourceType.WEB_ARTICLE]

            stars = int(repo_source.metadata.get("stargazers_count", 0)) if repo_source else 0
            release_count = int(repo_source.metadata.get("release_count", 0)) if repo_source else 0
            days_since_push = int(repo_source.metadata.get("days_since_push", 999)) if repo_source else 999

            score = 0.0
            if is_model_mode:
                score += 1.8 if docs_source else 0.6
                score += min(len(web_sources) * 0.35, 1.4)
            else:
                score += min(stars / 20000, 3.5)
                score += 1.5 if days_since_push <= 30 else 1.0 if days_since_push <= 120 else 0.4
                score += 1.2 if release_count >= 3 else 0.6 if release_count >= 1 else 0.2
                score += 1.3 if docs_source else 0.4
                score += min(len(web_sources) * 0.3, 0.9)

            lowered_question = scope.clarified_question.lower()
            if not is_model_mode and _contains_any(lowered_question, ("production", "stateful", "workflow", "durable", "生产", "长流程", "状态")) and target.name in {"LangGraph", "Mastra"}:
                score += 1.1
            if not is_model_mode and _contains_any(lowered_question, ("multi-agent", "autonomous", "crew", "多智能体", "协作")) and target.name in {"CrewAI", "AutoGen"}:
                score += 0.9
            if not is_model_mode and _contains_any(lowered_question, ("typed", "pydantic", "schema", "类型", "校验")) and target.name == "PydanticAI":
                score += 1.0
            if is_model_mode and _contains_any(lowered_question, ("中文", "chinese", "研究", "research")) and target.name in {"Qwen", "Kimi"}:
                score += 0.9
            if is_model_mode and _contains_any(lowered_question, ("成本", "性价比", "cost", "pricing")) and target.name == "DeepSeek":
                score += 1.1
            if is_model_mode and _contains_any(lowered_question, ("长上下文", "长文", "context window", "long context")) and target.name == "Kimi":
                score += 1.0
            if is_model_mode and _contains_any(lowered_question, ("openai-compatible", "兼容", "sdk", "api")) and target.name in {"Qwen", "DeepSeek", "Kimi"}:
                score += 0.8

            best_fit = "适合做通用探索，但定位相对均衡。"
            if target.name == "LangGraph":
                best_fit = "更适合需要持久状态、长流程和生产级可控性的 Agent 系统。"
            elif target.name == "CrewAI":
                best_fit = "更适合强调角色分工和多智能体协作的场景。"
            elif target.name == "AutoGen":
                best_fit = "更适合做 Agent 对话编排和研究型实验。"
            elif target.name == "Mastra":
                best_fit = "更适合 TypeScript 团队快速搭建 Agent 工作流产品。"
            elif target.name == "LlamaIndex":
                best_fit = "更适合检索增强、数据接入和知识型 Agent。"
            elif target.name == "Haystack":
                best_fit = "更适合搜索管线和企业级检索应用。"
            elif target.name == "PydanticAI":
                best_fit = "更适合强调类型安全与 Python 开发体验的 Agent 后端。"
            elif target.name == "OpenHands":
                best_fit = "更适合围绕 Coding Agent 的产品探索与实验。"
            elif target.name == "Qwen":
                best_fit = "更适合作为中文能力和多场景覆盖都比较均衡的通用研究模型。"
            elif target.name == "DeepSeek":
                best_fit = "更适合强调推理能力、性价比和技术分析深度的场景。"
            elif target.name == "Kimi":
                best_fit = "更适合重视长上下文处理和中文检索问答体验的场景。"

            watch_out = "仍需结合你的真实业务链路做压测与验证。"
            if is_model_mode:
                if not docs_source:
                    watch_out = "本次运行没有拿到足够可靠的官方接口或能力说明，建议补充厂商文档后再决策。"
                elif len(web_sources) == 0:
                    watch_out = "外部验证资料偏少，建议补充第三方评测、开发者反馈和真实压测结果。"
                else:
                    watch_out = "公开资料无法完整代表真实延迟、价格波动和限流表现，落地前仍需做业务压测。"
            elif days_since_push > 180:
                watch_out = "近期仓库活跃度相对偏弱，需要额外确认维护稳定性。"
            elif not docs_source:
                watch_out = "本次运行没有拿到足够可靠的官方文档证据。"
            elif len(web_sources) == 0:
                watch_out = "外部社区信号偏少，建议补充用户案例和第三方评测。"

            evidence_bits: list[str] = []
            if repo_source:
                evidence_bits.append(f"{stars:,} GitHub stars，近样本 {release_count} 个 release，最近更新于 {days_since_push} 天前")
            if docs_source:
                evidence_bits.append("有可用官方文档")
            if readme_source:
                evidence_bits.append("README 定位清晰")
            if web_sources:
                evidence_bits.append(f"{len(web_sources)} 篇外部补充资料")

            candidate_notes.append(
                f"{target.name}：{('；'.join(evidence_bits)) if evidence_bits else '公开信号较少'}。最适合的场景是：{best_fit}"
            )
            candidate_scores.append((target.name, score, best_fit, watch_out, [source.id for source in bucket]))
            dimension_rows.append(
                {
                    entity_label: target.name,
                    "关键信号": "；".join(evidence_bits) if evidence_bits else "证据较少",
                    "最佳适用场景": best_fit,
                    "风险提示": watch_out,
                }
            )

        candidate_scores.sort(key=lambda item: item[1], reverse=True)
        winner = candidate_scores[0] if candidate_scores else None
        runner_up = candidate_scores[1] if len(candidate_scores) > 1 else None

        recommendation = "当前证据不足，无法给出可靠推荐。"
        if winner:
            recommendation = (
                f"在当前问题范围下，{winner[0]} 更适合作为默认推理后端。"
                if is_model_mode
                else f"在当前问题范围下，{winner[0]} 是最稳妥的默认选择。"
            )
            if runner_up:
                runner_up_focus = runner_up[2].removeprefix("更适合").rstrip("。")
                recommendation += f" 如果你的团队更强调“{runner_up_focus or runner_up[2]}”，那么 {runner_up[0]} 是值得保留的备选。"

        risks_and_unknowns = [
            "公开仓库与文档信号无法完整代表真实生产故障率、延迟成本和团队维护负担。",
            "本次结论基于公开证据，真正落地前仍需要用你的业务流程做验证性评测。",
        ]
        if runner_up and winner:
            risks_and_unknowns.append(
                f"{winner[0]} 与 {runner_up[0]} 之间的差距更偏方向性判断，并不是不可逆的绝对优势。"
            )

        open_questions = (
            [
                "你的真实链路是否需要长上下文检索、多轮资料吸收或高并发限流配额？",
                "你的团队更看重中文推理深度、成本控制，还是与现有 OpenAI-compatible SDK 的兼容性？",
            ]
            if is_model_mode
            else [
                "你的系统是否需要更强的状态持久化、人工介入和可回放能力？",
                "你的团队更看重类型安全和工程约束，还是更看重多智能体灵活性？",
            ]
        )

        summary_lines = []
        runner_up_focus = runner_up[2].removeprefix("更适合").rstrip("。") if runner_up else ""
        if winner:
            if is_model_mode:
                summary_lines.append(
                    f"{winner[0]} 在这次研究中得分最高，原因是它在官方资料完整度、外部验证信号和工程接入适配性之间更均衡。"
                )
            else:
                summary_lines.append(
                    f"{winner[0]} 在这次研究中得分最高，原因是它在仓库活跃度、文档覆盖度和工程化信号之间取得了更平衡的表现。"
                )
        if runner_up:
            summary_lines.append(
                f"{runner_up[0]} 仍然具备竞争力，尤其适合把重点放在“{runner_up_focus or runner_up[2]}”的团队。"
            )
        summary_lines.append("整份报告只使用可回溯来源，因此每个关键判断都可以反查到具体证据。")

        section_specs = [
            {
                "slug": "candidate-landscape",
                "title": "候选方案概览",
                "body": "\n".join(f"- {line}" for line in candidate_notes),
                "citation_source_ids": [source_id for _, _, _, _, source_ids in candidate_scores for source_id in source_ids[:2]],
            },
            {
                "slug": "comparison-table",
                "title": "横向比较",
                "body": "\n".join(
                    f"- {row[entity_label]}：最佳适用场景是“{row['最佳适用场景']}”；关键信号：{row['关键信号']}；主要风险：{row['风险提示']}"
                    for row in dimension_rows
                ),
                "citation_source_ids": [source_id for _, _, _, _, source_ids in candidate_scores for source_id in source_ids[:1]],
            },
            {
                "slug": "recommendation",
                "title": "推荐结论",
                "body": recommendation,
                "citation_source_ids": winner[4][:3] if winner else [],
            },
            {
                "slug": "risks-and-unknowns",
                "title": "风险与未知项",
                "body": "\n".join(f"- {item}" for item in risks_and_unknowns),
                "citation_source_ids": runner_up[4][:2] if runner_up else (winner[4][:2] if winner else []),
            },
        ]

        return {
            "question_restatement": scope.clarified_question,
            "executive_summary": " ".join(summary_lines),
            "candidate_names": [target.name for target in scope.comparison_targets],
            "comparison_dimensions": scope.comparison_dimensions,
            "comparison_table": dimension_rows,
            "recommendation": recommendation,
            "risks_and_unknowns": risks_and_unknowns,
            "open_questions": open_questions,
            "sections": section_specs,
        }


@dataclass
class OpenAICompatibleSettings:
    base_url: str
    api_key: str
    model: str
    temperature: float
    timeout_seconds: float
    output_language: str
    report_audience: str
    report_style: str


class OpenAICompatibleProvider(ResearchProvider):
    def __init__(
        self,
        settings: OpenAICompatibleSettings,
        fallback: HeuristicResearchProvider,
        *,
        provider_id: str,
        provider_label: str,
    ) -> None:
        self._settings = settings
        self._fallback = fallback
        self.id = provider_id
        self.label = provider_label

    async def clarify(
        self,
        *,
        question: str,
        context: str | None,
        selected_targets: list[str] | None,
        comparison_dimensions: list[str] | None,
        must_include: list[str] | None,
    ) -> dict[str, Any]:
        fallback = await self._fallback.clarify(
            question=question,
            context=context,
            selected_targets=selected_targets,
            comparison_dimensions=comparison_dimensions,
            must_include=must_include,
        )
        prompt = {
            "question": question,
            "context": context,
            "selected_targets": selected_targets,
            "comparison_dimensions": comparison_dimensions,
            "must_include": must_include,
            "catalog": [
                {
                    "name": project.name,
                    "repo_full_name": project.repo_full_name,
                    "docs_url": project.docs_url,
                    "homepage_url": project.homepage_url,
                }
                for project in KNOWN_PROJECTS
            ],
            "fallback": fallback,
        }
        try:
            payload = await self._chat_json(
                build_clarifier_system_prompt(
                    output_language=self._settings.output_language,
                    audience=self._settings.report_audience,
                    style=self._settings.report_style,
                ),
                prompt,
            )
        except Exception:
            return fallback
        return {
            "clarified_question": payload.get("clarified_question") or fallback["clarified_question"],
            "research_goal": payload.get("research_goal") or fallback["research_goal"],
            "comparison_dimensions": _unique_preserve_order(
                payload.get("comparison_dimensions") or fallback["comparison_dimensions"]
            ),
            "constraints": _unique_preserve_order(payload.get("constraints") or fallback["constraints"]),
            "must_include": _unique_preserve_order(payload.get("must_include") or fallback["must_include"]),
            "suggested_targets": _unique_preserve_order(payload.get("suggested_targets") or fallback["suggested_targets"]),
            "clarification_questions": _unique_preserve_order(
                payload.get("clarification_questions") or fallback["clarification_questions"]
            ),
            "note": payload.get("note") or fallback.get("note"),
        }

    async def plan(self, scope: ResearchScope) -> list[dict[str, Any]]:
        fallback = await self._fallback.plan(scope)
        prompt = {
            "scope": scope.model_dump(mode="json"),
            "fallback": fallback,
        }
        try:
            payload = await self._chat_json(
                build_planner_system_prompt(
                    output_language=self._settings.output_language,
                    audience=self._settings.report_audience,
                    style=self._settings.report_style,
                ),
                prompt,
            )
        except Exception:
            return fallback
        nodes = payload.get("nodes") if isinstance(payload, dict) else payload
        if not isinstance(nodes, list) or not nodes:
            return fallback
        return nodes

    async def synthesize(self, scope: ResearchScope, sources: list[SourceDocument]) -> dict[str, Any]:
        fallback = await self._fallback.synthesize(scope, sources)
        prompt = {
            "scope": scope.model_dump(mode="json"),
            "sources": [
                {
                    "id": source.id,
                    "title": source.title,
                    "url": source.url,
                    "source_type": source.source_type.value,
                    "summary": source.summary,
                    "snippet": source.snippet,
                    "quality_score": source.quality_score,
                    "tags": source.tags,
                }
                for source in sources
                if source.included
            ],
            "fallback": fallback,
        }
        try:
            payload = await self._chat_json(
                build_synthesizer_system_prompt(
                    output_language=self._settings.output_language,
                    audience=self._settings.report_audience,
                    style=self._settings.report_style,
                ),
                prompt,
            )
        except Exception:
            return fallback
        if not isinstance(payload, dict):
            return fallback
        return {
            "question_restatement": payload.get("question_restatement") or fallback["question_restatement"],
            "executive_summary": payload.get("executive_summary") or fallback["executive_summary"],
            "candidate_names": fallback["candidate_names"],
            "comparison_dimensions": fallback["comparison_dimensions"],
            "comparison_table": fallback["comparison_table"],
            "recommendation": payload.get("recommendation") or fallback["recommendation"],
            "risks_and_unknowns": payload.get("risks_and_unknowns") or fallback["risks_and_unknowns"],
            "open_questions": payload.get("open_questions") or fallback["open_questions"],
            "sections": payload.get("sections") or fallback["sections"],
        }

    async def _chat_json(self, system_prompt: str, payload: dict[str, Any]) -> Any:
        body = {
            "model": self._settings.model,
            "temperature": self._settings.temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._settings.api_key}",
        }
        async with httpx.AsyncClient(
            base_url=self._settings.base_url.rstrip("/") + "/",
            timeout=httpx.Timeout(self._settings.timeout_seconds, connect=min(self._settings.timeout_seconds, 20.0)),
        ) as client:
            response = await client.post("chat/completions", headers=headers, json=body)
            response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return _extract_json_payload(content)


class ProviderManager:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._fallback = HeuristicResearchProvider(settings)
        self._cache: dict[str, ResearchProvider] = {"heuristic": self._fallback}

    def list_presets(self) -> tuple[ProviderPreset, ...]:
        return self._settings.provider_presets

    def describe(self, provider_id: str | None) -> ProviderPreset:
        normalized = (provider_id or self._settings.default_provider_id or "heuristic").strip().lower()
        requested = next((item for item in self._settings.provider_presets if item.id == normalized), None)
        if requested and (requested.enabled or requested.id == "heuristic"):
            return requested

        default_preset = next(
            (
                item
                for item in self._settings.provider_presets
                if item.id == self._settings.default_provider_id and (item.enabled or item.id == "heuristic")
            ),
            None,
        )
        if default_preset:
            return default_preset

        return next(item for item in self._settings.provider_presets if item.id == "heuristic")

    def resolve(self, provider_id: str | None) -> ResearchProvider:
        preset = self.describe(provider_id)
        if preset.id in self._cache:
            return self._cache[preset.id]
        if preset.kind == "heuristic" or not preset.enabled or not preset.base_url or not preset.api_key or not preset.model:
            return self._fallback

        provider = OpenAICompatibleProvider(
            OpenAICompatibleSettings(
                base_url=preset.base_url,
                api_key=preset.api_key,
                model=preset.model,
                temperature=self._settings.llm_temperature,
                timeout_seconds=self._settings.llm_timeout_seconds,
                output_language=self._settings.output_language,
                report_audience=self._settings.report_audience,
                report_style=self._settings.report_style,
            ),
            self._fallback,
            provider_id=preset.id,
            provider_label=preset.label,
        )
        self._cache[preset.id] = provider
        return provider


def build_provider_manager(settings: AppSettings) -> ProviderManager:
    return ProviderManager(settings)
