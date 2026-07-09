# 阶段 6：测试

## 目标

验证 API 路由、角色权限、向量检索、Agent 工作流和安全 guardrails。当前项目以可复现的定向 smoke tests 为主，完整覆盖率目标作为后续生产化工作。

---

## 设计决策

测试通过 `tests/conftest.py` 配置临时 SQLite 数据库和 HTTPX client，尽量保证每次测试运行都使用干净的数据状态，避免测试之间互相污染。

---

## 代码参考

- 测试 fixture：`tests/conftest.py`
- API 测试：`tests/test_apis.py`
- Agent 测试：`tests/test_agents.py`
- RAG 测试：`tests/test_rag.py`
- Guardrail 测试：`tests/test_guardrails.py`

---

## 验证步骤

推荐使用 Python 3.11 环境：

```bash
python -m compileall src tests
pytest tests/test_agents.py tests/test_rag.py -q
```

完整测试命令：

```bash
pytest --cov=src --cov-report=term-missing
```

已知限制：当前本地 Python 3.13/macOS 环境在安装较多 native/evaluation 依赖后，pytest 可能出现 `139` 崩溃。CI 已切换到 Python 3.11。
