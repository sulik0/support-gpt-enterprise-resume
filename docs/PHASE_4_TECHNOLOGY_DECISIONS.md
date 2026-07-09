# 阶段 4：技术选型

## 目标

根据客服 Agent 场景选择技术框架：

- 支持可插拔 LLM provider，便于切换 mock、OpenAI 和 Azure。
- 支持本地临时向量库，方便无密钥运行单元测试。
- 支持异步数据库访问，兼容本地 SQLite 和生产 PostgreSQL。

---

## 设计决策

- **可插拔 LLM Provider**：通过 `BaseLLMProvider` 定义统一接口，测试时使用 mock provider 降低成本。
- **SQLite + asyncpg**：测试和本地轻量场景使用 `aiosqlite`，生产配置使用 `asyncpg` 连接 PostgreSQL。
- **ChromaDB**：本地 demo 使用持久化目录或 ephemeral client，便于快速验证 RAG 流程。

---

## 代码参考

- LLM provider：`src/llm/provider.py`
- 数据库连接：`src/database.py`

---

## 验证步骤

1. 运行 Agent/RAG 定向测试，确认 mock LLM 能拦截模型调用。
