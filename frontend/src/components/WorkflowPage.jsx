import React, { useState } from 'react';
import { ArrowDown, ArrowLeft, ArrowRight, CheckCircle2, Database, GitBranch, Layers, RotateCcw, ShieldCheck } from 'lucide-react';
import './workflow.css';

// 演示配置对应当前 graph.py；不执行 Agent，也不读取真实客户数据。
const NODES = {
  input: { name: '接收用户问题', code: 'HTTP · Ticket · Memory', summary: '校验请求、保存工单，并加载当前会话的历史信息。', input: '用户问题、会话身份、知识库版本', output: 'ticket_id、request_id、客户标识、会话上下文', design: '先确认请求归属和大小限制，再进入 Agent。业务记录与会话消息持久化；Memory 只提供上下文，不代替实时业务查询。', tags: ['FastAPI', '限流与身份校验', 'Memory V1'] },
  analyzer: { name: '理解问题与检查输入', code: 'analyzer', summary: '检查安全风险，识别意图、优先级、部门和情绪。', input: '主题、问题描述、有界 Memory 上下文', output: 'intent、department、priority、confidence、安全标记', design: '规则先产生分类候选；启用 Jev 时由 DecisionProvider 复核，故障或低置信度时按当前策略回退规则或 LLM。安全检查命中后直接转升级判断，不继续查询工具或生成回复。', tags: ['规则 / Jev / LLM', 'Prompt Guardrails', '8 个统一 Intent'] },
  skill_selector: { name: '选择可用能力', code: 'skill_selector', summary: '根据 Intent 固定选择 Skill，明确可用工具和知识范围。', input: '统一 Intent、客户标识、操作角色', output: 'Skill 名称与版本、工具允许/禁止列表、知识类别、缺失槽位', design: '使用确定性匹配，不让模型自行授权工具。当前 6 个 Skill 的配置版本为 v1.1；选择结果进入 State、Checkpoint、运行记录和 Trace。', tags: ['Skill Framework', '确定性路由', '版本快照'] },
  context_enrichment: { name: '并行补充业务与知识', code: 'context_enrichment', summary: '同时执行 Tooling 与 Retriever，合并结果并再次检查安全。', input: 'Skill 边界、Intent、客户标识、问题、kb_version', output: 'tool_context、tool_calls、context_citations、上下文安全结果', design: 'Tooling 与 Retriever 在此 Graph 节点内部并行执行，而不是两个独立 Graph 节点。任一分支发现间接注入时，合并后的安全风险不能被另一分支覆盖，并跳过 Resolver 与 QA。', tags: ['asyncio.gather', '间接注入检测', '并行分支'] },
  tooling: { name: '查询业务系统', code: 'Tooling · ToolRegistry', summary: '按意图查询客户、订单、历史工单及售后信息。', input: '客户标识、Intent、角色、Skill Policy', output: '结构化业务结果、调用状态、审计记录', design: '共有 9 个注册工具。查询经过 Schema、角色、风险、Skill、停用开关和 Resilience 检查。新增物流、权益、支付发票和服务状态工具只读；退款写操作不在主 Workflow 自动执行。当前适配器均为本地演示数据。', tags: ['9 个 Tool', '权限与审计', '本地 Demo Adapter'] },
  retriever: { name: '检索政策与流程', code: 'Retriever · Hybrid RAG', summary: '按知识版本与类别召回，再排序并返回引用。', input: '当前问题、Memory 检索上下文、知识版本与类别', output: '带来源、版本和评分的 citation', design: '向量检索与词法打分结合，使用轻量 rerank。中文支持双字关键词召回。知识文档在交给模型前接受安全扫描；无类别结果时会按现有策略放宽类别，仍保留版本过滤。', tags: ['ChromaDB', 'Hybrid Search', 'Citation'] },
  resolver: { name: '生成客服回复', code: 'resolver', summary: '结合必要业务字段和最相关知识，只生成回复草稿。', input: '当前问题、Top-2 citation、精简 Tool Context、Memory', output: 'suggested_response、输入/输出 Token', design: '限制上下文字符数和输出 Token，默认跟随用户当前输入语言。这里不执行退款、取消订单或其他写操作，也不能把模拟查询结果当成真实系统完成通知。', tags: ['LLM', '上下文压缩', '只生成草稿'] },
  qa: { name: '检查回复质量', code: 'qa', summary: '检查依据、引用、幻觉和敏感内容。', input: '回复草稿、引用、业务上下文、安全结果', output: 'qa_score、hallucination_detected、citation_verified、qa_strategy', design: '确定性安全失败与部分澄清由规则处理；非确定评判可使用 Jev，低置信度或故障时按策略回退轻量 LLM。质量结果进入风险评估，不代表仅凭分数就一定自动放行。', tags: ['规则 / Jev / LLM', 'Grounding', '输出过滤'] },
  escalation: { name: '决定是否交给人工', code: 'escalation · Risk Engine', summary: '综合安全、业务风险、置信度与质量，记录具体原因。', input: '优先级、意图、质量、安全信号、依赖异常', output: 'risk_level、risk_reasons、escalation_recommended、approval_required', design: '把普通咨询和实际操作分开，不因提到退款就一律审批。真实高风险操作、无法确认的结果、低质量或故障按当前规则进入人工处理；原因用于后台展示与审计。', tags: ['Risk Engine', '具体升级原因', 'HITL gating'] },
  approval_gate: { name: '审批关口与持久化暂停', code: 'approval_gate', summary: '无需审批则结束；需要审批且启用 Durable Execution 时暂停。', input: 'approval_required、Durable 配置、人工决定', output: '暂停的 Checkpoint，或审批后恢复的最终 State', design: '使用 interrupt 保存 Graph State。人工通过、修改或拒绝后，服务通过 Command(resume) 恢复原 Thread。回复审批不等于退款执行授权；高风险 Tool Action 有独立审批和状态机。', tags: ['Checkpoint', 'interrupt / resume', '持久化恢复'] },
  end: { name: '保存结果并反馈用户', code: 'END · AgentRun · Feedback', summary: '保存回复、运行记录和状态，用户可查看结果并评价。', input: '最终 State，或等待人工的执行状态', output: '已保存的回复 / 人工处理中提示、AgentRun、Trace 关联', design: '用户查询和工单详情读取已保存结果，不因打开页面再次触发 Agent。待审批时明确提示用户仍需人工处理；评价关联 AgentRun，为后续数据反馈与评测提供依据。', tags: ['PostgreSQL / SQLite', 'AgentRun', 'FeedbackEvent'] },
};

