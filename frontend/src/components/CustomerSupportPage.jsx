import React, { useState } from 'react';
import {
  ArrowRight,
  Bot,
  CheckCircle2,
  Clock3,
  Headphones,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { submitSupportRequest } from '../api/client';

const EXAMPLE_QUESTIONS = [
  '我的订单还没有收到，能帮我查一下吗？',
  '我想了解退款需要满足什么条件？',
  'API 一直超时，应该如何排查？',
];

export default function CustomerSupportPage({ onStaffEntry }) {
  const [customerId, setCustomerId] = useState('cust_101');
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  async function handleSubmit(event) {
    event.preventDefault();
    if (!message.trim()) return;
    setSubmitting(true);
    setResult(null);
    setError('');
    try {
      setResult(await submitSupportRequest(customerId, message.trim()));
    } catch (requestError) {
      setError(requestError.message || '问题提交失败，请稍后重试。');
    } finally {
      setSubmitting(false);
    }
  }

  function resetConversation() {
    setMessage('');
    setResult(null);
    setError('');
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
          {!result && (
            <form onSubmit={handleSubmit} className="support-form">
              <div className="support-form-heading">
                <span className="support-bot"><Bot size={21} /></span>
                <div><strong>向智能客服提问</strong><small>通常几秒内完成处理</small></div>
              </div>

              <label className="customer-selector">
                <span>演示客户</span>
                <select value={customerId} onChange={(event) => setCustomerId(event.target.value)} disabled={submitting}>
                  <option value="cust_101">简·多伊（VIP 客户）</option>
                  <option value="cust_102">约翰·史密斯（标准客户）</option>
                  <option value="cust_103">艾克米公司（企业客户）</option>
                </select>
              </label>

              <label className="support-message-field">
                <span>请描述您的问题</span>
                <textarea
                  value={message}
                  onChange={(event) => setMessage(event.target.value)}
                  placeholder="例如：我的订单已经一周没有更新物流信息，请帮我查询……"
                  maxLength={5000}
                  disabled={submitting}
                  required
                />
                <small>{message.length} / 5000</small>
              </label>

              <div className="question-examples">
                <span>常见问题</span>
                <div>{EXAMPLE_QUESTIONS.map((question) => (
                  <button type="button" key={question} onClick={() => setMessage(question)} disabled={submitting}>{question}</button>
                ))}</div>
              </div>

              {error && <div className="support-error" role="alert">{error}</div>}

              <button className="support-submit" type="submit" disabled={submitting || !message.trim()}>
                {submitting
                  ? <><RefreshCw className="spin" size={17} /> 智能客服正在处理…</>
                  : <><Send size={17} /> 提交问题</>}
              </button>
              <p className="support-privacy"><ShieldCheck size={13} /> 系统会对敏感信息进行脱敏，并对回复执行安全校验。</p>
            </form>
          )}

          {result?.status === 'answered' && (
            <section className="support-result answered" aria-live="polite">
              <span className="result-icon"><CheckCircle2 size={28} /></span>
              <div className="result-heading"><span>工单 #{result.ticket_id}</span><strong>智能客服已完成回复</strong></div>
              <div className="customer-answer"><Bot size={18} /><p>{result.response}</p></div>
              <button type="button" className="support-secondary" onClick={resetConversation}>继续提问</button>
            </section>
          )}

          {result?.status === 'pending_human' && (
            <section className="support-result pending" aria-live="polite">
              <span className="result-icon"><Clock3 size={28} /></span>
              <div className="result-heading"><span>工单 #{result.ticket_id}</span><strong>已转交人工客服</strong></div>
              <p>{result.message}</p>
              <div className="human-review-note"><Headphones size={18} /><span>客服员工将在后台核对 AI 草稿、业务信息和风险原因后处理。</span></div>
              <button type="button" className="support-secondary" onClick={resetConversation}>提交其他问题</button>
            </section>
          )}
        </div>
      </section>

      <footer className="customer-footer">SupportGPT 企业智能客服 · AI 回复可能需要人工复核</footer>
    </main>
  );
}
