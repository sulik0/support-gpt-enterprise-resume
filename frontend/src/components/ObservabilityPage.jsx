import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  Bot,
  Check,
  Clock3,
  Copy,
  ExternalLink,
  RefreshCw,
  Route,
  ShieldAlert,
  Sparkles,
  X,
} from 'lucide-react';
import { fetchAgentRun, fetchAgentRuns } from '../api/client';

const PAGE_SIZE = 20;
const LANGSMITH_PROJECT_URL = import.meta.env.VITE_LANGSMITH_PROJECT_URL || 'https://smith.langchain.com/';
const HAS_PROJECT_URL = Boolean(import.meta.env.VITE_LANGSMITH_PROJECT_URL);

const NODE_LABELS = {
  ticket_analyzer: '工单分析',
  tool_call: '工具调用',
  retriever: '知识检索',
  llm_generation: '回复生成',
  qa: '质量校验',
  escalation: '升级判断',
};

function formatDate(value) {
  if (!value) return '-';
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date(value));
}

function runStatus(run) {
  if (run.workflow_errors?.length) return { label: '异常', className: 'status-error' };
  if (run.approval_required || run.escalation_recommended) {
    return { label: '待人工', className: 'status-review' };
  }
  return { label: '已完成', className: 'status-success' };
}

function SummaryCard({ icon, label, value, hint }) {
  return (
    <div className="obs-summary-card glass-card">
      <span className="obs-summary-icon">{icon}</span>
      <div>
        <div className="obs-summary-label">{label}</div>
        <div className="obs-summary-value">{value}</div>
        <div className="obs-summary-hint">{hint}</div>
      </div>
    </div>
  );
}

function RunDetail({ run, loading, onClose, onCopyTrace, copiedTrace }) {
  if (!run && !loading) return null;
  return (
    <div className="obs-detail-backdrop" onClick={onClose}>
      <aside className="obs-detail-panel" onClick={(event) => event.stopPropagation()}>
        <div className="obs-detail-header">
          <div>
            <span className="obs-eyebrow">Agent Run</span>
            <h2>{run?.id || '正在加载…'}</h2>
          </div>
          <button className="obs-icon-button" onClick={onClose} aria-label="关闭运行详情">
            <X size={18} />
          </button>
        </div>

        {loading ? (
          <div className="obs-empty"><RefreshCw className="spin" size={20} /> 正在加载运行详情…</div>
        ) : (
          <div className="obs-detail-content">
            <section className="obs-detail-section">
              <h3>Trace 关联</h3>
              <div className="obs-trace-box">
                <code>{run.trace_id || '本次运行未采集 Trace ID'}</code>
                {run.trace_id && (
                  <button className="obs-icon-button" onClick={() => onCopyTrace(run.trace_id)} title="复制 Trace ID">
                    {copiedTrace === run.trace_id ? <Check size={16} /> : <Copy size={16} />}
                  </button>
                )}
              </div>
              <a className="btn btn-primary obs-link-button" href={LANGSMITH_PROJECT_URL} target="_blank" rel="noreferrer">
                在 LangSmith 中查看 <ExternalLink size={15} />
              </a>
              <p className="obs-helper">打开 Project 后使用上方 Trace ID 定位完整 Span 链路。</p>
            </section>

            <section className="obs-detail-section">
              <h3>Workflow 路径</h3>
              <div className="obs-workflow">
                {(run.workflow_path || []).map((node, index) => (
                  <React.Fragment key={`${node}-${index}`}>
                    <div className="obs-node"><span>{index + 1}</span>{NODE_LABELS[node] || node}</div>
                    {index < run.workflow_path.length - 1 && <div className="obs-arrow">→</div>}
                  </React.Fragment>
                ))}
              </div>
            </section>

            <section className="obs-detail-section">
              <h3>执行快照</h3>
              <dl className="obs-kv-grid">
                <div><dt>模型</dt><dd>{run.model_provider} / {run.model_name}</dd></div>
                <div><dt>Prompt</dt><dd>{run.prompt_version}</dd></div>
                <div><dt>Workflow</dt><dd>{run.workflow_version}</dd></div>
                <div><dt>知识库</dt><dd>{run.kb_version}</dd></div>
                <div><dt>延迟</dt><dd>{run.latency_seconds.toFixed(3)}s</dd></div>
                <div><dt>Token</dt><dd>{run.tokens_input + run.tokens_output}</dd></div>
                <div><dt>QA Score</dt><dd>{run.qa_score == null ? '-' : run.qa_score.toFixed(2)}</dd></div>
                <div><dt>人工审批</dt><dd>{run.approval_required ? '需要' : '不需要'}</dd></div>
              </dl>
            </section>

            <section className="obs-detail-section">
              <h3>工具与引用</h3>
              <div className="obs-compact-list">
                {(run.tool_calls || []).length ? run.tool_calls.map((tool, index) => (
                  <div key={`${tool.tool_name}-${index}`}>
                    <Bot size={15} />
                    <span>{tool.tool_name || '未命名工具'}</span>
                    <em>{tool.status || '未知'}</em>
                  </div>
                )) : <p>本次运行没有 Tool Calling 记录。</p>}
                {(run.citations || []).map((citation, index) => (
                  <div key={`${citation.source}-${index}`}>
                    <Sparkles size={15} />
                    <span>{citation.source || '未命名知识来源'}</span>
                    <em>citation</em>
                  </div>
                ))}
              </div>
            </section>

            {(run.workflow_errors || []).length > 0 && (
              <section className="obs-detail-section obs-error-section">
                <h3><AlertTriangle size={16} /> Workflow 异常</h3>
                {run.workflow_errors.map((error, index) => <p key={index}>{error}</p>)}
              </section>
            )}

            <section className="obs-detail-section">
              <h3>脱敏输入与回复</h3>
              <div className="obs-text-snapshot"><strong>用户输入</strong><p>{run.input_text}</p></div>
              <div className="obs-text-snapshot"><strong>Agent 回复</strong><p>{run.output_text}</p></div>
            </section>
          </div>
        )}
      </aside>
    </div>
  );
}

