# 项目任务清单

> 最后更新：2026-08-12。状态以代码、测试和 `03_INTERVIEW_CANON.md` 为准。

## P0

- [x] 建立 `AgentRun`、`AgentRunLink`、`FeedbackEvent` 数据模型。
- [x] 将 `/chat`、`/suggest-response` 的执行快照与 OpenTelemetry Trace ID 关联。
- [x] 增加基于 `agent_run_id + feedback_token` 的用户评价 API。
- [x] 将人工审批通过、修改和拒绝自动沉淀为反馈事件。
- [x] 将在线与离线 Evaluation 结果关联到 Agent Run。
- [x] 增加 PII / 密钥过滤、Tool 字段白名单、会话 HMAC 摘要和独立事务 fail-open。
- [x] 增加 SFT / DPO 候选质量门控、去重、原子导出和 Manifest。
- [x] 跑通 FastAPI `/health` -> Workflow -> Ticket / AgentRun -> FeedbackEvent 的 MVP 持久化链路。
- [x] 修复 LangGraph State 缺少 `sla_hours` 导致的 Workflow 运行失败。
- [x] 固定核心 LangChain / LangGraph / ChromaDB 兼容版本，并使用版本化 ChromaDB 本地目录。
- [ ] 引入 Alembic，并为 Feedback Pipeline 新表生成生产 Migration。
- [ ] 增加训练样本人工复核状态、删除请求和数据保留周期。

## P1

- [ ] 建设 Dataset Registry、数据版本和不可变 Snapshot。
- [ ] 增加 Train / Validation / Test 划分及数据泄漏检查。
- [ ] 扩充 Synthetic Golden Dataset，并建立稳定回归基线。
- [ ] 增加 Prompt Registry、内容快照、灰度和回滚门禁。
- [ ] 增加 Tool Calling 完整持久化审计与 `ticket_status_events`。

## P2

- [ ] 接入 SFT / DPO 训练任务与 Model Registry；当前只导出候选数据。
- [ ] 引入 vLLM 自托管 Serving。
- [ ] 采集 TTFT、TPOT、吞吐、并发、GPU 利用率和 Token 成本。
- [ ] 建立“候选模型离线评测 → 灰度 → 回滚”的发布闭环。

## 已知问题与风险

- [x] 在新 Python 3.12 隔离环境完成 `pip check` 和 60 条全量测试；CI / Docker 使用 Python 3.11。
- [ ] 旧的 Python 3.13 `.venv` 仍是混装环境，不再作为项目验收环境。
- [ ] 当前新增表依赖 SQLAlchemy `create_all`，不等同于生产 Schema Migration。
- [ ] 默认 LLM、CRM、OMS 和工单 Adapter 仍为 Mock，尚无真实线上数据。
- [ ] 反馈 Token 目前随 Agent 响应返回，前端仍需安全保存并只在评价提交时使用。
- [ ] 训练候选属于敏感数据资产，生产环境还需对象存储加密、访问审计和生命周期策略。
