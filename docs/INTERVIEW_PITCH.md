# 2 分钟面试讲稿

## 版本一

这个项目叫 `SignalDesk / 研策台`，我把它定义成一个面向 `AI / Agent 技术选型` 的 `Deep Research Agent`。  
它不是聊天壳子，而是把一次技术研究拆成 `澄清、规划、检索、综合、校验` 五个阶段。

用户在首页只需要输入一个复杂问题，比如 `LangGraph、PydanticAI 和 Mastra 哪个更适合作为 Python Agent 底座`。  
系统会先判断问题是不是足够清晰，如果范围不够明确，就进入 `waiting_human` 让用户补充候选项或比较维度。

范围锁定之后，后端会生成研究计划，然后通过可插拔的检索层去聚合 `GitHub API`、官方文档、网页结果、Crossref，以及手动导入的学术来源。  
这些来源会被统一保存成 `SourceDocument`，再在综合阶段生成带引用链的结构化报告。

这个项目我比较看重的一点，是它不会在证据不足时硬给结论。  
我加了 `coverage summary` 和 `answer quality` 机制，会检查每个候选项有没有最低覆盖，如果覆盖失衡，就把报告降级成 `insufficient_evidence`，同时告诉用户缺了哪些证据。

技术上我用的是 `Next.js + FastAPI + PostgreSQL + DeepSeek`。  
前端负责搜索入口、研究详情和报告页；后端负责 agent 编排、来源归一化、引用生成和持久化。  
我还支持来源排除、阶段级重跑、Markdown/PDF 导出，所以它更像一个研究产品，而不是一次性的 demo。

## 版本二

我做这个项目的出发点是，很多 AI 项目只会聊天，但真实技术选型需要先收敛问题、再系统搜证，最后才能比较和决策。  
所以我做了一个 `Deep Research Agent`，而不是一个问答页面。

核心流程是：

1. `Clarifier` 先把模糊问题收紧成结构化研究范围  
2. `Planner` 生成研究计划  
3. `Retriever` 从 GitHub、官方文档、Web、学术元数据里收集证据  
4. `Synthesizer` 输出带引用链的报告  
5. `Answer Validator` 检查是否对题、是否覆盖完整、能不能给结论

工程上的亮点主要有三点：

- 第一，研究全过程是持久化的，我定义了 `ResearchRun / SourceDocument / RunStep / Citation / FinalReport` 这些核心对象，后端重启后还能恢复。
- 第二，系统支持人工参与，比如范围澄清、手动导入来源、排除弱来源、从某个阶段重跑。
- 第三，我专门处理了“答非所问”和“证据不足仍硬答”的问题，用 `verdict / recommendation_confidence / missing_evidence` 这些字段约束模型输出。

所以我会把它定义成一个 `面向 AI/Agent 技术选型的可解释研究系统`，而不是单纯的 LLM 应用。
