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

所有文本 payload 都会经过 `src/guardrails/` 下的输入和输出过滤器。

### 1. PII 脱敏 (`pii_detection.py`)

- 使用正则识别 SSN、信用卡、手机号、邮箱等敏感信息。
- 在文本发送给 LLM provider 前替换为 `[CREDIT_CARD]`、`[EMAIL]` 等标签。

### 2. Prompt Injection 防护 (`prompt_injection.py`)

- 检测 “ignore previous instructions”、“override rules” 等指令劫持模式。
- 命中后直接阻断下游工具调用、RAG 检索和回复生成，并路由到人工升级。

### 3. Jailbreak 检测 (`jailbreak_detection.py`)

- 阻断常见越权话术，例如 “DAN mode” 或 “sudo override”。

### 4. 输出泄露过滤 (`response_filter.py`)

- 在回复返回客户端前检查是否泄露系统 prompt、内部 Agent 节点或敏感实现细节。
- 命中风险时替换为安全兜底回复。

---

## 简历表述边界

可以说系统实现了规则型 prompt injection、jailbreak、PII 和输出泄露防护。不要说它已经达到完整企业安全合规标准；生产系统还需要审计日志、策略配置中心、模型型安全分类器和安全团队评审。
