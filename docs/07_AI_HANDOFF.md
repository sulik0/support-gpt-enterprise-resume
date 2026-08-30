# AI 开发交接

> 本文档面向 Codex、GPT、Claude Code、Cursor 等后续 AI。参与开发前必须先读 `00_PROJECT_CONTEXT.md`，再按任务查阅本文档与对应专题文档。

## 阅读顺序

1. `00_PROJECT_CONTEXT.md`：唯一项目概览。
2. `03_INTERVIEW_CANON.md`：唯一可对外引用的事实口径。
3. `01_ARCHITECTURE.md`：工程架构、State 与模块边界。
4. `02_BUSINESS_LOGIC.md`：业务流程与结束条件。
5. `04_DECISIONS.md`：已确定的技术决策。
6. `05_ENGINEERING_GUIDE.md`：启动、API、测试、评测、可观测与部署。
7. `06_PROMPTS.md`：Prompt 策略与变更约束。
8. `08_TODO.md`：当前任务、技术债和风险。
9. `09_INTERVIEW_QA.md`：面试问题的统一回答。

## 当前系统快照

- 后端：FastAPI + SQLAlchemy Async + JWT/RBAC。
- Agent：LangGraph StateGraph，节点为 Analyzer、Tooling、Retriever、Resolver、QA 和 Escalation。
- 执行：Analyzer 后 Tooling/Retriever 并行，安全强命中直接短路；之后 Resolver、QA、Escalation。
- LLM：默认 Mock，保留 `mock/openai/azure`；`openai` 为通用 OpenAI-compatible Provider。
- 优化：Analyzer 规则优先，Analyzer/QA 可使用小模型，Resolver 裁剪 Context，QA 仅返回最小 JSON。
- RAG：ChromaDB + 关键词/向量 Hybrid Search + 轻量 rerank + version/category filter + citation。
- Tool：Mock CRM/OMS/Ticket Adapter 通过 ToolRegistry 暴露，具备 Schema、RBAC、风险和审计边界。
- 故障治理：LLM/RAG/Tool 统一超时、有界 Retry、进程内 Circuit Breaker 与 Fallback；高风险/非幂等写 Tool 禁止自动重试。
- 安全：确定性多层规则 + 可选 Qwen3Guard-Gen-0.6B + Risk Engine + 输出过滤 + HITL。
- Memory：Redis 短期状态，PostgreSQL 长期持久化，Redis 不可用时回退数据库。
- 可观测：OpenTelemetry 唯一采集，OTLP 统一导出，Collector 分发 LangSmith Trace 和 Prometheus Metrics。
- 评测：Ragas + DeepEval + 确定性 Agent/Security Evaluator，固定 100 条 Baseline 支持真实 Workflow Replay。
- 反馈：AgentRun、FeedbackEvent 和 AgentRunLink 关联 Trace、用户评价、人工修正与 Evaluation。
- 前端：用户咨询页 + 客服审批后台 + Agent 可观测页。打开工单详情只读持久化结果，不重复调用 Agent。

## 必须保持的设计

1. 默认 Mock 模式必须能在无 API Key、无 Redis、无 Collector 时启动和测试。
2. CRM、OMS、Ticketing 与 Refund 仍是 Mock Adapter，不得写成已接入真实企业系统。
3. 所有业务 Tool 必须经过 ToolRegistry，不得从 Agent 直接调 Adapter。
4. 工单状态只能经 TicketStateMachine 流转。
5. Prompt Injection 或 Jailbreak 强命中必须短路 Tool/RAG/Resolver/QA，隔离不可信上下文并转人工。
6. 退款、投诉、越权写操作、低置信度、低 QA 或高风险结果必须保持 HITL 策略。
7. OpenTelemetry 是唯一 Trace/Metrics 采集路径，不得恢复 LangSmith SDK `traceable` 双轨采集。
8. Trace 上报前必须脱敏、密钥过滤和敏感业务字段过滤；遥测失败不影响主流程。
9. LLM 默认使用用户当前输入语言回复，除非用户明确要求切换。
10. Evaluation 必须真实 Replay 当前 Workflow，报告保留实验配置与 Trace ID；不得通过降低 Dataset 期望来伪造通过率。
11. 打开工单详情不得触发新 Workflow，只加载已保存 AgentRun 和 Approval。

## 代码定位

| 范围 | 目录/文件 |
|---|---|
| FastAPI 路由与启动 | `src/main.py` |
| 环境配置 | `src/config.py` |
| LangGraph Workflow / AgentState | `src/agents/graph.py` |
| 意图枚举 | `src/models/intents.py` |
| LLM Provider 与 Prompt | `src/llm/provider.py` |
| Tool Registry / Adapter | `src/tools/` |
| RAG | `src/rag/` |
| Guardrails / Risk | `src/guardrails/`、`src/risk/` |
| Resilience | `src/resilience/` |
| Memory | `src/memory/` |
| Approval | `src/approval/` |
| Trace / Metrics / 脱敏 | `src/observability/` |
| Evaluation | `src/evaluation/`、`evaluation/`、`scripts/run_*eval.py` |
| Feedback | `src/feedback/`、`scripts/export_training_candidates.py` |
| React 前端 | `frontend/src/` |
| 部署与监控 | `deployment/`、`monitoring/` |

## 修改流程

1. 先检查 `git status`，保留用户未相关改动。
2. 阅读相关实现和测试，不根据文档猜测当前代码。
3. 以最小范围实现，函数可增加一两行精简中文注释，主要类应有简短中文职责说明。
4. 对新行为增加确定性测试；若影响 Agent，评估 Baseline 兼容性。
5. 运行 `git diff --check`、相关 pytest，高风险改动运行全量 pytest。
6. 同步 `00_PROJECT_CONTEXT.md`、`03_INTERVIEW_CANON.md`、`08_TODO.md` 中受影响的完成状态与边界。
7. 提交时不得包含 `.env`、评测运行产物、API Key、训练数据或无关用户文件。

## 已知限制

- 真实 CRM/OMS/Ticketing 尚未接入。
- 多轮 Memory 已存储，尚未系统性注入 Prompt。
- Tool 调用记录可返回，但 Registry 完整审计尚未持久化。
- Qwen3Guard 默认关闭，Risk Engine 阈值尚未基于真实运营数据校准。
- Feedback Pipeline 只生成脱敏 SFT/DPO 候选，尚无 Dataset Registry、训练与发布闭环。
- Docker Compose/Kubernetes 是可复现模板，不代表生产上线。
- Resilience 当前是单进程 V1，没有分布式 Breaker、Queue / DLQ 和写 Tool 幂等对账。
- 真实 Baseline V1 在同一固定 100 条 Dataset 上经归因优化后通过率为 0.99，仍不等于生产业务指标。

## 当前优先级

1. 为 Feedback 表引入 Alembic migration。
2. 为 Resilience V1 增加故障注入、多副本 Breaker 与写 Tool 幂等对账设计。
3. 建设 Dataset Registry、人工复核与数据保留策略。
4. 增强 Tool 与 Ticket State 的持久化审计。
5. 使用 Shadow Mode 校准 Qwen3Guard 与 Risk Engine。

最终任务清单始终以 `08_TODO.md` 为准。
