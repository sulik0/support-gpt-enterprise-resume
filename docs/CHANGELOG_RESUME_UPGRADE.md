# 简历项目改造变更日志

本文记录在上游项目基础上，为“企业级智能客服 Agent 简历项目”所做的改造。后续 `docs/` 下的项目文档统一使用中文；代码标识符、命令、配置项、API 路径和通用技术名词可保留英文。

## Commit 1：`docs: add resume upgrade plan`

提交：`9f31e13`

### 修改文件

- `docs/RESUME_UPGRADE_PLAN.md`

### 修改内容

- 增加简历项目改造计划。
- 区分已实现能力、mock 集成和生产化缺口。
- 记录 GitHub 上传流程和 remote 状态。

### 简历价值

该文档避免过度包装项目，并提供清晰面试叙事：

- 项目具备 FastAPI / LangGraph / RAG / HITL 主干。
- CRM、订单和工单工具是本地 mock adapter。
- 生产化缺口已明确列出。

## Commit 2：`feat: add tool context node to agent workflow`

提交：`824da7b`

### 修改文件

- `src/agents/tooling.py`
- `src/agents/graph.py`
- `src/agents/resolver.py`

### 修改内容

- 新增 `ToolingAgent`，作为 LangGraph 中独立工具上下文节点。
- 工具节点调用 CRM、订单和历史工单 mock adapter。
- 在 Agent state 中新增 `tool_context`。
- 将工作流升级为：

```text
analyzer -> tooling -> retriever -> resolver -> qa -> escalation
```

- Resolver 生成回复时同时接收 RAG 知识库上下文和结构化工具上下文。

### 简历价值

可以真实表述为：

> 设计工具增强型客服 Agent 工作流，在回复生成前为工单注入 CRM、订单和历史工单上下文。

### Mock 边界

工具是本地 mock adapter，不是真实企业 API。作为简历项目可以接受，但面试中需要明确说明。

## Commit 3：`feat: add optional Redis conversation memory`

提交：`57d948d`

### 修改文件

- `src/memory/__init__.py`
- `src/memory/redis_memory.py`
- `src/main.py`

### 修改内容

- 新增 `RedisConversationMemory`，作为可选 Redis 短期记忆层。
- 按 `session_id` 加载和保存最近对话 turn。
- Redis 不配置或不可用时，系统继续使用 SQL `SessionMemory`。
- `/chat` 流程会优先读取 Redis 最近消息，并同时持久化 SQL 会话历史。

### 简历价值

可以真实表述为：

> 实现 Redis 短期会话记忆，并使用 SQL 保存持久化会话历史。

### Mock 边界

Redis 能力是真实实现，但属于可选能力。本地 demo 不启动 Redis 时系统也能运行。

### 验证记录

通过：

```bash
python -m compileall src
```

```bash
.venv/bin/python -c 'import src.main; from src.memory.redis_memory import redis_memory; print("memory import ok", redis_memory.max_turns)'
```

```bash
.venv/bin/python -c 'from src.agents.graph import run_agent_workflow; import asyncio; out=asyncio.run(run_agent_workflow({"ticket_id":1,"customer_id":"cust_101","subject":"refund","description":"I want refund for charge","kb_version":"v1"})); print(out["department"], bool(out.get("tool_context")), out.get("tool_context", {}).get("mocked"), out["approval_required"])'
```

输出：

```text
billing True True True
```

已知限制：

- 当前本地 Python 3.13/macOS 环境在安装较多 evaluation/native 依赖后，full pytest 可能以 `139` 崩溃。建议使用 Python 3.11 或 3.12，并拆分可选依赖。

## Commit 4：`feat: add security short-circuit routing`

提交：`923b073`

### 修改文件

- `src/agents/graph.py`

### 修改内容

- 新增 analyzer 后的条件路由 `route_after_analyzer`。
- 命中 prompt injection 或 jailbreak 的请求会直接进入 `escalation`。
- 安全风险请求会跳过 tooling、retriever、resolver 和 QA。

工作流变为：

```text
analyzer
  ├── security threat -> escalation -> END
  └── normal request  -> tooling -> retriever -> resolver -> qa -> escalation -> END
```

### 简历价值

可以真实表述为：

> 在 LangGraph 工作流中增加条件路由，使 prompt injection 和 jailbreak 请求在调用工具或检索前被提前阻断并升级人工处理。

### Mock 边界

当前 guardrail 是规则型实现。生产系统应结合模型分类器、策略配置、审计日志和安全评审。

## Commit 5：`feat: expose tool context in API responses`

