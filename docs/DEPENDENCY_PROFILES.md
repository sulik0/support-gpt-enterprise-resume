# 依赖分层说明

项目将依赖拆分为多个 profile，避免本地 demo、CI、评估实验和压测都安装同一组较重依赖。

## Profile 列表

| 文件 | 用途 | 典型使用场景 |
|---|---|---|
| `requirements.txt` | 运行时入口 | FastAPI 后端、Docker 镜像、本地 demo |
| `requirements/base.txt` | 基础运行时依赖 | 被其他 profile 引用 |
| `requirements/test.txt` | 测试依赖 | CI 和本地 smoke tests |
| `requirements/eval.txt` | 可选评估依赖 | RAGAS / DeepEval 离线质量评估 |
| `requirements/load.txt` | 可选压测依赖 | Locust 压测 |

## 推荐本地环境

使用 Python 3.11：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements/test.txt
```

运行定向检查：

```bash
python -m compileall src tests
python -m pytest tests/test_agents.py tests/test_rag.py -q
```

仅在需要评估实验时安装可选评估依赖：

```bash
python -m pip install -r requirements/eval.txt
```

## 简历可讲表述

> 将运行时、测试、评估和压测依赖拆分为独立 profile，使核心服务可以在不安装可选评估和压测依赖的情况下完成安装与 CI 验证。

## 生产边界

这是可复现性改进，不是完整生产锁版本策略。生产级构建还应补充：

- 生成式 lock file。
- 依赖漏洞扫描。
- Docker 镜像扫描。
- 多 Python 版本 CI matrix。
- 云厂商或模型 provider 的可选 extras。

## 文档语言约定

本仓库后续新增和更新的项目文档统一使用中文。代码标识符、命令、配置项、API 路径和通用技术名词可以保留英文。