const SCENARIOS = {
  normal: { title: '普通订单查询', question: '我的订单还没有收到，能帮我查一下吗？', path: ['input', 'analyzer', 'skill_selector', 'context_enrichment', 'resolver', 'qa', 'escalation', 'approval_gate', 'end'], result: '示意：按 order_status 选择 order_support，查询订单与物流并检索配送说明；质量与风险通过后返回保存的回复。' },
  refund: { title: '退款申请待审批', question: '我想申请这笔订单的退款。', path: ['input', 'analyzer', 'skill_selector', 'context_enrichment', 'resolver', 'qa', 'escalation', 'approval_gate', 'end'], result: '示意：收集订单与账务依据并生成草稿；实际退款申请需人工确认。启用 Durable 时在审批关口暂停，审批后恢复；真正写操作走独立 Tool Action。' },
  injection: { title: '输入安全拦截', question: '示例：要求忽略系统约束并泄露内部信息。', path: ['input', 'analyzer', 'escalation', 'approval_gate', 'end'], result: '示意：Analyzer 识别安全威胁后短路，不执行 Skill、工具、RAG、Resolver 或 QA，进入风险处置并反馈安全提示。' },
  indirect: { title: '上下文安全拦截', question: '示例：工具结果或知识文档包含恶意指令。', path: ['input', 'analyzer', 'skill_selector', 'context_enrichment', 'escalation', 'approval_gate', 'end'], result: '示意：并行查询后的上下文扫描发现间接注入，隔离结果，跳过回复生成和 QA，交给风险处置。' },
};
const STAGES = ['input', 'analyzer', 'skill_selector', 'context_enrichment', 'resolver', 'qa', 'escalation', 'approval_gate', 'end'];

