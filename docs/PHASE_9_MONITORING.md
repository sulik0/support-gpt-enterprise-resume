# 阶段 9：监控

## 目标

通过 `/metrics` 暴露 Prometheus 指标，跟踪请求量、延迟、Agent 执行耗时、token 使用量、成本估算、QA 结果和升级决策。

---

## 设计决策

- **Prometheus 指标**：使用 `prometheus_client` 挂载指标端点。
- **请求级监控**：记录 API 请求耗时和调用量。
- **Agent 级监控**：记录各 Agent 节点执行时长。
- **成本估算**：按 provider/model 统计 token 和 USD 成本。
- **OpenTelemetry Trace**：将 HTTP 请求、Agent workflow、各 Agent 节点、工具调用、RAG 查询和审批动作串联为 trace。
- **Grafana 面板**：保留 dashboard 模板，用于展示请求量、成本和风控命中。

---

## 代码参考

- 指标定义：`src/observability/metrics.py`
- Trace 初始化和工具函数：`src/observability/tracing.py`
- 请求耗时采集：`src/main.py`
- Agent workflow spans：`src/agents/graph.py`
- RAG 查询 spans：`src/agents/retriever.py`
- 工具调用 spans：`src/tools/registry.py`
- 审批流程 spans：`src/approval/workflows.py`
- Grafana 模板：`monitoring/grafana-dashboard.json`

---

## 验证步骤

```bash
curl http://localhost:8000/metrics
```

提交几条工单后，检查计数器和耗时指标是否增加。

本地 demo 默认使用 Console Exporter，可在后端日志中看到 span 输出。生产环境可替换为 OTLP exporter，并接入 Jaeger、Tempo 或云厂商 APM。
