import React, { useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  Bot,
  CheckCircle2,
  Clock3,
  Headphones,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  Star,
} from 'lucide-react';
import { submitSupportRequest, submitUserFeedback } from '../api/client';

const EXAMPLE_QUESTIONS = [
  '我的订单还没有收到，能帮我查一下吗？',
  '我想了解退款需要满足什么条件？',
  'API 一直超时，应该如何排查？',
];

const WELCOME_MESSAGE = {
  role: 'assistant',
  content: '您好，我是 SupportGPT 智能客服。请告诉我您遇到的问题，我会直接回复处理结果；需要人工确认时也会明确告知您。',
};

function createSessionId() {
  return globalThis.crypto?.randomUUID?.()
    || `support-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function sessionForCustomer(customerId) {
  const key = `supportgpt:session:${customerId}`;
  const existing = localStorage.getItem(key);
  if (existing) return existing;
  const created = createSessionId();
  localStorage.setItem(key, created);
  return created;
}

export default function CustomerSupportPage({ onStaffEntry }) {
  const [customerId, setCustomerId] = useState('cust_101');
  const [sessionId, setSessionId] = useState(() => sessionForCustomer('cust_101'));
  const [message, setMessage] = useState('');
  const [conversation, setConversation] = useState([WELCOME_MESSAGE]);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [feedbackRating, setFeedbackRating] = useState(0);
  const [feedbackComment, setFeedbackComment] = useState('');
  const [feedbackState, setFeedbackState] = useState('idle');
  const [feedbackError, setFeedbackError] = useState('');

  async function handleSubmit(event) {
    event.preventDefault();
    if (!message.trim()) return;
    setSubmitting(true);
    setResult(null);
    setError('');
    resetFeedback();
    const userMessage = message.trim();
    setMessage('');
    setConversation((current) => [...current, { role: 'user', content: userMessage }]);
    try {
      const nextResult = await submitSupportRequest(customerId, userMessage, sessionId);
      setResult(nextResult);
      setConversation((current) => [...current, {
        role: nextResult.status === 'answered' ? 'assistant' : 'status',
        content: nextResult.response || nextResult.message || '您的问题已收到，我们正在继续处理。',
        ticketId: nextResult.ticket_id,
      }]);
    } catch (requestError) {
      const errorMessage = requestError.message || '问题提交失败，请稍后重试。';
      setError(errorMessage);
      setConversation((current) => [...current, {
        role: 'error',
        content: '抱歉，本次请求暂时未能完成。您的问题仍保留在当前对话中，请稍后重试；如持续失败，请联系人工客服。',
      }]);
    } finally {
      setSubmitting(false);
    }
  }

  function resetFeedback() {
    setFeedbackRating(0);
    setFeedbackComment('');
    setFeedbackState('idle');
    setFeedbackError('');
  }

  async function handleFeedback(event) {
    event.preventDefault();
    if (!feedbackRating || !result?.agent_run_id || !result?.feedback_token) return;
    setFeedbackState('submitting');
    setFeedbackError('');
    try {
      const randomPart = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
      await submitUserFeedback(
        result.agent_run_id,
        result.feedback_token,
        feedbackRating,
        feedbackComment,
        `feedback-${result.ticket_id}-${randomPart}`,
      );
      setFeedbackState('submitted');
    } catch (requestError) {
      setFeedbackError(requestError.message || '提交评价失败，请稍后重试。');
      setFeedbackState('idle');
    }
  }

  function startNewConversation(nextCustomerId = customerId) {
    const nextSessionId = createSessionId();
    localStorage.setItem(`supportgpt:session:${nextCustomerId}`, nextSessionId);
    setCustomerId(nextCustomerId);
    setSessionId(nextSessionId);
    setConversation([WELCOME_MESSAGE]);
    setMessage('');
    setResult(null);
    setError('');
    resetFeedback();
  }

  function switchCustomer(nextCustomerId) {
    setCustomerId(nextCustomerId);
    setSessionId(sessionForCustomer(nextCustomerId));
    setConversation([WELCOME_MESSAGE]);
    setMessage('');
    setResult(null);
    setError('');
    resetFeedback();
  }

  return (
    <main className="customer-portal">
      <header className="customer-header">
        <div className="customer-brand">
          <span><Sparkles size={20} /></span>
          <div><strong>SupportGPT</strong><small>智能客户服务</small></div>
        </div>
        <button type="button" className="staff-entry" onClick={onStaffEntry}>
          <Headphones size={16} /> 客服员工入口 <ArrowRight size={15} />
        </button>
      </header>

      <section className="customer-hero">
        <div className="customer-hero-copy">
          <span className="customer-eyebrow"><ShieldCheck size={15} /> 安全、专业、可追踪</span>
          <h1>您好，需要什么帮助？</h1>
          <p>描述您的问题，智能客服会查询相关业务信息和服务政策。复杂或高风险问题将自动转交人工客服。</p>
          <div className="customer-capabilities">
            <span><CheckCircle2 size={15} /> 订单与物流</span>
            <span><CheckCircle2 size={15} /> 退款与售后</span>
            <span><CheckCircle2 size={15} /> 账户与技术支持</span>
          </div>
        </div>

        <div className="support-card">
          <div className="support-chat-toolbar">
            <div className="support-form-heading">
              <span className="support-bot"><Bot size={21} /></span>
              <div><strong>SupportGPT 智能客服</strong><small>在线 · 通常几秒内回复</small></div>
            </div>
            <button type="button" className="support-new-session" onClick={() => startNewConversation()} disabled={submitting}>
              <RefreshCw size={14} /> 新对话
            </button>
          </div>

          <label className="customer-selector support-customer-selector">
            <span>当前演示客户</span>
            <select value={customerId} onChange={(event) => switchCustomer(event.target.value)} disabled={submitting}>
              <option value="cust_101">简·多伊（VIP 客户）</option>
              <option value="cust_102">约翰·史密斯（标准客户）</option>
              <option value="cust_103">艾克米公司（企业客户）</option>
            </select>
          </label>

          <div className="support-conversation" aria-label="当前对话记录" aria-live="polite">
            {conversation.slice(-12).map((item, index) => (
              <div className={`support-message ${item.role}`} key={`${item.role}-${item.ticketId || index}-${index}`}>
                <span>{item.role === 'user' ? '您' : item.role === 'assistant' ? 'AI' : item.role === 'error' ? '异常' : '状态'}</span>
                <div>
                  <p>{item.content}</p>
                  {item.ticketId && <small>工单 #{item.ticketId}</small>}
                </div>
              </div>
            ))}
            {submitting && (
              <div className="support-message status support-typing">
                <span>AI</span><p><RefreshCw className="spin" size={13} /> 正在查询业务信息并生成回复……</p>
              </div>
            )}
          </div>

          {result?.status === 'pending_human' && (
            <div className={`support-status-panel ${result.handling_reason || 'manual_review'}`} role="status">
              {result.handling_reason === 'processing_exception' ? <AlertTriangle size={18} /> : <Clock3 size={18} />}
              <div>
                <strong>{result.handling_reason === 'risk_review' ? '该请求需要安全核验'
                  : result.handling_reason === 'processing_exception' ? '部分处理环节出现异常'
                    : result.handling_reason === 'quality_review' ? '回复需要质量复核' : '已转交人工客服'}</strong>
                <span>{result.message}</span>
              </div>
            </div>
          )}

          {result?.status === 'answered' && result.agent_run_id && result.feedback_token && (
            feedbackState === 'submitted' ? (
              <div className="feedback-success" role="status"><CheckCircle2 size={17} /> 感谢您的评价，将用于改进服务质量。</div>
            ) : (
              <form className="support-feedback support-feedback-compact" onSubmit={handleFeedback}>
                <strong>这次回答对您有帮助吗？</strong>
                <div className="feedback-rating" aria-label="回答评分">
                  {[1, 2, 3, 4, 5].map((rating) => (
                    <button
                      type="button"
                      key={rating}
                      className={feedbackRating >= rating ? 'active' : ''}
                      onClick={() => setFeedbackRating(rating)}
                      aria-label={`${rating} 分`}
                      aria-pressed={feedbackRating === rating}
                      disabled={feedbackState === 'submitting'}
                    >
                      <Star size={18} fill={feedbackRating >= rating ? 'currentColor' : 'none'} />
                    </button>
                  ))}
                </div>
                <textarea
                  value={feedbackComment}
                  onChange={(event) => setFeedbackComment(event.target.value)}
                  placeholder="可选：告诉我们哪里做得好或需要改进"
                  maxLength={2000}
                  disabled={feedbackState === 'submitting'}
                />
                {feedbackError && <span className="feedback-error" role="alert">{feedbackError}</span>}
                <button type="submit" className="support-secondary" disabled={!feedbackRating || feedbackState === 'submitting'}>
                  {feedbackState === 'submitting' ? '提交中……' : '提交评价'}
                </button>
              </form>
            )
          )}

          <form onSubmit={handleSubmit} className="support-form support-composer">
            {conversation.length === 1 && (
              <div className="question-examples">
                <span>您可以这样问</span>
                <div>{EXAMPLE_QUESTIONS.map((question) => (
                  <button type="button" key={question} onClick={() => setMessage(question)} disabled={submitting}>{question}</button>
                ))}</div>
              </div>
            )}

            <label className="support-message-field">
              <span>输入您的问题</span>
              <textarea
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                placeholder="继续描述问题或补充订单号等信息……"
                maxLength={5000}
                disabled={submitting}
                required
              />
              <small>{message.length} / 5000</small>
            </label>

            {error && <div className="support-error" role="alert">{error}</div>}

            <button className="support-submit" type="submit" disabled={submitting || !message.trim()}>
              {submitting
                ? <><RefreshCw className="spin" size={17} /> 正在处理…</>
                : <><Send size={17} /> 发送问题</>}
            </button>
            <p className="support-privacy"><ShieldCheck size={13} /> 敏感信息会被脱敏；风险或处理异常会明确反馈并转交人工。</p>
          </form>
        </div>
      </section>

      <footer className="customer-footer">SupportGPT 企业智能客服 · AI 回复可能需要人工复核</footer>
    </main>
  );
}
