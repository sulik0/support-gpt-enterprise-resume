# 阶段 9：监控

## 目标

通过 OpenTelemetry Metrics SDK 统一采集请求量、延迟、Agent 执行耗时、token 使用量、成本估算、QA 结果和升级决策，并经 OTLP 上报 OpenTelemetry Collector。

---

## 设计决策

- **统一指标采集**：应用使用 OpenTelemetry Counter、Histogram 和 UpDownCounter，不直接暴露 Prometheus 端点。
- **指标导出**：OpenTelemetry Collector 接收 OTLP Metrics，并通过 Prometheus exporter 供 Prometheus 抓取。
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
curl http://localhost:8889/metrics
```

提交几条工单后，在 Collector 的 Prometheus exporter 或 Prometheus 中检查指标是否增加。Trace 与 Metrics exporter 失败均采用 fail-open，不影响业务主流程。
