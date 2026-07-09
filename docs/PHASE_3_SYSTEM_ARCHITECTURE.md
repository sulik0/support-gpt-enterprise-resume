# 阶段 3：系统架构

## 目标

实现一个容器化、可扩展、具备基础安全边界的客服 Agent 后端服务。架构需要区分 API 入口、Agent 状态流转、安全层、数据库、缓存和监控组件。

---

## 设计决策

核心技术选择：

- **FastAPI**：提供异步后端 API。
- **LangGraph**：编排多个专职 Agent 节点。
- **ChromaDB**：提供本地低延迟语义检索。
- **Redis**：作为可选短期会话记忆和缓存层。
- **PostgreSQL / SQLAlchemy**：持久化工单、审批、会话和知识库元数据。

---

## 代码参考

- 架构总览：`ARCHITECTURE.md`
- API 入口和中间件：`src/main.py`

---

## 验证步骤

1. 启动容器栈：`docker-compose -f deployment/docker-compose.yml up --build`
2. 访问 Swagger 文档：`http://localhost:8000/docs`
