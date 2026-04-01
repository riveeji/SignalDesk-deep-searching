# Provider 配置

`SignalDesk / 研策台` 现在只保留一个外部模型入口：`DeepSeek`。

系统仍然内置 `heuristic` 回退路径，所以即使暂时没有配置 API Key，也可以完整跑通：

- 澄清
- 规划
- 检索
- 综合
- 报告导出

## DeepSeek

```powershell
DEEP_RESEARCH_DEFAULT_PROVIDER=deepseek
DEEP_RESEARCH_DEEPSEEK_API_KEY=your_key
DEEP_RESEARCH_DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEP_RESEARCH_DEEPSEEK_MODEL=deepseek-chat
```

## 未配置 Key 时

如果 `DEEP_RESEARCH_DEEPSEEK_API_KEY` 为空，系统会自动退回：

```powershell
heuristic
```

这时首页仍然能正常使用，只是推理与综合阶段会由内置启发式逻辑完成。

## 运行参数

```powershell
DEEP_RESEARCH_OUTPUT_LANGUAGE=简体中文
DEEP_RESEARCH_REPORT_AUDIENCE=需要快速做出技术判断的工程团队
DEEP_RESEARCH_REPORT_STYLE=结构化、克制、可追溯、结论明确
DEEP_RESEARCH_WEB_RESULTS_PER_TARGET=2
DEEP_RESEARCH_LLM_TEMPERATURE=0.15
DEEP_RESEARCH_LLM_TIMEOUT_SECONDS=60
```

这些参数会影响：

- 报告语言
- 报告语气
- 检索深度
- 模型采样温度
- 外部调用超时

## 推荐使用方式

1. 先配置 `DeepSeek` 并验证 `/health` 返回的默认 provider 是 `deepseek`
2. 在首页直接输入研究问题并发起任务
3. 进入任务详情页查看研究计划、来源证据和执行轨迹
4. 打开报告页导出 `Markdown / PDF`
