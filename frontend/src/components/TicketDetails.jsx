import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ClipboardCheck,
  FileText,
  RefreshCw,
  ShieldAlert,
  ShoppingBag,
  Sparkles,
  User,
} from 'lucide-react';
import { evaluateResponse, fetchCustomerContext, fetchTicketAgentResult, submitApproval } from '../api/client';
import {
  translateEscalationReason,
  translateOrderItem,
  translatePriority,
  translateStatus,
  translateSubject,
  translateTier,
} from '../i18n';

export default function TicketDetails({ ticket, onActionComplete }) {
  const [customer, setCustomer] = useState(null);
  const [chatOutput, setChatOutput] = useState(null);
  const [editedResponse, setEditedResponse] = useState('');
  const [evaluation, setEvaluation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [evalLoading, setEvalLoading] = useState(false);
  const [loadError, setLoadError] = useState('');

  // 切换工单时只读取已经持久化的 Agent 结果。
  useEffect(() => {
    if (!ticket) return;
    setCustomer(null);
    setChatOutput(null);
    setEditedResponse('');
    setEvaluation(null);
    setLoadError('');
    loadDetails();
  }, [ticket]);

  async function loadDetails() {
    setLoading(true);
    setLoadError('');
    try {
      const crmProfile = await fetchCustomerContext(ticket.customer_id);
      setCustomer(crmProfile);
      const chatRes = await fetchTicketAgentResult(ticket.id);
      setChatOutput(chatRes);
      setEditedResponse(chatRes.response);
    } catch (err) {
      console.error('加载工单详情失败：', err);
      setLoadError(err.message || 'Agent 处理失败，请稍后重试。');
    } finally {
      setLoading(false);
    }
  }

  async function handleApproval(status) {
    if (!chatOutput?.approval_id) return;
    setLoading(true);
    try {
      await submitApproval(chatOutput.approval_id, status, editedResponse);
      alert(status === 'approved' ? 'AI 回复已批准，工单处理完成。' : '人工修改已保存。');
      onActionComplete?.();
    } catch (err) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function triggerEvaluation() {
    if (!chatOutput) return;
    setEvalLoading(true);
    try {
      const contexts = (chatOutput.citations || []).map((citation) => citation.text);
      setEvaluation(await evaluateResponse(ticket.description, contexts, editedResponse));
    } catch (err) {
      alert(`回复评测失败：${err.message}`);
    } finally {
      setEvalLoading(false);
    }
  }

  if (!ticket) {
    return (
      <section className="ticket-empty-state">
        <span className="empty-state-icon"><ClipboardCheck size={34} /></span>
        <span className="section-label">等待处理</span>
        <h2>从人工队列中选择一张工单</h2>
        <p>普通问题会自动回复；这里只展示 Agent 判定为高风险、低置信度或需要人工审批的已保存结果。</p>
        <div className="empty-workflow">
          <span>1. 理解诉求</span><i />
          <span>2. 补全上下文</span><i />
          <span>3. 生成回复</span><i />
          <span>4. 人工确认</span>
        </div>
      </section>
    );
  }

  const citations = chatOutput?.citations || [];
  const recentOrders = customer?.recent_orders || [];

  return (
    <section className="ticket-detail">
      <header className="ticket-detail-header">
        <div>
          <div className="ticket-detail-meta">
            <span>工单 #{ticket.id}</span>
            <span className={`status-chip status-${ticket.status || 'open'}`}>{translateStatus(ticket.status)}</span>
            <span className={`priority-chip priority-${ticket.priority || 'medium'}`}>{translatePriority(ticket.priority)}优先级</span>
          </div>
          <h2>{translateSubject(ticket.subject)}</h2>
          <p>客户 {ticket.customer_id} · 处理结果知识库 {chatOutput?.kb_version || '加载中'}</p>
        </div>
        <button className="btn btn-secondary compact-button" onClick={loadDetails} disabled={loading}>
          <RefreshCw size={15} className={loading ? 'spin' : ''} /> 刷新保存结果
        </button>
      </header>

      <div className="workflow-progress" aria-label="工单处理进度">
        <span className="complete"><i>1</i>读取工单</span><b />
        <span className={loading || chatOutput ? 'complete' : 'active'}><i>2</i>Agent 分析</span><b />
        <span className={chatOutput ? 'complete' : ''}><i>3</i>生成建议</span><b />
        <span className={chatOutput?.approval_required ? 'active' : chatOutput ? 'complete' : ''}><i>4</i>人工确认</span>
      </div>

      <div className="case-context-grid">
        <article className="detail-card issue-card">
          <div className="card-heading"><span className="card-icon blue"><FileText size={17} /></span><div><span>客户原始诉求</span><small>Agent 分析的输入内容</small></div></div>
          <p>{ticket.description}</p>
        </article>

        <article className="detail-card customer-card">
          <div className="card-heading"><span className="card-icon purple"><User size={17} /></span><div><span>客户上下文</span><small>来自客户关系管理系统</small></div></div>
          {customer ? (
            <div className="customer-facts">
              <div><span>客户</span><strong>{customer.name}</strong></div>
              <div><span>等级</span><strong>{translateTier(customer.tier)}</strong></div>
              <div><span>未结工单</span><strong>{customer.open_tickets_count}</strong></div>
              <div><span>最近订单</span><strong>{recentOrders.length}</strong></div>
            </div>
          ) : <div className="context-placeholder">正在获取客户画像…</div>}
        </article>
      </div>

      {customer && recentOrders.length > 0 && (
        <details className="orders-disclosure">
          <summary><span><ShoppingBag size={16} /> 最近订单</span><span>{recentOrders.length} 笔 <ChevronDown size={15} /></span></summary>
          <div className="orders-grid">
            {recentOrders.map((order) => (
              <div className="order-item" key={order.order_id}>
                <div><strong>{order.order_id}</strong><span>{translateStatus(order.status)}</span></div>
                <p>{order.items.map(translateOrderItem).join('、')}</p>
                <b>${order.total_amount}</b>
              </div>
            ))}
          </div>
        </details>
      )}

      {loading && (
        <div className="agent-loading-card">
          <span className="agent-orbit"><Sparkles size={22} /></span>
          <div><strong>正在加载已保存的 Agent 结果</strong><p>正在读取客户上下文、引用依据与回复草稿，请稍候……</p></div>
          <span className="loading-dots"><i /><i /><i /></span>
        </div>
      )}

      {!loading && loadError && (
        <div className="detail-error"><AlertTriangle size={19} /><div><strong>本次 Agent 运行失败</strong><span>{loadError}</span></div><button className="btn btn-secondary" onClick={loadDetails}>重试</button></div>
      )}

      {!loading && chatOutput && (
        <article className="assistant-panel">
          <header className="assistant-heading">
            <div className="assistant-title">
              <span className="assistant-logo"><Sparkles size={19} /></span>
              <div><span>SupportGPT 建议</span><small>已完成检索、工具调用与质量校验</small></div>
            </div>
            <div className="assistant-badges">
              <span className="evidence-badge"><BookOpen size={13} /> {citations.length} 条知识依据</span>
              {chatOutput.approval_required
                ? <span className="review-badge"><ShieldAlert size={13} /> 待人工审批</span>
                : <span className="passed-badge"><CheckCircle2 size={13} /> 自动校验通过</span>}
            </div>
          </header>

          {chatOutput.escalation_recommended && (
            <div className="escalation-banner">
              <ShieldAlert size={19} />
              <div><strong>建议升级人工处理</strong><span>{translateEscalationReason(chatOutput.escalation_reason)}</span></div>
            </div>
          )}

          <div className="draft-section">
            <div className="draft-label"><div><strong>回复草稿</strong><span>发送前可直接编辑</span></div><span>{editedResponse.length} 字</span></div>
            <textarea value={editedResponse} onChange={(event) => setEditedResponse(event.target.value)} placeholder="Agent 回复草稿将在这里生成……" />
          </div>

          <details className="reference-disclosure">
            <summary>
              <span><BookOpen size={16} /> 查看知识引用与检索依据</span>
              <span>{citations.length} 条 <ChevronDown size={15} /></span>
            </summary>
            <div className="reference-list">
              {citations.length === 0 ? <p className="no-reference">本次未检索到可引用的知识文档。</p> : citations.map((citation, index) => (
                <div className="reference-item" key={`${citation.source}-${index}`}>
                  <div><span>{index + 1}</span><strong>{citation.source}</strong><em>相关度 {citation.score}</em></div>
                  <p>{citation.text}</p>
                </div>
              ))}
            </div>
          </details>

          <footer className="assistant-actions">
            <div>
              {chatOutput.approval_required ? (
                <><button onClick={() => handleApproval('approved')} className="btn btn-primary"><CheckCircle2 size={16} /> 批准 AI 回复</button><button onClick={() => handleApproval('modified')} className="btn btn-secondary">发送人工修改</button></>
              ) : <span className="no-review-needed"><CheckCircle2 size={16} /> 此回复无需人工审批</span>}
            </div>
            <button onClick={triggerEvaluation} className="btn btn-quiet" disabled={evalLoading}>
              <Sparkles size={14} className={evalLoading ? 'spin' : ''} /> {evalLoading ? '评测中…' : '运行质量评测'}
            </button>
          </footer>

          {evaluation && (
            <section className="evaluation-panel">
              <div className="evaluation-heading"><div><span>离线质量评测</span><small>Ragas + DeepEval</small></div><CheckCircle2 size={19} /></div>
              <div className="evaluation-grid">
                <div><span>忠实度</span><strong>{evaluation.faithfulness_score}</strong></div>
                <div><span>幻觉率</span><strong className={evaluation.hallucination_rate > 0.3 ? 'score-risk' : ''}>{evaluation.hallucination_rate}</strong></div>
                <div><span>上下文召回</span><strong>{evaluation.context_recall}</strong></div>
                <div><span>回答相关性</span><strong>{evaluation.answer_relevance}</strong></div>
              </div>
            </section>
          )}
        </article>
      )}
    </section>
  );
}
