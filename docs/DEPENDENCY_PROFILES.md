# Dependency Profiles

This project separates dependency groups so local demos, CI checks, evaluation experiments, and load tests do not all install the same heavy package set.

## Profiles

| File | Purpose | Typical Use |
|---|---|---|
| `requirements.txt` | Runtime entry point | FastAPI backend, Docker image, local demo |
| `requirements/base.txt` | Runtime dependencies | Imported by all other profiles |
| `requirements/test.txt` | Focused backend tests | CI and local smoke tests |
| `requirements/eval.txt` | Optional RAGAS/DeepEval dependencies | Offline quality evaluation |
| `requirements/load.txt` | Optional Locust dependency | Load testing |

## Recommended Local Setup

Use Python 3.11:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements/test.txt
```

Run focused checks:

```bash
python -m compileall src tests
python -m pytest tests/test_agents.py tests/test_rag.py -q
```

Install optional evaluation tools only when needed:

```bash
python -m pip install -r requirements/eval.txt
```

## Resume-Safe Explanation

> I separated runtime, test, evaluation, and load-test dependency profiles so the core service can be installed and tested without pulling optional evaluation and load-testing packages into every environment.

## Production Boundary

This is a reproducibility improvement, not a full production lock strategy. A production-grade build should add:

- A generated lock file.
- Dependency vulnerability scanning.
- Docker image scanning.
- A CI matrix for supported Python versions.
- Separate optional extras for cloud-specific providers.
