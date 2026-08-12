# 阶段 7：RAG + Agent 离线评测

## 目标

评测模块采用 `Dataset + Workflow Replay`，对同一次客服 Agent 执行同时评估检索质量、回复质量和 Agent 行为质量。评测独立运行，不改变线上 Workflow 的业务路由。

## Pipeline

```text
Golden Dataset
    ↓
Workflow Replay
    ├── Agent 最终状态
    ├── Retriever Context / Citation
    ├── Tool Calls / Routing / Workflow Path
    └── OpenTelemetry Trace ID
    ↓
Ragas RAG Evaluation + DeepEval Agent Evaluation
    ↓
统一 JSON + Markdown Report
```

Dataset 中每条用例同时包含：

- `reference_answer`、`expected_sources`、`kb_version` 等 RAG 标准数据。
- `agent_expectations`，声明预期路由、Tool、节点顺序、升级和审批行为。

## RAG Evaluation

Ragas 输出：

- `Faithfulness`
- `Answer Relevancy`
- `Context Precision`
- `Context Recall`
- `Citation Hit Rate`

## Agent Evaluation

DeepEval `GEval` 负责语义层行为判断：

- `Task Completion`
- `Policy Compliance`

确定性断言负责必须严格满足的流程约束：

- `Routing Correctness`
- `Tool Correctness`
- `Workflow Correctness`
- `Escalation Correctness`

高风险规则不只依赖 LLM Judge。必需 Tool 缺失、禁止 Tool 被调用、节点顺序错误、人工升级或审批错误都会直接导致用例失败。

## Trace 关联

每次 Replay 在 `evaluation.workflow_replay` OpenTelemetry Span 内执行，LangGraph、LLM、Retriever 和 Tool Span 作为其子链路。报告为每个用例保存 32 位 `trace_id`；失败用例可据此在 Trace 后端定位具体节点。OpenTelemetry 未启用时，报告明确记录 `unavailable`，不会伪造 Trace ID。

## 代码参考

- Pipeline 与统一报告：`src/evaluation/offline_rag.py`
- Agent 行为评测：`src/evaluation/agent_evaluation.py`
- Golden Dataset：`evaluation/golden/support_qa_golden.json`
- 独立入口：`scripts/run_agent_eval.py`
- 可选依赖：`requirements/eval.txt`

## 运行

正式评测需要有效的 `OPENAI_API_KEY`：

```bash
python scripts/run_agent_eval.py \
  --rag-engine ragas \
  --agent-engine deepeval
```

无网络 CI 烟测：

```bash
python scripts/run_agent_eval.py \
  --rag-engine local \
  --agent-engine local \
  --limit 3
```

统一产物：

- `evaluation/reports/evaluation_latest.json`
- `evaluation/reports/evaluation_latest.md`

`local` 只用于确定性回归验证，不能作为 Ragas 或 DeepEval 正式评测结果对外引用。
