# 项目任务清单

> 最后更新：2026-08-31。状态以代码、测试和 `03_INTERVIEW_CANON.md` 为准。

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
- [x] 将 Prompt Injection 升级为规范化、中英特征、组合启发式、角色提权和 Base64 载荷组合的多层检测。
- [x] 在客户输入、Tool 返回和 RAG 文档三类信任边界检查直接/间接 Prompt Injection。
- [x] 增加 Qwen3Guard-Gen-0.6B OpenAI-compatible Adapter，将三类信任边界的语义安全结果接入 Risk Engine、Trace 和 Metrics。
- [x] 建立独立 Risk Engine，统一输出风险等级、分数、原因、人工与自动化处置建议。
- [x] 将 Risk Engine 结果接入 LangGraph 路由、QA、Escalation、API、结构化日志、OpenTelemetry Trace 与 Metrics。
- [x] 在 Dataset + Workflow Replay 中增加安全混淆矩阵、Precision / Recall / F1 / 误报率和安全处置正确率。
- [x] 将业务回归 Baseline 扩展到 100 条，增加多语言、安全攻击与安全 hard negative 覆盖。
- [x] 增加真实 LLM Regression 专用入口、smoke/full 套件、Dry Run、付费确认、调用预算和 Token/成本归因。
- [x] 拆分用户咨询页与客服员工后台；普通问题自动回复，异常请求进入受 RBAC 保护的人工审批队列。
- [x] 建立统一 `IntentType`，让规则、LLM Provider、AgentState、Tooling、Risk Engine 和 Agent Evaluation 共用同一套意图枚举与兜底策略。
- [x] 实现 Baseline Workflow Replay V1：固定 100 条完整 Ticket State 回放、六项确定性行为指标、逐 Case 结果和 OTel Trace 同源性能汇总。
- [x] 建立 Evaluation Report 生命周期：清理旧 `report_*.json`、单条评测最多保留 20 份、Baseline 使用时间戳快照与 latest 普通文件副本，并固化完整实验配置。
- [x] Baseline Report 增加 `metric_failure_index`，支持按 Intent、Department、Required/Forbidden Tool、HITL 和 Approval 指标反查失败 Case 与 Trace ID。
- [x] Baseline 每次运行后纯离线生成 Error Analysis 时间戳快照与 latest 副本，覆盖 Failure Breakdown、Intent Confusion Matrix、HITL/Approval mismatch、Tool 问题和逐 FAIL Case 详情。
- [x] 建立 PR Agent Quality Gate：固定 100 条 Dataset 使用 Mock Provider 完整回放 Workflow，校验 Dataset Hash、六项行为指标与新增失败 Case。
- [x] 建立真实 LLM Release Quality Gate：显式付费确认、调用预算、行为/延迟/Token/LLM Calls 阈值与 Actions Artifact。
- [x] 建立门禁后 CD：仅对通过 Release Gate 的同一 Git SHA 构建镜像，发布 GHCR 不可变 SHA Tag 并生成 Provenance Attestation。
- [x] 完成 Resilience V1：LLM/RAG/Tool 统一故障分类、超时、有界 Retry、进程内 Circuit Breaker、Fallback、AgentState/Risk/OTel 联动与高风险禁重试。
- [ ] 引入 Alembic，并为 Feedback Pipeline 新表生成生产 Migration。
- [ ] 增加训练样本人工复核状态、删除请求和数据保留周期。

## P1

- [ ] 建设 Dataset Registry、数据版本和不可变 Snapshot。
- [ ] 增加 Train / Validation / Test 划分及数据泄漏检查。
- [ ] 扩充 Synthetic Golden Dataset，并建立稳定回归基线。
- [ ] 增加 Prompt Registry、内容快照、灰度和回滚门禁。
- [x] 基于首次真实 100 条 Baseline 完成归因修复，Case Pass 由 `0.54` 提升到 `0.99`，固化 Release Gate 阈值与已知失败 Case 白名单。
- [ ] 增加 Tool Calling 完整持久化审计与 `ticket_status_events`。
- [ ] 建设安全样本库、持久化安全事件、策略版本与 Risk Engine 阈值回放校准。
- [ ] 启用 Qwen3Guard Shadow Mode，用中英文安全数据校准 `Controversial / Unsafe` 处置策略。
- [ ] 建设 Resilience V2：分布式 Circuit Breaker、故障注入/混沌测试、写 Tool 幂等键与结果对账，并评估 Queue / DLQ。

## P2

- [ ] 接入 SFT / DPO 训练任务与 Model Registry；当前只导出候选数据。
- [ ] 引入 vLLM 自托管 Serving。
- [ ] 采集 TTFT、TPOT、吞吐、并发、GPU 利用率和 Token 成本。
- [ ] 建立“候选模型离线评测 → 灰度 → 回滚”的发布闭环。

## 已知问题与风险

- [x] 2026-08-27 在 Python 3.12 与关闭外部 OTel exporter 的隔离配置下完成 146 条全量测试；CI / Docker 使用 Python 3.11。
- [ ] 旧的 Python 3.13 `.venv` 仍是混装环境，不再作为项目验收环境。
- [ ] 当前新增表依赖 SQLAlchemy `create_all`，不等同于生产 Schema Migration。
- [ ] 默认 LLM、CRM、OMS 和工单 Adapter 仍为 Mock，尚无真实线上数据。
- [ ] 反馈 Token 目前随 Agent 响应返回，前端仍需安全保存并只在评价提交时使用。
- [ ] 训练候选属于敏感数据资产，生产环境还需对象存储加密、访问审计和生命周期策略。
- [ ] Qwen3Guard 默认未启用且尚无本项目真实运行指标，未知语义变体与误报率仍需通过持续红队样本验证。
- [ ] Risk Engine 阈值尚未基于真实客服运营数据校准，当前采用保守的 high / critical 转人工策略。
- [ ] Circuit Breaker 当前只在单进程内生效；`asyncio.to_thread` 超时不能终止已运行的底层线程，真实写 Tool 上线前必须补幂等和对账。
- [ ] 用户咨询页当前使用演示客户选择器；生产接入前必须绑定真实用户身份与工单归属，并增加限流和异步处理完成通知。
