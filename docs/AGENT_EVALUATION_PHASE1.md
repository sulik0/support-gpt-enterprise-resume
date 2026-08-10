# 第一阶段 Agent Evaluation

## 目标

本阶段在不改变现有 LangGraph 业务节点、路由和审批规则的前提下，增加两类评估能力：

1. 使用 LangSmith 记录 LangGraph workflow、LLM 调用、Retriever 和 Tool 调用的 Trace。
2. 使用独立 evaluation dataset 执行 RAG 离线评测，输出 JSON 和 Markdown 报告。

## LangSmith Trace

以下调用会在同一个 workflow Trace 下形成子 Span：

| 对象 | Run Type | Trace 名称 |
|---|---|---|
| LangGraph workflow | `chain` | `supportgpt.langgraph.workflow` |
| LLM 意图分析 | `llm` | `supportgpt.llm.analyze_ticket` |
| LLM 回复生成 | `llm` | `supportgpt.llm.generate_resolution` |
| LLM QA | `llm` | `supportgpt.llm.evaluate_qa` |
| Hybrid Retriever | `retriever` | `supportgpt.rag.hybrid_retriever` |
| ToolRegistry | `tool` | `supportgpt.tool.call` |

Trace 序列化会对 email、电话号码和 secret/token 类字段做脱敏，只影响上报数据，不修改业务 State。

在 `.env` 中配置：

```dotenv
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://localhost:4318/v1/traces
```

Agent Evaluation 与线上请求使用同一套 OpenTelemetry Trace。应用不启用 LangSmith SDK 直连；如需在 LangSmith 查看 Trace，由 OpenTelemetry Collector 通过 OTLP 统一转发。

## 离线评测数据集

Golden dataset 位于 `evaluation/golden/support_qa_golden.json`，当前用例仅使用项目已有的 seed knowledge，覆盖：

- 退款 v1：30 天窗口、active dispute 限制、到账时间。
- 退款 v2：60 天窗口、5% 手续费、原卡退回。
- API 异常：504、backup routing cluster、AWS us-east-1、cache 处理。
- 账户设置：Preferences 路径、email validation、API key access。

每条用例包含 `query`、`reference_answer`、`expected_sources`、`category`、`risk_level` 和 `kb_version`。

## 正式 Ragas 评测

先安装可选评测依赖、配置评委模型密钥，并确保已完成知识库 seed：

```bash
pip install -r requirements/eval.txt
python scripts/seed_kb.py
export OPENAI_API_KEY=<your-key>
python scripts/run_agent_eval.py --engine ragas
```

正式模式使用 Ragas 评估：

- Faithfulness
- Answer Relevancy
- Context Precision
- Context Recall

为了与当前 `langchain<0.3` 技术栈保持兼容，`requirements/eval.txt` 固定使用 Ragas `0.1.x` 的 dataset schema。正式模式如果缺少 API key 或依赖不兼容会直接失败，不会将本地 proxy 伪装成 Ragas 结果。

## 无网络回归烟测

```bash
python scripts/run_agent_eval.py --engine local
```

`local` 使用确定性文本 proxy，用于 CI 和管道连通性检查，报告中会明确标识 engine，不得作为正式 Ragas 分数引用。

## 评测报告

运行后生成：

- `evaluation/reports/agent_eval_latest.json`
- `evaluation/reports/agent_eval_latest.md`

报告包含四项 Ragas 指标的汇总分和用例级分数，同时附带 citation hit rate、实际检索来源和 workflow error，便于回归对比和问题定位。
