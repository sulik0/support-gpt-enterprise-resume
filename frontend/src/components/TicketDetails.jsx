import React, { useState, useEffect } from 'react';
import { fetchCustomerContext, submitChat, submitApproval, evaluateResponse } from '../api/client';
import {
  translateEscalationReason,
  translateOrderItem,
  translatePriority,
  translateStatus,
  translateSubject,
  translateTier,
} from '../i18n';
import { User, ShoppingBag, ShieldAlert, Sparkles, BookOpen, CheckCircle, RefreshCw } from 'lucide-react';

export default function TicketDetails({ ticket, onActionComplete }) {
  const [customer, setCustomer] = useState(null);
  const [chatOutput, setChatOutput] = useState(null);
  const [editedResponse, setEditedResponse] = useState('');
  const [evaluation, setEvaluation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [evalLoading, setEvalLoading] = useState(false);

  // 切换工单时重新加载客户信息并触发 Agent 生成草稿。
  useEffect(() => {
    if (!ticket) return;
    setCustomer(null);
    setChatOutput(null);
    setEditedResponse('');
    setEvaluation(null);
    loadDetails();
  }, [ticket]);

  async function loadDetails() {
    setLoading(true);
    try {
      // 1. 加载 CRM 客户画像
      const crmProfile = await fetchCustomerContext(ticket.customer_id);
      setCustomer(crmProfile);

      // 2. 调用 Agent Workflow 生成回复建议
      const aiSessionId = `session_${ticket.id}`;
      const chatRes = await submitChat(ticket.description, ticket.customer_id, aiSessionId);
      setChatOutput(chatRes);
      setEditedResponse(chatRes.response);
    } catch (err) {
      console.error('加载工单详情失败：', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleApproval(status) {
    if (!chatOutput || !chatOutput.approval_id) return;
    setLoading(true);
    try {
      await submitApproval(chatOutput.approval_id, status, editedResponse);
      alert(status === 'approved' ? 'AI 回复已批准，工单处理完成。' : '人工修改已保存。');
      if (onActionComplete) onActionComplete();
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
      const contexts = chatOutput.citations.map(c => c.text);
      const evalRes = await evaluateResponse(ticket.description, contexts, editedResponse);
      setEvaluation(evalRes);
    } catch (err) {
      alert('回复评测失败：' + err.message);
    } finally {
      setEvalLoading(false);
    }
  }

  if (!ticket) {
    return (
      <div className="glass-card" style={{ display: 'flex', flex: 1, alignItems: 'center', justifyContent: 'center', height: '550px', color: '#6b7280' }}>
        请选择一个客户工单，查看详情并启动 AI 助手。
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* 1. 原始工单 */}
      <div className="glass-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.8rem' }}>
          <h2 style={{ margin: 0, fontSize: '1.2rem', fontFamily: 'Outfit, sans-serif' }}>
            工单 #{ticket.id}：{translateSubject(ticket.subject)}
          </h2>
          <span className={`badge badge-priority-${ticket.priority}`}>{translatePriority(ticket.priority)}</span>
        </div>
        <p style={{ margin: 0, fontSize: '0.95rem', color: '#d1d5db', lineHeight: 1.5, background: 'rgba(255,255,255,0.02)', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
          {ticket.description}
        </p>
      </div>

      {loading ? (
        <div className="glass-card" style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>
          <RefreshCw className="animate-spin" size={24} style={{ animation: 'spin 1.5s linear infinite' }} />
        </div>
      ) : (
        <>
          {/* 2. 客户画像与订单历史 */}
          {customer && (
            <div className="glass-card" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1.5rem' }}>
              <div>
                <h3 style={{ margin: '0 0 0.8rem 0', fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#8b5cf6' }}>
                  <User size={16} /> 客户画像
                </h3>
                <div style={{ fontSize: '0.85rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                  <div><strong>客户名称：</strong>{customer.name}</div>
                  <div><strong>邮箱：</strong>{customer.customer_id}@enterprise.com</div>
                  <div><strong>客户等级：</strong><span style={{ fontWeight: 'bold', color: '#8b5cf6' }}>{translateTier(customer.tier)}</span></div>
                  <div><strong>未结工单：</strong>{customer.open_tickets_count}</div>
                </div>
              </div>

              <div>
                <h3 style={{ margin: '0 0 0.8rem 0', fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#3b82f6' }}>
                  <ShoppingBag size={16} /> 最近订单
                </h3>
                <div style={{ fontSize: '0.85rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                  {customer.recent_orders.length === 0 ? (
                    <div style={{ color: '#6b7280' }}>暂无最近订单</div>
                  ) : (
                    customer.recent_orders.map((o, idx) => (
                      <div key={idx} style={{ padding: '0.3rem', background: 'rgba(255,255,255,0.01)', border: '1px dashed rgba(255,255,255,0.05)', borderRadius: '4px' }}>
                        <div><strong>订单号：</strong>{o.order_id}（{translateStatus(o.status)}）</div>
                        <div style={{ color: '#9ca3af', fontSize: '0.75rem' }}>商品：{o.items.map(translateOrderItem).join('、')} · 金额：${o.total_amount}</div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}

          {/* 3. AI Copilot 面板 */}
          {chatOutput && (
            <div className="glass-card" style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem', border: '1px solid rgba(139, 92, 246, 0.25)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.6rem' }}>
                <h3 style={{ margin: 0, fontSize: '1.05rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#a5b4fc', fontFamily: 'Outfit, sans-serif' }}>
                  <Sparkles size={18} color="#8b5cf6" /> SupportGPT 智能客服助手
                </h3>
                {chatOutput.approval_required && (
                  <span className="badge badge-priority-urgent" style={{ fontSize: '0.7rem' }}>
                    需要人工审批
                  </span>
                )}
              </div>

              {/* RAG 引用 */}
              <div>
                <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#9ca3af' }}>
                  <BookOpen size={14} /> RAG 检索引用
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {chatOutput.citations.length === 0 ? (
                    <div style={{ fontSize: '0.8rem', color: '#6b7280', fontStyle: 'italic' }}>未检索到可引用的知识文档</div>
                  ) : (
                    chatOutput.citations.map((c, idx) => (
                      <div key={idx} style={{ padding: '0.6rem', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)', borderRadius: '6px', fontSize: '0.8rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', color: '#3b82f6', fontWeight: '500', marginBottom: '0.2rem' }}>
                          <span>来源：{c.source}</span>
                          <span>相关度：{c.score}</span>
                        </div>
                        <div style={{ color: '#d1d5db' }}>{c.text}</div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* SLA / 人工升级提示 */}
              {chatOutput.escalation_recommended && (
                <div style={{ background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.2)', padding: '0.8rem', borderRadius: '6px', display: 'flex', alignItems: 'flex-start', gap: '0.6rem' }}>
                  <ShieldAlert color="#ef4444" size={18} style={{ flexShrink: 0, marginTop: '0.1rem' }} />
                  <div>
                    <div style={{ fontSize: '0.85rem', fontWeight: 'bold', color: '#ef4444' }}>建议升级人工处理</div>
                    <div style={{ fontSize: '0.8rem', color: '#fca5a5' }}>原因：{translateEscalationReason(chatOutput.escalation_reason)}</div>
                  </div>
                </div>
              )}

              {/* 回复草稿 */}
              <div>
                <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.85rem', color: '#9ca3af' }}>建议回复</h4>
                <textarea
                  value={editedResponse}
                  onChange={(e) => setEditedResponse(e.target.value)}
                  style={{
                    width: '100%',
                    height: '140px',
                    padding: '0.8rem',
                    borderRadius: '8px',
                    background: '#0f172a',
                    border: '1px solid var(--border-color)',
                    color: '#f3f4f6',
                    fontFamily: 'Inter, sans-serif',
                    fontSize: '0.9rem',
                    lineHeight: 1.5,
                    resize: 'vertical',
                    boxSizing: 'border-box'
                  }}
                  placeholder="请在此审核或修改 AI 回复草稿……"
                />
              </div>

              {/* Human-in-the-loop 操作 */}
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                {chatOutput.approval_required ? (
                  <>
                    <button onClick={() => handleApproval('approved')} className="btn btn-primary">
                      <CheckCircle size={16} /> 批准并关闭工单
                    </button>
                    <button onClick={() => handleApproval('modified')} className="btn btn-secondary">
                      保存人工修改
                    </button>
                  </>
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#10b981', fontSize: '0.85rem', fontWeight: '600' }}>
                    <CheckCircle size={16} /> 回复已通过校验，可以发送。
                  </div>
                )}
                
                <button onClick={triggerEvaluation} className="btn btn-secondary" style={{ marginLeft: 'auto' }}>
                  <Sparkles size={14} /> 运行 Ragas 与 DeepEval 评测
                </button>
              </div>

              {/* 评测结果 */}
              {evalLoading && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#9ca3af', fontSize: '0.85rem' }}>
                  <RefreshCw className="animate-spin" size={14} style={{ animation: 'spin 1.5s linear infinite' }} /> 正在计算评测指标……
                </div>
              )}

              {evaluation && (
                <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
                  <div style={{ fontWeight: 'bold', fontSize: '0.9rem', color: '#a5b4fc', fontFamily: 'Outfit, sans-serif' }}>
                    Ragas 与 DeepEval 评测结果
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.8rem' }}>
                    <div style={{ padding: '0.5rem', background: '#0f172a', borderRadius: '4px', textAlign: 'center' }}>
                      <div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>忠实度</div>
                      <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: '#10b981' }}>{evaluation.faithfulness_score}</div>
                    </div>
                    <div style={{ padding: '0.5rem', background: '#0f172a', borderRadius: '4px', textAlign: 'center' }}>
                      <div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>幻觉率</div>
                      <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: evaluation.hallucination_rate > 0.3 ? '#ef4444' : '#10b981' }}>{evaluation.hallucination_rate}</div>
                    </div>
                    <div style={{ padding: '0.5rem', background: '#0f172a', borderRadius: '4px', textAlign: 'center' }}>
                      <div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>上下文召回率</div>
                      <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: '#3b82f6' }}>{evaluation.context_recall}</div>
                    </div>
                    <div style={{ padding: '0.5rem', background: '#0f172a', borderRadius: '4px', textAlign: 'center' }}>
                      <div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>回答相关性</div>
                      <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: '#eab308' }}>{evaluation.answer_relevance}</div>
                    </div>
                  </div>
                  <div style={{ fontSize: '0.8rem', color: '#d1d5db', lineHeight: 1.4, borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '0.5rem' }}>
                    综合评测已完成：忠实度 {evaluation.faithfulness_score}，幻觉率 {evaluation.hallucination_rate}，上下文召回率 {evaluation.context_recall}，回答相关性 {evaluation.answer_relevance}。
                  </div>
                </div>
              )}

            </div>
          )}
        </>
      )}
    </div>
  );
}