export default function ObservabilityPage() {
  const [page, setPage] = useState({ items: [], total: 0, limit: PAGE_SIZE, offset: 0 });
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedRun, setSelectedRun] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [copiedTrace, setCopiedTrace] = useState('');

  const loadRuns = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setPage(await fetchAgentRuns(PAGE_SIZE, offset));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }, [offset]);

  useEffect(() => { loadRuns(); }, [loadRuns]);

  const summary = useMemo(() => {
    const runs = page.items;
    const totalTokens = runs.reduce((sum, run) => sum + run.tokens_input + run.tokens_output, 0);
    const averageLatency = runs.length
      ? runs.reduce((sum, run) => sum + run.latency_seconds, 0) / runs.length
      : 0;
    const reviewCount = runs.filter((run) => run.approval_required || run.escalation_recommended).length;
    return { totalTokens, averageLatency, reviewCount };
  }, [page.items]);

  async function openRun(runId) {
    setDetailLoading(true);
    setSelectedRun({ id: runId });
    try {
      setSelectedRun(await fetchAgentRun(runId));
    } catch (requestError) {
      setError(requestError.message);
      setSelectedRun(null);
    } finally {
      setDetailLoading(false);
    }
  }

  async function copyTrace(traceId) {
    await navigator.clipboard.writeText(traceId);
    setCopiedTrace(traceId);
    window.setTimeout(() => setCopiedTrace(''), 1600);
  }

  const canGoNext = offset + PAGE_SIZE < page.total;

  return (
    <section className="observability-page">
      <div className="obs-hero glass-card">
        <div>
          <span className="obs-eyebrow"><Activity size={14} /> Agent Observability</span>
          <h2>LangSmith 链路观测</h2>
          <p>从 Agent Run 快照定位 Trace ID，再进入 LangSmith 查看 Workflow、LLM、Retriever 和 Tool Span。</p>
        </div>
        <div className="obs-hero-actions">
          <button className="btn btn-secondary" onClick={loadRuns} disabled={loading}>
            <RefreshCw size={15} className={loading ? 'spin' : ''} /> 刷新
          </button>
          <a className="btn btn-primary" href={LANGSMITH_PROJECT_URL} target="_blank" rel="noreferrer">
            打开 LangSmith <ExternalLink size={15} />
          </a>
        </div>
      </div>

      {!HAS_PROJECT_URL && (
        <div className="obs-config-notice">
          <ShieldAlert size={17} />
          当前未配置具体 Project URL，按钮将打开 LangSmith 首页。可在前端环境变量中设置 <code>VITE_LANGSMITH_PROJECT_URL</code>。
        </div>
      )}

      <div className="obs-summary-grid">
        <SummaryCard icon={<Route size={20} />} label="Agent Run" value={page.total} hint="已持久化总数" />
        <SummaryCard icon={<Clock3 size={20} />} label="平均延迟" value={`${summary.averageLatency.toFixed(2)}s`} hint="当前页运行" />
        <SummaryCard icon={<Bot size={20} />} label="Token 用量" value={summary.totalTokens.toLocaleString()} hint="当前页输入 + 输出" />
        <SummaryCard icon={<ShieldAlert size={20} />} label="人工介入" value={summary.reviewCount} hint="当前页升级 / 审批" />
      </div>

      <div className="obs-runs-card glass-card">
        <div className="obs-table-heading">
          <div><h3>Agent Run 列表</h3><p>仅主管和管理员可查看</p></div>
          <span>{page.total ? offset + 1 : 0}–{Math.min(offset + PAGE_SIZE, page.total)} / {page.total}</span>
        </div>

        {error && <div className="obs-error-banner"><AlertTriangle size={17} /> {error}</div>}
        {loading ? (
          <div className="obs-empty"><RefreshCw className="spin" size={20} /> 正在加载 Agent Run…</div>
        ) : page.items.length === 0 ? (
          <div className="obs-empty">暂无 Agent Run，请先执行一次 <code>/chat</code>。</div>
        ) : (
          <div className="obs-table-wrap">
            <table className="obs-table">
              <thead><tr><th>时间</th><th>Run / Trace</th><th>Workflow</th><th>质量</th><th>消耗</th><th>状态</th></tr></thead>
              <tbody>
                {page.items.map((run) => {
                  const status = runStatus(run);
                  return (
                    <tr key={run.id} onClick={() => openRun(run.id)} tabIndex={0} onKeyDown={(event) => event.key === 'Enter' && openRun(run.id)}>
                      <td>{formatDate(run.created_at)}</td>
                      <td><code>{run.id.slice(0, 8)}</code><small>{run.trace_id ? `Trace ${run.trace_id.slice(0, 10)}…` : '无 Trace ID'}</small></td>
                      <td><strong>{run.workflow_path?.length || 0} 节点</strong><small>{run.model_name}</small></td>
                      <td><strong>{run.qa_score == null ? '-' : run.qa_score.toFixed(2)}</strong><small>{run.hallucination_detected ? '幻觉风险' : '未检出幻觉'}</small></td>
                      <td><strong>{run.latency_seconds.toFixed(2)}s</strong><small>{(run.tokens_input + run.tokens_output).toLocaleString()} Token</small></td>
                      <td><span className={`obs-status ${status.className}`}>{status.label}</span></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="obs-pagination">
          <button className="btn btn-secondary" disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>上一页</button>
          <button className="btn btn-secondary" disabled={!canGoNext || loading} onClick={() => setOffset(offset + PAGE_SIZE)}>下一页</button>
        </div>
      </div>

      <RunDetail run={selectedRun} loading={detailLoading} onClose={() => setSelectedRun(null)} onCopyTrace={copyTrace} copiedTrace={copiedTrace} />
    </section>
  );
}
