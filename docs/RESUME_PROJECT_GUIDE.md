# Resume Project Guide

## Recommended Project Name

基于 LangGraph 的企业级智能客服 Agent 与工单自动化平台

English version:

Enterprise Customer Support Agent Platform with LangGraph, RAG, Tool Context, and HITL Approval

## Resume Project Description

面向企业售后客服场景，设计并实现一套智能客服 Agent 平台，支持用户意图识别、知识库 RAG 检索、CRM/订单/历史工单上下文增强、客服回复生成、人工审批、工单升级和质量评估。系统基于 FastAPI 提供后端服务，使用 LangGraph 编排多 Agent 工作流，通过 Redis 管理短期会话记忆、PostgreSQL/SQLAlchemy 持久化工单与审批记录，并结合 Prometheus 指标与 RAG 评估模块提升系统可观测性和回答可信度。

## Resume Bullets

- 基于 `LangGraph` 设计客服 Agent 工作流，将工单分析、工具上下文增强、知识库检索、回复生成、质量校验和 SLA 升级拆分为可观测节点，提升客服流程的可控性。
- 构建 `RAG` 知识库检索链路，支持文档切分、Embedding 向量化、ChromaDB 存储、知识库版本过滤和 citation 返回，降低无依据回答风险。
- 设计 CRM、订单管理、历史工单等工具上下文节点，将结构化客户画像、订单状态和历史问题注入回复生成流程，模拟真实客服业务系统集成。
- 实现 `Redis` 短期会话记忆与 SQL 持久化会话历史，支持多轮客服对话上下文复用，并在 Redis 不可用时自动降级。
- 基于 `FastAPI + SQLAlchemy` 封装聊天、工单、用户鉴权、人工审批和评估接口，持久化用户、Ticket、SessionMemory 和 ResponseApproval 记录。
- 引入 PII 检测、Prompt Injection 检测、Jailbreak 检测、输出过滤、QA 评分和人工审批机制，对高风险或低置信度回复触发人工确认。

## What Is Implemented

- FastAPI backend APIs.
- LangGraph workflow.
- Tooling node inside the Agent graph.
- ChromaDB vector store manager.
- SQLAlchemy ticket/session/approval models.
- Optional Redis memory adapter.
- Mock LLM provider plus OpenAI/Azure provider adapters.
- Human-in-the-loop approval workflow.
- Prometheus metrics hooks.
- Docker Compose with backend, PostgreSQL, Redis, and Prometheus.

## What Is Mocked

These are acceptable for a resume project if explained clearly:

- CRM customer profile tool uses local mock data.
- Order management tool uses local mock orders.
- Ticket history tool uses local mock ticket records.
- Default LLM is a deterministic mock provider for local demos.
- Evaluation can run in simplified deterministic mode unless real API keys are configured.

Suggested interview wording:

> I used mock adapters to simulate enterprise CRM, order management, and ticketing systems because the project is designed as a resume/demo system. The important engineering point is that the Agent workflow is adapter-driven, so these mock classes can be replaced by real REST or RPC clients.

## What Not To Overclaim

Avoid saying:

- This has been deployed to a real production customer support center.
- It connects to real CRM or order systems.
- It performs autonomous tool selection with arbitrary function calling.
- Full pytest is stable in every environment.
- Redis is mandatory for all memory behavior.

Prefer saying:

- It is production-inspired.
- It has a production-style architecture.
- CRM/order/ticketing tools are mocked adapters.
- Redis is optional short-term memory with SQL fallback.
- The next production step would be replacing mock adapters with real service clients.

## Suggested Metrics

Use these as design/target metrics unless measured:

- FAQ Top-5 recall target: 85%+
- Answer relevance target: 0.80+
- Faithfulness target: 0.85+
- Manual approval recall for high-risk requests: 90%+
- Average response latency target: 2-5 seconds with external LLMs
- Mock-mode workflow latency: under 100 ms locally
- Common issue auto-draft coverage target: 60%-75%

## Interview Explanation

This project is an enterprise customer support Agent platform. A customer message enters the FastAPI `/chat` endpoint, where the system creates or updates a ticket and loads conversation history. Redis is used as short-term working memory when configured, while SQL keeps durable conversation records.

The request then enters a LangGraph workflow. The analyzer node performs guardrail checks and classifies the ticket by sentiment, priority, department, and intent. The tooling node enriches the state with CRM, order, and historical ticket context. The retriever node queries the knowledge base through ChromaDB using the detected department and knowledge-base version. The resolver node combines RAG context and structured tool context to draft a support response. The QA node checks response quality and hallucination risk, and the escalation node triggers human approval when the answer is high-risk or low-confidence.

For local development, CRM/order/ticket tools and the LLM are mocked so the system can run without private enterprise APIs. In production, those adapters would be replaced with real CRM, OMS, logistics, refund, or ticketing service clients.

## High-Frequency Questions

### Why LangGraph instead of a normal chain?

Customer support is not just one prompt. It needs guardrails, classification, structured tool context, RAG retrieval, response generation, QA validation, and escalation. LangGraph makes each stage explicit and observable.

### Are the tools real?

The current tools are mock adapters. They simulate CRM, order, and ticketing systems. The architecture is designed so those classes can be replaced with real service adapters without changing the graph contract.

### How is memory implemented?

Redis stores recent conversation turns by session ID as short-term working memory. SQL `SessionMemory` remains the durable fallback and audit record.

### How do you prevent hallucination?

The system combines RAG citations, QA scoring, response filtering, and escalation rules. If retrieved context is missing or QA score is low, the response can be routed to human approval.

### What would you improve next?

I would add real service adapters, BM25 + vector hybrid retrieval, reranking, dependency locking, Python 3.11/3.12 CI, and OpenTelemetry traces that connect LLM calls, tool calls, retrieval, and approval decisions.
