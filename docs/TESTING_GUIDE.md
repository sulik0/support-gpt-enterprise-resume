# Testing & Evaluation Guide

This document describes how to execute the testing suite, run locust load tests, and configure offline evaluations for **SupportGPT Enterprise**.

---

## 🧪 Unit & Integration Testing

We use **pytest** and **pytest-asyncio** to verify all system components.

### Dependency Profiles

Runtime dependencies are intentionally separated from optional test, evaluation, and load-test dependencies:

```bash
pip install -r requirements.txt
pip install -r requirements/test.txt
pip install -r requirements/eval.txt   # optional RAGAS/DeepEval
pip install -r requirements/load.txt   # optional Locust
```

Use Python 3.11 for the most reproducible local and CI behavior.

### Running Pytest
Execute the focused smoke suite below from the repository root:
```bash
python -m compileall src tests
pytest tests/test_agents.py tests/test_rag.py -q
```

The full suite can still be run with:

```bash
pytest --cov=src --cov-report=term-missing
```

If full pytest crashes in Python 3.13/macOS after installing optional evaluation packages, recreate the environment with Python 3.11 and install only `requirements/test.txt` first.

### Coverage targets
The CI/CD pipeline enforces **90%+ test coverage** on key business layers:
- `src/auth/`
- `src/agents/`
- `src/guardrails/`
- `src/rag/`
- `src/evaluation/`

### Test Database isolation
During test runs, `tests/conftest.py` overrides database settings, creating a fresh, in-memory SQLite database (`sqlite+aiosqlite:///:memory:`) for each test, ensuring tests do not mutate local development files.

---

## ⚡ Load Testing with Locust

We use **Locust** to test how the FastAPI backend handles multiple customer chats and agent validations under load.

1. Install Locust:
   ```bash
   pip install locust
   ```
2. Launch the load test script:
   ```bash
   locust -f tests/load_test.py
   ```
3. Open [http://localhost:8089](http://localhost:8089) to configure the target client request volumes and view real-time latency graphs.

---

## 📈 RAG Evaluation Framework

SupportGPT implements evaluation calculations:

1. **Ragas & DeepEval Adapters**:
   - If an `OPENAI_API_KEY` is present, the evaluators trigger real RAGAS and DeepEval calculations.
   - If no key is set, the system falls back to local estimators checking exact keyword recall, context precision, and word overlap hallucination rates.
2. **Generating Evaluation Reports**:
   - Run the script:
     ```bash
     python scripts/run_eval.py
     ```
   - This script runs test prompts against the RAG/Agent pipeline and outputs a summary grid.
   - Individual evaluation reports are saved in `evaluation/reports/` as JSON documents.
