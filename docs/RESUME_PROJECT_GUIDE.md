# 简历项目指南

## 推荐项目名称

基于 LangGraph 的企业级智能客服 Agent 与工单自动化平台

英文名称可在简历中作为括号补充：

Enterprise Customer Support Agent Platform with LangGraph, RAG, Tool Context, and HITL Approval

## 简历项目描述

面向企业售后客服场景，设计并实现一套智能客服 Agent 平台，支持用户意图识别、知识库 RAG 检索、CRM / 订单 / 历史工单上下文增强、客服回复生成、人工审批、工单升级和质量评估。系统基于 FastAPI 提供后端服务，使用 LangGraph 编排多 Agent 工作流，通过 Redis 管理短期会话记忆，使用 SQLAlchemy 持久化工单与审批记录，并结合 Prometheus 指标与 RAG 评估模块提升系统可观测性和回答可信度。

## 简历 Bullet

- 基于 `LangGraph` 设计客服 Agent 工作流，将工单分析、工具上下文增强、知识库检索、回复生成、质量校验和 SLA 升级拆分为可观测节点，提升客服流程可控性。
- 构建 `RAG` 知识库检索链路，支持文档切分、Embedding 向量化、ChromaDB 存储、知识库版本过滤、BM25 风格混合检索、轻量 rerank 和 citation 返回，降低无依据回答风险。
- 设计统一工具调用 registry，为 CRM、订单管理、历史工单和退款初筛工具增加 schema 校验、角色权限、超时控制和审计记录，并将结构化客户画像、订单状态和历史问题注入回复生成流程。
- 实现 `Redis` 短期会话记忆与 SQL 持久化会话历史，支持多轮客服对话上下文复用，并在 Redis 不可用时自动降级。
- 基于 `FastAPI + SQLAlchemy` 封装聊天、工单、用户鉴权、人工审批和评估接口，持久化用户、Ticket、SessionMemory 和 ResponseApproval 记录。
- 引入 PII 检测、Prompt Injection 检测、Jailbreak 检测、输出过滤、QA 评分和人工审批机制，对高风险或低置信度回复触发人工确认。
- 拆分 runtime、test、eval、load 依赖 profile，并增加 Python 3.11 GitHub Actions smoke workflow，提高项目可复现性。

## 已实现能力

- FastAPI 后端 API。
- LangGraph 工作流。
- Agent graph 内的 tooling node。
- 统一工具调用 registry、工具 schema、角色权限校验和工具调用审计。
- ChromaDB 向量存储。
- BM25 风格混合检索和轻量 rerank。
- SQLAlchemy 工单、会话和审批模型。
- 可选 Redis memory adapter。
- Mock LLM provider，以及 OpenAI / Azure provider 适配接口。
- Human-in-the-Loop 审批流程。
- Prometheus 指标。
- Docker Compose 本地栈。
- Python 3.11 CI smoke workflow。

## Mock 内容

这些内容可以用于简历项目，但面试时需要说明边界：

- CRM 客户画像工具使用本地 mock 数据。
- 订单管理工具使用本地 mock 订单。
- 历史工单工具使用本地 mock 工单记录。
- 默认 LLM 是确定性的 mock provider。
- 评估模块在无 API key 时使用简化本地指标。

推荐面试说法：

> 这个项目用 mock adapter 模拟企业 CRM、订单和工单系统，因为简历项目无法访问真实企业私有 API。关键工程点是 Agent 工作流按 adapter 设计，后续可以把这些 mock class 替换成真实 REST 或 RPC client。

## 不要过度包装

避免说：

- 已经部署到真实生产客服中心。
- 已经接入真实 CRM 或订单系统。
- 支持任意自主工具选择和任意 function calling。
- 全量 pytest 在所有环境都稳定。
- Redis 是所有记忆能力的强依赖。

建议说：

- 这是 production-inspired 的简历项目。
- 它具备生产风格架构。
- CRM / 订单 / 工单工具是 mock adapter。
- Redis 是可选短期记忆，SQL 是持久化兜底。
- 下一步生产化是替换真实业务系统 client，并补充权限、审计和更完整 CI。

## 可量化指标设计

以下指标适合作为设计目标或本地实验目标，未真实测量时不要写成线上结果：

- FAQ Top-5 recall 目标：85%+
- Answer relevance 目标：0.80+
- Faithfulness 目标：0.85+
- 高风险请求人工审批召回目标：90%+
- 外部 LLM 平均响应延迟目标：2-5 秒
- Mock 模式工作流本地延迟目标：100 ms 以内
- 常见问题自动草稿覆盖率目标：60%-75%

## 面试讲解稿

这个项目是一个企业智能客服 Agent 平台。用户消息进入 FastAPI `/chat` 接口后，系统会创建或更新工单，并加载会话历史。Redis 用作可选短期工作记忆，SQL 保存持久化会话记录。

请求随后进入 LangGraph 工作流。Analyzer 节点先做 guardrail 检测，并识别情绪、优先级、部门和意图。如果命中安全风险，请求会直接进入 escalation 节点。正常请求会进入 tooling 节点，补充 CRM、订单和历史工单上下文。Retriever 节点根据部门和知识库版本查询 ChromaDB，并使用 BM25 风格关键词分数做轻量 rerank。Resolver 节点结合 RAG 上下文和结构化工具上下文生成客服回复。QA 节点检查回复质量和幻觉风险，Escalation 节点对高风险或低置信度回复触发人工审批。

本地开发中，CRM、订单、工单工具和默认 LLM 都是 mock，因此项目可以脱离企业私有 API 运行。生产环境可以将这些 adapter 替换成真实 CRM、OMS、物流、退款或工单服务 client。

## 高频追问

### 为什么用 LangGraph，而不是普通 chain？

客服流程不是一次 prompt 就能完成。它需要安全检测、分类、工具上下文、RAG 检索、回复生成、QA 校验和升级决策。LangGraph 可以把这些阶段拆成显式节点，便于观测、测试和插入条件路由。

### 工具调用是真的业务系统吗？

当前工具是 mock adapter，用来模拟 CRM、订单和工单系统。架构上这些工具被封装在独立 class 后面，可以不改 graph contract 就替换成真实服务 client。

### 工具权限怎么控制？

工具统一注册到 `ToolRegistry`，每个工具都有 `input_schema`、`output_schema`、`min_role` 和超时时间。调用前会先做角色权限校验和参数校验，例如读类工具允许 `agent` 调用，退款初筛工具要求 `manager` 及以上角色。每次调用都会生成 `tool_calls` 审计记录，API 可以返回工具名、状态、耗时和是否 mock。

### 记忆系统怎么做？

Redis 按 `session_id` 保存最近对话 turn，作为短期工作记忆。SQL `SessionMemory` 保存持久化历史，Redis 不可用时系统会降级到 SQL。

### 如何降低幻觉？

系统结合 RAG citation、QA 分数、输出过滤和升级规则。如果检索上下文为空、QA 分数低或命中高风险规则，回复会进入人工审批。

### 下一步会怎么改？

我会接入真实业务系统 adapter，引入生产搜索后端或 cross-encoder reranker，补充 lock file 和 Python 版本 CI matrix，并增加 OpenTelemetry trace，把 LLM 调用、工具调用、检索和审批决策串起来。

## 后续加分改造

更详细的后续改造建议见 `docs/RESUME_VALUE_ENHANCEMENT_ROADMAP.md`。建议优先做 RAG 评估集、工具调用协议、工单状态机、OpenTelemetry Trace 和多租户知识库隔离，这些方向最容易体现“不是普通 Chatbot demo”，也最适合在面试中展开。
