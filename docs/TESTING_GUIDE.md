# 测试与评估指南

本文说明如何运行测试、压测和离线评估。

---

## 单元测试与集成测试

项目使用 **pytest** 和 **pytest-asyncio** 验证核心模块。

### 依赖分层

运行时依赖、测试依赖、评估依赖和压测依赖已经拆分：

```bash
pip install -r requirements.txt
pip install -r requirements/test.txt
pip install -r requirements/eval.txt   # 可选：RAGAS / DeepEval
pip install -r requirements/load.txt   # 可选：Locust
```

推荐使用 Python 3.11，以获得和 CI 一致的行为。

### 运行 Pytest

推荐先运行定向 smoke suite：

```bash
python -m compileall src tests
pytest tests/test_agents.py tests/test_rag.py -q
```

完整测试命令：

```bash
pytest --cov=src --cov-report=term-missing
```

如果在 Python 3.13/macOS 环境中安装了可选评估依赖后 full pytest 出现 `139` 崩溃，建议重新创建 Python 3.11 虚拟环境，并优先只安装 `requirements/test.txt`。

### 覆盖率目标

生产化目标是核心业务层覆盖率达到 90%+，重点包括：

- `src/auth/`
- `src/agents/`
- `src/guardrails/`
- `src/rag/`
- `src/evaluation/`

当前简历项目阶段更关注可复现 smoke tests 和关键链路验证。

### 测试数据库隔离

`tests/conftest.py` 会覆盖数据库配置，使用内存 SQLite 数据库 `sqlite+aiosqlite:///:memory:`，避免测试污染本地开发数据。

---

## Locust 压测

项目提供 Locust 脚本，用于模拟多个客户聊天和 Agent 校验请求。

1. 安装压测依赖：

```bash
pip install -r requirements/load.txt
```

2. 启动压测：

```bash
locust -f tests/load_test.py
```

3. 打开 `http://localhost:8089` 配置并发量和请求速率。

---

## RAG 评估

评估模块支持两种模式：

1. **RAGAS / DeepEval 适配器**

如果配置了 `OPENAI_API_KEY`，评估器可以调用真实框架计算指标。

2. **本地简化指标**

如果没有 API key，系统会使用关键词召回、上下文覆盖和文本重合度等本地估算指标。

运行评估：

```bash
python scripts/run_eval.py
```

评估报告会保存到 `evaluation/reports/`。
