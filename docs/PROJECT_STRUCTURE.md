# 项目结构

## 根目录

```text
.
├── backend
├── docs
├── frontend
├── compose.yml
├── README.md
├── README_EN.md
├── CONTRIBUTING.md
├── ROADMAP.md
└── FAQ.md
```

## backend

后端负责研究任务编排、检索、持久化与报告生成。

### 关键文件

- `backend/app/main.py`
  FastAPI 入口，暴露研究任务、来源、报告和导出接口。
- `backend/app/research_service.py`
  研究主流程编排器，负责 `clarify / plan / retrieve / synthesize / validate`。
- `backend/app/retrieval.py`
  多源检索层，负责 `SearchProvider` 抽象和来源归一化。
- `backend/app/providers.py`
  模型 provider 适配层，当前以 `DeepSeek` 为主。
- `backend/app/store.py`
  基于 `PostgreSQL` 的持久化实现。
- `backend/app/schemas.py`
  核心对象定义，如 `ResearchRun / SourceDocument / Citation / FinalReport`。

## frontend

前端负责搜索入口、研究详情、来源资料库和报告展示。

### 关键目录

- `frontend/src/app`
  Next.js 路由入口。
- `frontend/src/components`
  首页、详情页、报告页、图表与品牌组件。
- `frontend/src/lib`
  前后端接口、类型和文案映射。

## docs

文档目录用于支持开源展示、演示、简历和面试讲解。

- `ARCHITECTURE.md`
- `CASE_STUDIES.md`
- `DEMO_SCRIPT.md`
- `INTERVIEW_PITCH.md`
- `RESUME_NOTES.md`
- `PROVIDER_CONFIG.md`
- `GITHUB_ABOUT.md`
- `assets/`

## 设计原则

- 研究链路与页面结构尽量一一对应
- 检索源统一归一化到 `SourceDocument`
- 结论输出必须能回到 `Citation`
- 质量约束不依赖前端，而是在后端显式建模
