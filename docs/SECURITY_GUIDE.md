# 安全与风控说明

本文说明 **SupportGPT Enterprise** 中的鉴权、RBAC、输入输出安全过滤和 Agent 风控逻辑。

---

## 鉴权与 RBAC

API 使用 **JWT Bearer Token** 进行保护，签名算法为 `HS256`。

### 角色权限控制

系统在 FastAPI route dependency 层限制不同角色权限：

- **客服坐席 (`agent`)**：查看工单、请求 AI 回复、审批 AI 生成的回复卡片。
- **经理 (`manager`)**：查看坐席指标、回滚知识库版本、处理高风险升级工单。
- **管理员 (`admin`)**：管理集合、系统 prompt、用户和支持人员账号。

```python
@app.get("/approvals/pending")
async def list_pending_approvals(current_user: User = Depends(require_agent)):
    ...
```

---

## AI Guardrails 与安全层

客户输入、Tool 返回和 RAG 文档在进入生成 Prompt 前均有明确的安全检查边界；生成内容在返回前经过 QA 和输出过滤。

### 1. PII 脱敏 (`pii_detection.py`)

- 使用正则识别 SSN、信用卡、手机号、邮箱等敏感信息。
- 在文本发送给 LLM provider 前替换为 `[CREDIT_CARD]`、`[EMAIL]` 等标签。

### 2. Prompt Injection 防护 (`prompt_injection.py`)

- 文本规范化层：使用 Unicode NFKC，清理零宽字符和多余空白，同时构造紧凑文本以识别分隔符混淆。
- 模式检测层：组合中英文直接特征、“操作 + 指令边界”、“提取 + 敏感对象”和角色提权启发式。
- 编码载荷层：受限解码 Base64 / URL-safe Base64，并对解码后内容重新扫描。
- 信任边界层：分别检查 `user_input`、`tool_result` 和 `rag_document`，防护直接与间接 Prompt Injection。
- 检测结果返回结构化 `risk_score`、`confidence`、`layers` 和不包含原文的 `signals`。
- 命中后直接阻断后续 Tool / RAG / Resolver / QA 链路，清空不可信上下文并转人工。

### 3. Jailbreak 检测 (`jailbreak_detection.py`)

- 阻断常见越权话术，例如 “DAN mode” 或 “sudo override”。

### 4. 输出泄露过滤 (`response_filter.py`)

- 在回复返回客户端前检查是否泄露系统 prompt、内部 Agent 节点或敏感实现细节。
- 命中风险时替换为安全兜底回复。

## 独立 Risk Engine

`src/risk/engine.py` 不依赖 LLM 自由判断，而是在 Analyzer、QA 和 Escalation 阶段使用同一套可测试规则综合风险。

风险信号包括：

- Prompt Injection / Jailbreak 安全威胁与检测分数。
- 工单优先级、负面情绪和退款、拒付、投诉等高风险业务意图。
- Analyzer `confidence_score`。
- QA 分数、幻觉标记和 Workflow 错误。

默认等级为 `low < 0.4`、`medium >= 0.4`、`high >= 0.7`、`critical >= 0.9`。`high` 与 `critical` 要求人工处理；安全威胁额外设置 `risk_block_automation=true`。阈值通过 `RISK_*` 环境变量配置，最终结果写入 `AgentState`、API 响应、结构化日志、OpenTelemetry Trace 和 Metrics。

---

## 简历表述边界

可以说系统实现了确定性多层 Prompt Injection 检测、间接注入隔离、Jailbreak、PII、输出泄露防护和独立 Risk Engine。不要说它已经达到完整企业安全合规标准；当前仍没有专用训练的模型型安全分类器、策略配置中心、持久化安全事件平台或生产安全团队评审。