提交：`51c6523`

### 修改文件

- `src/models/schemas.py`
- `src/main.py`

### 修改内容

- `ChatResponse` 增加 `tool_context`。
- `SuggestResponseResponse` 增加 `tool_context`。
- `/chat` 和 `/suggest-response` 会返回 Agent 收集到的结构化工具上下文。

示例：

```json
{
  "customer_profile": {
    "customer_id": "cust_101",
    "tier": "VIP",
    "open_tickets_count": 2
  },
  "recent_orders": [],
  "past_tickets": [],
  "mocked": true
}
```

### 简历价值

API 层可以直接展示工具增强效果，便于 demo、调试和面试讲解。

### Mock 边界

`tool_context.mocked` 明确标识当前工具数据来自本地 mock adapter。

## Commit 6：`docs: document mock boundaries for resume claims`

提交：`20565c5`

### 修改文件

- `docs/MOCK_BOUNDARIES.md`
- `README.md`

### 修改内容

- 增加 mock 边界说明文档。
- 给出安全简历表述和应避免的过度表述。
- 增加 mock 到生产化的升级清单。
- 在 README 中增加文档入口。

### 简历价值

帮助面试中明确区分真实工程实现和模拟业务集成，体现工程判断。

## Commit 7：`feat: add hybrid retrieval reranking`

提交：`de876b9`

### 修改文件

- `src/rag/vector_store.py`
- `tests/test_rag.py`
- `docs/RAG_ARCHITECTURE.md`
- `docs/RESUME_PROJECT_GUIDE.md`
- `docs/MOCK_BOUNDARIES.md`

### 修改内容

- 将 `VectorStoreManager.query_kb` 从纯向量检索升级为混合检索。
- ChromaDB 向量检索会多取候选。
- 增加进程内 BM25 风格关键词 scorer。
- 增加轻量 reranker，融合向量相似度、归一化关键词分和精确词重合。
- 增加定向测试，验证关键词密集型客服查询可以排到正确 chunk。
- 更新 RAG 和简历文档，说明实现边界。

### 简历价值

可以真实表述为：

> 构建混合 RAG 检索层，结合向量相似度、BM25 风格关键词分数和轻量 rerank，提升退款窗口、产品名、保修短语等精确词的召回质量。

### Mock 边界

关键词 scorer 是进程内轻量实现，不是生产分布式搜索后端。生产系统可替换为 OpenSearch、Elasticsearch、PostgreSQL full-text search 或专用 reranker 服务。

### 验证记录

通过：

```bash
python -m compileall src tests
```

```bash
.venv/bin/python -c 'from src.rag.vector_store import vector_store; print("vector store import ok", vector_store.collection_name)'
```

```bash
.venv/bin/python -c 'from src.agents.graph import run_agent_workflow; import asyncio; out=asyncio.run(run_agent_workflow({"ticket_id":7,"customer_id":"cust_101","subject":"warranty headphones","description":"My damaged headphones need warranty support and serial number validation","kb_version":"v1"})); print({"department": out.get("department"), "citations": len(out.get("context_citations", [])), "tool_context": bool(out.get("tool_context")), "approval_required": out.get("approval_required")})'
```

输出：

```text
{'department': 'general', 'citations': 2, 'tool_context': True, 'approval_required': False}
```

已知限制：

- `.venv/bin/python -m pytest tests/test_rag.py -q` 在当前 Python 3.13/macOS 环境仍以 `139` 退出，和前面记录的 native 依赖问题一致。

## Commit 8：`chore: stabilize python dependency profiles`

提交：`c977f56`

### 修改文件

- `.python-version`
- `.github/workflows/ci.yml`
- `requirements.txt`
- `requirements/base.txt`
- `requirements/test.txt`
- `requirements/eval.txt`
- `requirements/load.txt`
- `docs/DEPENDENCY_PROFILES.md`
- `deployment/Dockerfile`
- `pyproject.toml`
- `README.md`
- `docs/TESTING_GUIDE.md`

### 修改内容

- 将本地开发、Docker 和 CI 推荐版本统一为 Python 3.11。
- 拆分 runtime、test、eval 和 load 依赖 profile。
- 根目录 `requirements.txt` 保留为运行时安装入口。
- 将 RAGAS / DeepEval 和 Locust 从默认安装路径移出。
- 增加 GitHub Actions workflow，执行编译和定向 Agent/RAG 测试。
- 更新 README 和测试文档。
- 增加依赖分层说明文档。

### 简历价值

可以真实表述为：

