# 贡献指南

欢迎为 `SignalDesk / 研策台` 提交 issue 或 PR。

这个项目目前仍处于快速迭代阶段，比较适合小步、明确、可验证的改动。

## 推荐贡献方向

- 检索源扩展
- 来源质量排序与去重
- 报告展示与导出优化
- Human-in-the-loop 体验
- 文档、示例和部署说明

## 开发前建议

1. 先阅读 [README.md](README.md) 了解项目定位  
2. 再看 [ROADMAP.md](ROADMAP.md) 确认方向是否一致  
3. 涉及架构或流程修改时，先看 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## 本地开发

### 后端

```powershell
pip install -r backend\requirements.txt
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

### 前端

```powershell
cd frontend
npm install
npm run dev
```

### 数据库

```powershell
docker compose -p deepresearch up -d postgres
```

## 提交规范

- 保持改动范围聚焦，不要顺手重构无关代码
- 如果是功能改动，优先同步更新文档
- 如果改动会影响研究结果质量，请补说明或回归案例
- 提交信息尽量直接、简洁

## PR 建议包含的信息

- 改了什么
- 为什么要改
- 对用户或系统行为有什么影响
- 如何验证

## 不建议直接提交的大改动

- 一次性引入大规模多 agent 编排
- 未验证的自动化抓取策略
- 没有文档说明的架构重写

这类改动建议先开 issue 讨论。
