# 简历写法

## 一句话项目描述

独立开发一个面向 `AI / Agent 技术选型` 的 `Deep Research Agent`，支持问题澄清、研究规划、多源证据检索、引用链报告生成，以及证据不足时的结论降级。

## 简历要点版本一

- 基于 `Next.js + FastAPI + PostgreSQL + DeepSeek` 搭建深度研究工作台，将技术选型流程拆分为 `澄清 / 规划 / 检索 / 综合 / 校验` 五个可追踪阶段。
- 设计 `ResearchRun / ResearchPlanNode / SourceDocument / RunStep / Citation / FinalReport` 六类核心对象，实现研究任务、来源池、步骤轨迹和最终报告的全链路持久化。
- 实现可插拔 `SearchProvider` 检索层，聚合 `GitHub API + 官方文档 + Web Search + Crossref`，并支持手动导入 `DOI / BibTeX / 外部链接`。
- 增加 `coverage summary / verdict / recommendation_confidence / missing_evidence` 机制，在证据失衡时自动降级结论，降低答非所问和强结论幻觉风险。

## 简历要点版本二

- 开发 AI 技术选型研究系统，支持用户输入复杂问题后自动澄清范围、生成研究计划、抓取多源证据并输出带引用链的结构化报告。
- 用 PostgreSQL 建模并持久化研究任务、计划节点、来源、步骤、引用和报告，支持后端重启后恢复历史研究任务。
- 设计 human-in-the-loop 机制，在问题不清晰时进入 `waiting_human`，在来源质量不佳时支持人工排除来源并从综合阶段重跑。
- 支持 Markdown / PDF 导出和来源手动补充，使研究结果可用于面试演示、技术选型记录和后续复盘。

## 可以直接说的真实结果

- 多候选选型题可稳定生成 `15` 条来源、`35` 条引用
- 单次完整研究耗时约 `2~3` 分钟
- 证据失衡时系统会自动降级为 `insufficient_evidence`

## 面试时怎么解释这个项目不是普通 LLM 应用

- 它不是直接问模型，而是先做 `clarify`
- 它不是单源搜索，而是有 `SearchProvider` 检索层
- 它不是黑盒结果，而是有 `RunStep + Citation`
- 它不是盲目自动化，而是支持人工补充和人工排除
- 它不是一律给结论，而是有 `Answer Validator`

## 如果面试官问你最有价值的设计点

优先答这三个：

1. `问题澄清`
   防止一开始就围绕模糊问题胡乱搜索
2. `证据覆盖建模`
   用 coverage matrix 显式判断每个候选项是否都被搜到
3. `结论降级机制`
   证据不够时不硬推，而是输出 `missing_evidence`

## 如果面试官追问“为什么这个项目像 Agent”

可以直接答：

- 会先判断问题是否清晰
- 会自己生成计划
- 会调用不同来源搜证
- 会根据证据写报告
- 会在不确定时停下来让人参与

这 5 点加起来，才构成一个真正的 research agent。