> 通过拆分运行时、测试、评估和压测依赖，并增加 Python 3.11 CI smoke workflow，提升项目可复现性和工程质量。

### 生产边界

这是依赖治理和可复现性改进，不是完整生产锁版本策略。更严格的生产系统还需要 lock file、漏洞扫描、镜像扫描和完整 CI matrix。

### 验证记录

通过：

```bash
python -m compileall src tests
```

```bash
.venv/bin/python -c 'import yaml; yaml.safe_load(open(".github/workflows/ci.yml")); print("ci yaml ok")'
```

```bash
.venv/bin/python -c 'import src.main; print("main import ok")'
```

检查项：

- `requirements/test.txt` 可以从 `requirements/` 目录解析 `-r base.txt`。
- Dockerfile 会在安装前复制 `requirements.txt` 和 `requirements/` 目录。

已知限制：

- 本地 `pip install --dry-run -r requirements/test.txt` 因当前虚拟环境是 Python 3.13，开始解析 native package metadata 后被中止；提交的 CI 使用 Python 3.11。

## Commit 9：`docs: translate docs to chinese`

### 修改文件

- `docs/*.md`

### 修改内容

- 将 `docs/` 下项目文档统一改为中文。
- 保留代码标识符、命令、API 路径、配置项和通用技术名词。
- 移除旧文档中的本机 `file://` 参考路径。
- 在依赖分层说明中增加后续文档语言约定。

### 简历价值

中文文档更适合直接用于简历准备、项目复盘和中文面试讲解，同时保留必要英文技术词，便于和代码实现对应。

## Commit 10：`docs: add resume enhancement roadmap`

### 修改文件

- `docs/RESUME_VALUE_ENHANCEMENT_ROADMAP.md`
- `docs/RESUME_PROJECT_GUIDE.md`
- `docs/RESUME_UPGRADE_PLAN.md`
- `docs/CHANGELOG_RESUME_UPGRADE.md`

### 修改内容

- 增加后续简历加分改造路线图。
- 按优先级列出 RAG 评估集、工具调用协议、工单状态机、OpenTelemetry Trace、多租户知识库隔离、生产检索后端、客服工作台和 Prompt 灰度等方向。
- 对每个方向补充简历可写法、可 mock 边界和面试追问回答。
- 在简历指南和改造计划中增加文档入口。

### 简历价值

该文档用于指导后续继续增强项目，避免盲目堆技术名词。优先选择能体现业务闭环、质量评估、安全工具调用和生产排障能力的方向。

## Commit 11：`feat: add tool registry permissions and audit`

### 修改文件

- `src/tools/registry.py`
- `src/agents/tooling.py`
- `src/agents/graph.py`
- `src/models/schemas.py`
- `src/main.py`
- `tests/test_agents.py`
- `tests/test_tool_registry.py`
- `docs/AGENT_ARCHITECTURE.md`
- `docs/RESUME_PROJECT_GUIDE.md`
- `docs/MOCK_BOUNDARIES.md`
- `docs/CHANGELOG_RESUME_UPGRADE.md`

### 修改内容

- 新增 `ToolRegistry`，统一管理工具定义、参数 schema、输出 schema、最低角色、超时和 mock 标记。
- 将 CRM、订单、历史工单工具注册为 schema 校验后的读类工具。
- 新增 `orders.check_refund_eligibility` manager 级 mock 工具，用于展示高风险业务工具的权限控制。
- `ToolingAgent` 改为只通过 registry 调用工具，不再直接调用具体工具 class。
- 每次工具调用都会生成 `tool_calls` 审计记录，包含工具名、角色、工单 ID、是否允许、状态、耗时、mock 标记和错误信息。
- `/chat` 和 `/suggest-response` 响应增加 `tool_calls` 字段，便于前端展示和面试 demo。

### 简历价值

可以真实表述为：

> 设计统一工具调用协议，为 CRM、订单、历史工单和退款初筛工具增加 Pydantic schema 校验、角色权限、超时控制和调用审计，使 Agent 工具调用具备可治理能力。

### Mock 边界

当前业务工具仍是本地 mock adapter，没有接入真实 CRM / OMS / 财务退款系统。权限校验、schema 校验、超时控制和审计记录是真实工程实现；生产环境需要将工具 handler 替换为真实 API client，并将审计记录持久化。

### 验证记录

通过：

```bash
python -m compileall src tests
```

```bash
.venv/bin/python -c 'import src.main; print("main import ok")'
```

