# 阶段 8：部署

## 目标

将应用容器化，并提供本地完整依赖栈：

- FastAPI 后端。
- PostgreSQL 数据库。
- Redis 缓存。
- Prometheus 监控。
- ChromaDB 本地持久化目录。

---

## 设计决策

- **多阶段 Dockerfile**：构建阶段安装依赖，运行阶段复制依赖和代码。
- **Python 3.11**：Docker、CI 和本地推荐版本保持一致。
- **Docker Compose**：在本地网络中编排 backend、PostgreSQL、Redis 和 Prometheus。
- **可选 Kubernetes**：仓库中保留 k8s 模板，用于说明水平扩展方向。

---

## 代码参考

- Dockerfile：`deployment/Dockerfile`
- Compose 配置：`deployment/docker-compose.yml`
- Kubernetes 模板：`deployment/k8s/deployment.yml`

---

## 验证步骤

```bash
docker-compose -f deployment/docker-compose.yml up --build
docker-compose -f deployment/docker-compose.yml ps
```

启动后访问：

- API 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`
- Prometheus：`http://localhost:9090`
