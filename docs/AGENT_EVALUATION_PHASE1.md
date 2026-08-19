# 第一阶段 Agent Evaluation

## 目标

本阶段在不改变现有 LangGraph 业务节点、路由和审批规则的前提下，增加两类评估能力：

1. 使用 LangSmith 记录 LangGraph workflow、LLM 调用、Retriever 和 Tool 调用的 Trace。
2. 使用独立 evaluation dataset 执行 RAG、Agent 和 Security 离线评测，输出统一 JSON 和 Markdown 报告。

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

Baseline dataset 位于 `evaluation/baseline/supportgpt_baseline_100.json`，包含 100 条业务回归样本，覆盖退款、订单、账户、API 故障、信息不足、RAG、Tool Calling、人工升级、多语言、Prompt Injection、Jailbreak 和安全 hard negative。每条 Baseline 还可以通过 `customer_id` 绑定现有 Mock CRM/OMS/工单数据，并使用 `tags` 统计覆盖面。

```bash
LLM_PROVIDER=mock \
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT= \
OTEL_EXPORTER_OTLP_METRICS_ENDPOINT= \
python scripts/run_agent_eval.py \
  --dataset evaluation/baseline/supportgpt_baseline_100.json \
  --rag-engine local \
  --agent-engine local
```

Baseline 中包含针对已知能力边界的期望断言，失败样本用于暴露回归或待建设能力，不应通过降低期望来换取通过率。

## Security Evaluation

Security Evaluation 是独立的确定性指标引擎，不使用 LLM Judge。它从 Dataset 的 `security_expectations` 或 `prompt_injection` / `jailbreak` 标签读取攻击真值，并根据 Workflow Replay 的实际输出计算：

- 检测指标：TP、FP、TN、FN、Precision、Recall、F1、Accuracy、False Positive Rate 和 False Negative Rate。
- 处置指标：自动化阻断率、安全短路率、不可信上下文隔离率、人工介入率和 critical 风险标记率。
- 分组指标：按 `user_input` / `tool_result` / `rag_document` 信任边界和攻击类型统计检测 Recall。
- 用例结果：每条用例记录检测分类、通过状态、处置检查、失败原因和 OpenTelemetry Trace ID。

普通退款或投诉因业务风险转人工，不会被计为安全检测命中。Baseline 100 现有 14 条攻击样本与 86 条非攻击样本，其中包含 6 条安全语义 hard negative，用于同时评估攻击召回和误报。

## 正式 Ragas 评测

先安装可选评测依赖、配置评委模型密钥，并确保已完成知识库 seed：

```bash
pip install -r requirements/eval.txt
python scripts/seed_kb.py
export OPENAI_API_KEY=<your-key>
python scripts/run_agent_eval.py --rag-engine ragas --agent-engine deepeval
```

正式模式使用 Ragas 评估：

- Faithfulness
- Answer Relevancy
- Context Precision
- Context Recall

为了与当前 `langchain<0.3` 技术栈保持兼容，`requirements/eval.txt` 固定使用 Ragas `0.1.x` 的 dataset schema。正式模式如果缺少 API key 或依赖不兼容会直接失败，不会将本地 proxy 伪装成 Ragas 结果。

## 无网络回归烟测

```bash
python scripts/run_agent_eval.py --rag-engine local --agent-engine local
```

`local` 使用确定性文本 proxy，用于 CI 和管道连通性检查，报告中会明确标识 engine，不得作为正式 Ragas 分数引用。

## 评测报告

运行后生成：

- `evaluation/reports/evaluation_latest.json`
- `evaluation/reports/evaluation_latest.md`

报告包含 RAG、Agent 和 Security 三类汇总指标与用例级结果，同时附带 citation hit rate、实际检索来源、Workflow Path、workflow error 和 Trace ID，便于回归对比和失败链路定位。