```bash
.venv/bin/python -c 'import asyncio
from src.tools.registry import tool_registry
async def main():
    denied = await tool_registry.call_tool("orders.check_refund_eligibility", {"customer_id":"cust_101", "order_id":"ORD-7001"}, role="agent", ticket_id=1)
    allowed = await tool_registry.call_tool("orders.check_refund_eligibility", {"customer_id":"cust_101", "order_id":"ORD-7001"}, role="manager", ticket_id=1)
    print({"agent_status": denied["status"], "manager_status": allowed["status"], "eligible": allowed["result"]["eligible"]})
asyncio.run(main())'
```

输出：

```text
{'agent_status': 'permission_denied', 'manager_status': 'success', 'eligible': True}
```

```bash
.venv/bin/python -c 'from src.agents.graph import run_agent_workflow; import asyncio; out=asyncio.run(run_agent_workflow({"ticket_id":11,"customer_id":"cust_101","subject":"Billing refund request","description":"Can I get a refund for my payment done 5 days ago?","kb_version":"v1"})); print({"tool_calls": len(out.get("tool_calls", [])), "statuses": [c["status"] for c in out.get("tool_calls", [])], "permission_checked": out.get("tool_context", {}).get("tool_policy", {}).get("permission_checked")})'
```

输出：

```text
{'tool_calls': 3, 'statuses': ['success', 'success', 'success'], 'permission_checked': True}
```

已知限制：

- `.venv/bin/python -m pytest tests/test_tool_registry.py -q` 在当前 Python 3.13/macOS 环境仍以 `139` 退出，和此前记录的 pytest/native 依赖问题一致。CI 推荐 Python 3.11。

## Commit 12：`feat: add ticket lifecycle state machine`

### 修改文件

- `src/tickets/__init__.py`
- `src/tickets/state_machine.py`
- `src/approval/workflows.py`
- `src/main.py`
- `tests/test_ticket_state_machine.py`
- `docs/AGENT_ARCHITECTURE.md`
- `docs/RESUME_PROJECT_GUIDE.md`
- `docs/RESUME_VALUE_ENHANCEMENT_ROADMAP.md`
- `docs/CHANGELOG_RESUME_UPGRADE.md`

### 修改内容

- 新增 `TicketStateMachine`，统一管理工单合法状态流转。
- 定义 `open`、`in_progress`、`pending_approval`、`resolved`、`closed` 五个核心状态。
- 创建人工审批时，工单从 `open` 或 `in_progress` 进入 `pending_approval`。
- 审批通过或修改时，工单进入 `resolved`。
- 审批拒绝时，工单回到 `in_progress`。
- 新增 `/tickets/{ticket_id}/close` 接口，仅允许合法状态流转到 `closed`。
- 非法流转返回 `409 Conflict`，避免业务代码直接随意修改 `Ticket.status`。

### 简历价值

可以真实表述为：

> 设计工单闭环状态机，将 AI 草稿生成、人工审批、拒绝重处理、解决和关闭归档串联起来，并通过合法流转校验避免工单状态被随意修改。

### 生产边界

当前状态机复用 `Ticket.status` 字段，没有新增状态流转历史表。生产环境建议增加 `ticket_status_events` 审计表，记录操作者、动作、来源状态、目标状态、原因和时间。

### 验证记录

通过：

```bash
python -m compileall src tests
```

```bash
.venv/bin/python -c 'from src.models.db_models import Ticket; from src.tickets.state_machine import TicketAction, TicketStatus, ticket_state_machine; t=Ticket(customer_id="c", subject="s", description="d", status=TicketStatus.OPEN); print(ticket_state_machine.transition(t, TicketAction.REQUEST_APPROVAL)); print(ticket_state_machine.transition(t, TicketAction.APPROVE_RESPONSE)); print(ticket_state_machine.transition(t, TicketAction.CLOSE)); print(t.status)'
```

输出：

```text
Transition(source='open', target='pending_approval', action='request_approval')
Transition(source='pending_approval', target='resolved', action='approve_response')
Transition(source='resolved', target='closed', action='close')
closed
```

非法流转验证：

```bash
.venv/bin/python -c 'from fastapi import HTTPException; from src.models.db_models import Ticket; from src.tickets.state_machine import TicketAction, TicketStatus, ticket_state_machine; t=Ticket(customer_id="c", subject="s", description="d", status=TicketStatus.OPEN);
try:
    ticket_state_machine.transition(t, TicketAction.CLOSE)
except HTTPException as exc:
    print(exc.status_code, exc.detail["current_status"], exc.detail["requested_action"])
print(t.status)'
```

输出：

```text
409 open close
open
```