export default function WorkflowPage({ onBack }) {
  const [scenarioKey, setScenarioKey] = useState('normal');
  const [step, setStep] = useState(-1);
  const [selected, setSelected] = useState('analyzer');
  const scenario = SCENARIOS[scenarioKey];
  const detail = NODES[selected];
  const visited = scenario.path.slice(0, step + 1);
  const current = scenario.path[step];
  const finished = step === scenario.path.length - 1;

  function nextStep() {
    const next = Math.min(step + 1, scenario.path.length - 1);
    setStep(next);
    setSelected(scenario.path[next]);
  }

  function renderNode(key, branch = false) {
    const node = NODES[key];
    const parentActive = branch && visited.includes('context_enrichment');
    const skipped = step >= 0 && !scenario.path.includes(branch ? 'context_enrichment' : key);
    return <button type="button" className={`wf-node ${selected === key ? 'is-selected' : ''} ${visited.includes(key) || parentActive ? 'is-visited' : ''} ${current === key ? 'is-current' : ''} ${skipped ? 'is-skipped' : ''}`} onClick={() => setSelected(key)} aria-pressed={selected === key}>
      <span className="wf-node-top"><code>{node.code}</code>{(visited.includes(key) || parentActive) && <CheckCircle2 size={15} aria-label="演示路径已经过" />}</span>
      <strong>{node.name}</strong><span>{node.summary}</span>
      {skipped && <em className="wf-skipped-label">当前演示路径跳过此步骤</em>}
      {key === 'context_enrichment' && <em>两个分支并行执行 ↓</em>}
    </button>;
  }

  return <section className="wf-page">
    {onBack && <button className="wf-back" type="button" onClick={onBack}><ArrowLeft size={16} /> 返回用户咨询</button>}
    <div className="wf-hero"><div><span className="wf-eyebrow"><GitBranch size={16} /> SupportGPT · 架构演示</span><h1>从一个问题，到可追踪的处理结果</h1><p>理解问题、选择能力、并行查询、生成与校验，再决定自动回复或等待人工。</p></div><span className="wf-demo-label">架构说明 · 非实时执行</span></div>
    <div className="wf-overview">{[['7', 'LangGraph 主节点'], ['6', '版本化 Skill'], ['9', '注册业务 Tool'], ['OTel', '统一 Trace 与 Metrics']].map(([value, label]) => <div key={label}><strong>{value}</strong><span>{label}</span></div>)}</div>
    <section className="wf-scenarios" aria-label="演示场景">
      <div className="wf-section-heading"><div><h2>选择一个场景，逐步看处理路径</h2><p>这是一段本地流程演示，不发送请求、不调用模型，不展示真实业务数据或测量结果。</p></div></div>
      <div className="wf-tabs">{Object.entries(SCENARIOS).map(([key, item]) => <button type="button" key={key} aria-pressed={key === scenarioKey} className={key === scenarioKey ? 'active' : ''} onClick={() => { setScenarioKey(key); setStep(-1); setSelected('analyzer'); }}>{item.title}</button>)}</div>
      <div className="wf-example"><div><small>示例输入</small><p>{scenario.question}</p></div><div className="wf-controls"><button type="button" className="btn btn-secondary" onClick={() => { setStep(-1); setSelected('analyzer'); }}><RotateCcw size={15} /> 重置</button><button type="button" className="btn btn-primary" onClick={nextStep} disabled={finished}>{step < 0 ? '开始演示' : finished ? '演示完成' : '下一步'}<ArrowRight size={15} /></button></div></div>
      <p className="wf-scenario-result" role="status">{step < 0 ? scenario.result : `当前步骤：${NODES[current].name}（${step + 1} / ${scenario.path.length}）${finished ? '。' + scenario.result : '。点击节点可查看输入、输出和设计说明。'}`}</p>
      <div className="wf-path" aria-label="当前场景路径">{scenario.path.map((key, index) => <React.Fragment key={key}>{index > 0 && <ArrowRight size={12} />}<span className={current === key ? 'current' : visited.includes(key) ? 'visited' : ''}>{NODES[key].name}</span></React.Fragment>)}</div>
    </section>
    <div className="wf-layout">
      <section className="wf-graph" aria-label="完整 Workflow 架构图"><div className="wf-section-heading"><h2><GitBranch size={18} /> 完整处理流程</h2><span>点击节点查看详情</span></div>
        <div className="wf-flow">{STAGES.map((key, index) => <React.Fragment key={key}>
          {index > 0 && <div className="wf-connector"><ArrowDown size={18} /><span>{key === 'approval_gate' ? '是否需要审批？' : key === 'end' ? '无需审批直接结束 / 人工决定后恢复' : '传递 AgentState'}</span></div>}
          {renderNode(key)}
          {key === 'analyzer' && <div className="wf-route-note"><ShieldCheck size={14} /> 输入命中安全威胁 → escalation → approval_gate</div>}
          {key === 'context_enrichment' && <><div className="wf-parallel">{renderNode('tooling', true)}{renderNode('retriever', true)}</div><div className="wf-route-note"><ShieldCheck size={14} /> 合并结果；上下文命中安全威胁 → escalation → approval_gate</div></>}
          {key === 'approval_gate' && <div className="wf-approval"><Database size={17} /><div><strong>需要审批 + Durable 已启用</strong><p>interrupt → Checkpoint → 等待人工通过 / 修改 / 拒绝 → Command(resume)</p><small>回复审批与高风险 Tool Action 审批是两套不同流程。</small></div></div>}
        </React.Fragment>)}</div>
      </section>
      <aside className="wf-details" aria-label="节点详情"><div className="wf-detail-card"><span className="wf-eyebrow">节点说明</span><h2>{detail.name}</h2><code>{detail.code}</code><div className="wf-tags">{detail.tags.map(tag => <span key={tag}>{tag}</span>)}</div><dl><dt>接收什么</dt><dd>{detail.input}</dd><dt>产生什么</dt><dd>{detail.output}</dd><dt>为什么这样处理</dt><dd>{detail.design}</dd></dl></div>
        <div className="wf-detail-card"><h3><Layers size={17} /> 节点之间传递什么？</h3><p>AgentState 保存请求标识、Intent、Skill 快照、业务结果、引用、草稿、QA 与风险结果。Checkpoint 保存 Graph 执行状态；数据库另存工单、AgentRun、审批与审计。</p></div>
        <div className="wf-detail-card wf-boundary"><h3>演示边界</h3><p>页面展示当前代码的流程结构，场景是说明性示例，不保证真实请求一定走相同路径。实际分支由输入、运行配置、风险和质量结果决定。</p><p>工具数据为本地 Mock；模型和 Jev 是否启用取决于后端配置。初始化知识文档共 16 篇，不代表当前部署已导入全部文档。</p></div>
      </aside>
    </div>
    <section className="wf-foundations"><h2>流程之外，系统如何可靠运行</h2><div className="wf-foundation-grid">{[
      ['持久化与 Memory', 'SQL 保存工单、会话和运行记录；Redis 缓存近期上下文。Checkpoint 及执行租约支持审批后的恢复，不重新执行已完成节点。'],
      ['Tool Governance V2.2', '高风险写操作独立提议和审批，经幂等键、Transactional Outbox 与 Worker 执行。超时进入 unknown，先对账，再决定重试或人工处理。'],
      ['可观测与质量评测', 'OpenTelemetry 采集节点、LLM、RAG 和工具调用；Collector 转发 LangSmith Trace 与 Prometheus Metrics。固定 Baseline 回放检查行为，PromptOps 支持候选版本成对评测。'],
      ['故障与安全处理', 'LLM、RAG 和 Tool 使用超时、有界重试、熔断与回退。输入、工具结果、知识与输出分层检查；依赖故障和不可靠结果按风险策略反馈给用户或转人工。'],
    ].map(([title, text]) => <article key={title}><h3>{title}</h3><p>{text}</p></article>)}</div></section>
  </section>;
}
