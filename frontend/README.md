# 研策台前端

前端使用 `Next.js + TypeScript + Tailwind CSS`，负责承载 `研策台` 的四个主界面：

- 研究工作台
- 任务详情页
- 最终报告页
- 来源资料库

## 本地启动

```bash
npm install
npm run dev
```

默认地址是 `http://127.0.0.1:3000`。

## 依赖后端

前端会读取 `NEXT_PUBLIC_API_BASE`，默认请求 `http://127.0.0.1:8000`。

如果你只想跑前端界面，请先保证后端和 PostgreSQL 已启动，否则工作台会显示加载失败。

## 当前页面结构

- 首页：`src/app/page.tsx`
- 任务详情：`src/app/research/[runId]/page.tsx`
- 报告页：`src/app/research/[runId]/report/page.tsx`
- 来源资料库：`src/app/sources/page.tsx`

## 核心组件

- `src/components/research-workspace.tsx`
- `src/components/research-run-detail.tsx`
- `src/components/report-view.tsx`
- `src/components/source-library.tsx`
- `src/components/brand-mark.tsx`
