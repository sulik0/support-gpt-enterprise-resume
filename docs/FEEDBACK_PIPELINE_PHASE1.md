# Feedback Pipeline 第一阶段

## 目标

第一阶段将线上 Agent 运行数据、用户评价、人工审批修正、OpenTelemetry Trace 和质量评测结果关联起来，形成可审计、可脱敏、可导出的训练数据候选池。

该阶段只建设数据闭环，不执行模型训练，也不会自动把未经审核的数据送入 SFT 或 DPO。

## 数据链路

```text
Agent Workflow
    ↓
AgentRun
    ├── request_id / trace_id
    ├── Prompt / Workflow / Model / KB Version
    ├── Input / Output / Citation / Tool Calls
    └── QA / Hallucination / Token / Latency
         ↓
FeedbackEvent
    ├── User Rating
    ├── Human Review / Correction
    └── Evaluation Result
         ↓
Quality Gate + PII Redaction + Deduplication
         ↓
SFT Candidates / DPO Candidates
```

## 核心数据模型

### AgentRun

`AgentRun` 是 Feedback Pipeline 的统一关联主键。每次 `/chat` 或 `/suggest-response` 执行后保存：

- `request_id`、OpenTelemetry `trace_id` 和不可逆的 `session_id_hash`。
- `prompt_version`、`workflow_version`、`model_provider`、`model_name`、`kb_version`。
- 脱敏后的用户输入和 Agent 输出。
- Workflow Path、Tool Calls、Citation。
- QA Score、幻觉标记、升级和审批标记。
- Token、延迟和 Workflow Error。

### FeedbackEvent

所有反馈使用统一事件模型：

- `source=user`：用户评分和评论。
- `source=human_review`：人工通过、拒绝或修改 AI 草稿。
- `source=evaluation`：在线或离线评测指标与 Pass/Fail 结论。

每个事件保存 `agent_run_id` 和 `trace_id`，可以从低质量反馈直接定位完整 Agent Trace。

数据库约束保证每个 Run 对每种 `source` 只有一条当前反馈记录。用户反馈不可变；Evaluation 采用 Latest Snapshot + `sequence` 更新，并在指标中保留有限历史，控制数据量同时避免旧结论继续参与质量门控。

### AgentRunLink

使用通用关联表连接 `AgentRun` 与审批记录。这样无需修改已有审批表，也为后续关联 CRM 事件、投诉记录和实验版本保留扩展点。

## API

### 用户反馈

```http
POST /feedback/user
```

```json
{
  "agent_run_id": "run-uuid",
  "feedback_token": "one-time-returned-high-entropy-token",
  "rating": 5,
  "comment": "回复解决了问题",
  "idempotency_key": "client-generated-key"
}
```

`/chat` 与 `/suggest-response` 在创建 Agent Run 时返回一次高熵 `feedback_token`，数据库仅保存其 SHA-256 摘要。反馈接口必须校验 Run ID 和 Token；每个 Run 只接受一条不可变用户反馈，`idempotency_key` 用于客户端重试协议，服务端即使收到不同 Key 也不会重复采集。

### 反馈关联查询

```http
GET /feedback/runs/{agent_run_id}
```

仅 `manager` 或 `admin` 可以查看完整 Run、版本信息及 Feedback Event。

### 评测关联

`POST /evaluate-response` 可选传入 `agent_run_id` 与 `external_ref`。普通评测保持原有访问方式；只有 `manager` 或 `admin` 可以把评测结果关联到 Agent Run，避免未授权数据影响训练质量门控。

对于统一离线评测报告，可在 replay 或回放 Dataset 用例中提供已有 `agent_run_id`，再执行：

```bash
python scripts/import_evaluation_feedback.py \
  --report evaluation/reports/evaluation_latest.json
```

脚本会把 RAG / Agent 指标和 Pass/Fail 结论批量回写为 Evaluation Event；默认 Synthetic Golden Dataset 没有关联线上 Run，因此会被安全跳过。

离线用例只有在 Agent Evaluation 通过、Citation 命中且四项 RAG 指标平均分达到配置阈值时，才会成为“评测通过”事件；单条导入失败不会中断整批任务。

## 训练数据质量门控

### SFT 候选

满足任意一种条件：

1. 人工通过或修改后的最终回复；
2. 高评分用户反馈、评测通过、无幻觉且无 Workflow Error 同时成立。

同一 Run 的可信评测使用单条最新快照和递增 `sequence`；更新时保留最近 19 条历史指标，质量门控只采用最新结果，避免旧的 Pass 结论覆盖后续回归失败。

### DPO 候选

仅当人工修改后的回复与原始 AI 草稿不同时生成：

- `chosen`：人工修正回复。
- `rejected`：原始 AI 回复。

用户低评分不会被直接当作 DPO `rejected`，因为没有可信的 `chosen` 对照答案。

## 数据保护

- 输入、输出、评论和人工修正进入反馈域前统一 PII 脱敏。
- 原始 `session_id` 不进入反馈域，仅保存 HMAC-SHA256 摘要。
- Agent Run 和审批关联使用独立数据库事务，采集失败不会回滚客服主流程。
- Tool Call 只保存允许的审计字段，不保存 Tool Result 中的客户业务数据。
- 训练候选继承脱敏后的文本。
- 导出文件默认写入 `evaluation/training_candidates/`，该目录不会提交 Git。

## 导出命令

```bash
python scripts/export_training_candidates.py
```

生成：

- `sft_candidates.jsonl`
- `dpo_candidates.jsonl`
- `manifest.json`，记录数据 Schema、生成时间、质量门控阈值和样本数量。

每条样本保留 `agent_run_id`、`trace_id` 和模型、Prompt、Workflow、KB 版本，便于数据审计和回溯。

## 当前边界

- CRM、订单、工单和默认 LLM 仍是本地 Mock Adapter。
- 当前使用 `create_all` 创建新增表，生产环境上线前需补充 Alembic migration。
- 本阶段只输出训练候选集，不执行训练、数据标注平台同步或模型自动发布。
