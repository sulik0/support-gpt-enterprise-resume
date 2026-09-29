import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  FileCode2,
  Plus,
  RefreshCw,
  Save,
  Settings2,
  ShieldCheck,
  Trash2,
  Wrench,
} from 'lucide-react';
import {
  createPromptCandidate,
  deleteAdminRagDocument,
  fetchAdminPrompts,
  fetchAdminRagDocuments,
  fetchAdminTools,
  reindexAdminRagDocuments,
  saveAdminRagDocument,
  updateAdminTool,
} from '../api/client';

const EMPTY_DOCUMENT = {
  id: '', title: '', category: 'faq', version: 'v1', content: '', metadata: '{}',
};

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function shortHash(value) {
  return value ? `${value.slice(0, 10)}…${value.slice(-6)}` : '未设置';
}

export default function ResourceManagementPage() {
  const [activeTab, setActiveTab] = useState('tools');
  const [tools, setTools] = useState([]);
  const [prompts, setPrompts] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyKey, setBusyKey] = useState('');
  const [notice, setNotice] = useState(null);
  const [promptDraft, setPromptDraft] = useState(null);
  const [editingDocumentId, setEditingDocumentId] = useState(null);
  const [documentDraft, setDocumentDraft] = useState(EMPTY_DOCUMENT);

  async function loadResources() {
    setLoading(true);
    setNotice(null);
    try {
      const [toolItems, promptState, documentItems] = await Promise.all([
        fetchAdminTools(), fetchAdminPrompts(), fetchAdminRagDocuments(),
      ]);
      setTools(toolItems);
      setPrompts(promptState);
      setDocuments(documentItems);
    } catch (error) {
      setNotice({ type: 'error', text: error.message || '加载管理资源失败。' });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadResources(); }, []);

  async function toggleTool(tool) {
    const enabled = !tool.enabled;
    let reason = '管理员恢复启用';
    if (!enabled) {
      reason = window.prompt(`请输入停用 ${tool.name} 的原因：`, '运维管控')?.trim();
      if (!reason) return;
    }
    setBusyKey(tool.name);
    try {
      const updated = await updateAdminTool(tool.name, enabled, reason);
      setTools((items) => items.map((item) => item.name === tool.name ? updated : item));
      setNotice({ type: 'success', text: `${tool.name} 已${enabled ? '启用' : '停用'}。` });
    } catch (error) {
      setNotice({ type: 'error', text: error.message });
    } finally {
      setBusyKey('');
    }
  }

  function beginPromptCandidate() {
    const source = prompts?.effective?.production?.payload;
    if (!source) return;
    const draft = clone(source);
    draft.version = `${source.version}-candidate`;
    setPromptDraft(draft);
  }

  function updatePromptTemplate(node, role, value) {
    setPromptDraft((current) => ({
      ...current,
      templates: {
        ...current.templates,
        [node]: { ...current.templates[node], [role]: value },
      },
    }));
  }

  async function savePrompt(event) {
    event.preventDefault();
    setBusyKey('prompt');
    try {
      const created = await createPromptCandidate(promptDraft);
      const refreshed = await fetchAdminPrompts();
      setPrompts(refreshed);
      setPromptDraft(null);
      setNotice({ type: 'success', text: `已创建候选 Bundle ${created.version}，生产晋级仍需通过 EvalOps。` });
    } catch (error) {
      setNotice({ type: 'error', text: error.message });
    } finally {
      setBusyKey('');
    }
  }

  function beginDocument(document = null) {
    if (!document) {
      setEditingDocumentId(null);
      setDocumentDraft(EMPTY_DOCUMENT);
      return;
    }
    setEditingDocumentId(document.id);
    setDocumentDraft({
      ...document,
      metadata: JSON.stringify(document.metadata || {}, null, 2),
    });
  }

  async function saveDocument(event) {
    event.preventDefault();
    let metadata;
    try {
      metadata = JSON.parse(documentDraft.metadata || '{}');
    } catch {
      setNotice({ type: 'error', text: 'Metadata 必须是有效 JSON。' });
      return;
    }
    setBusyKey('document');
    try {
      const payload = { ...documentDraft, metadata };
      await saveAdminRagDocument(payload, editingDocumentId);
      setDocuments(await fetchAdminRagDocuments());
      setEditingDocumentId(null);
      setDocumentDraft(EMPTY_DOCUMENT);
      setNotice({ type: 'success', text: `文档 ${payload.id} 及向量索引已更新。` });
    } catch (error) {
      setNotice({ type: 'error', text: error.message });
    } finally {
      setBusyKey('');
    }
  }

  async function removeDocument(document) {
    if (!window.confirm(`确认删除「${document.title}」及其全部向量 Chunk？`)) return;
    setBusyKey(`delete:${document.id}`);
    try {
      await deleteAdminRagDocument(document.id);
      setDocuments((items) => items.filter((item) => item.id !== document.id));
      if (editingDocumentId === document.id) beginDocument();
      setNotice({ type: 'success', text: `文档 ${document.id} 已删除。` });
    } catch (error) {
      setNotice({ type: 'error', text: error.message });
    } finally {
      setBusyKey('');
    }
  }

  async function reindexDocuments() {
    setBusyKey('reindex');
    try {
      const result = await reindexAdminRagDocuments();
      setNotice({ type: 'success', text: `已从 SQL 权威数据重建 ${result.indexed_documents} 篇文档的向量索引。` });
    } catch (error) {
      setNotice({ type: 'error', text: error.message });
    } finally {
      setBusyKey('');
    }
  }

  const toolStats = useMemo(() => ({
    total: tools.length,
    enabled: tools.filter((item) => item.enabled).length,
    highRisk: tools.filter((item) => item.risk_level === 'high').length,
  }), [tools]);

  return (
    <section className="resource-page">
      <div className="resource-hero">
        <div>
          <span className="resource-eyebrow"><ShieldCheck size={14} /> 管理员专属</span>
          <h2>Agent 资源与能力治理</h2>
          <p>统一查看 Tool Registry、Prompt Bundle 和 RAG 知识文档，所有变更均保留现有权限与发布边界。</p>
        </div>
        <button className="btn btn-secondary" onClick={loadResources} disabled={loading}>
          <RefreshCw size={15} className={loading ? 'spin' : ''} /> 刷新全部
        </button>
      </div>

      {notice && (
        <div className={`resource-notice ${notice.type}`} role="status">
          {notice.type === 'success' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
          {notice.text}
        </div>
      )}

      <div className="resource-tabs" role="tablist">
        <button className={activeTab === 'tools' ? 'active' : ''} onClick={() => setActiveTab('tools')}>
          <Wrench size={16} /> Tools <span>{tools.length}</span>
        </button>
        <button className={activeTab === 'prompts' ? 'active' : ''} onClick={() => setActiveTab('prompts')}>
          <FileCode2 size={16} /> Prompts <span>{prompts?.bundles?.length || 0}</span>
        </button>
        <button className={activeTab === 'rag' ? 'active' : ''} onClick={() => setActiveTab('rag')}>
          <BookOpen size={16} /> RAG 文档 <span>{documents.length}</span>
        </button>
      </div>

      {loading ? <div className="resource-loading"><RefreshCw className="spin" /> 正在加载资源…</div> : null}

      {!loading && activeTab === 'tools' && (
        <div className="resource-section">
          <div className="resource-stat-row">
            <div><span>已注册</span><strong>{toolStats.total}</strong></div>
            <div><span>已启用</span><strong>{toolStats.enabled}</strong></div>
            <div><span>高风险</span><strong>{toolStats.highRisk}</strong></div>
          </div>
          <div className="tool-admin-grid">
            {tools.map((tool) => (
              <article className={`tool-admin-card ${tool.enabled ? '' : 'disabled'}`} key={tool.name}>
                <div className="tool-admin-heading">
                  <div><code>{tool.name}</code><p>{tool.description}</p></div>
                  <span className={tool.enabled ? 'resource-status enabled' : 'resource-status disabled'}>
                    {tool.enabled ? '运行中' : '已停用'}
                  </span>
                </div>
                <div className="tool-admin-tags">
                  <span>{tool.operation_type === 'write' ? '写操作' : '读操作'}</span>
                  <span>{tool.risk_level} risk</span><span>{tool.min_role}+</span><span>{tool.version}</span>
                </div>
                {tool.disabled_reason && <p className="tool-disabled-reason">停用原因：{tool.disabled_reason}</p>}
                <details><summary>查看 Schema 与意图边界</summary><pre>{JSON.stringify({ input: tool.input_schema, output: tool.output_schema, allowed_intents: tool.allowed_intents }, null, 2)}</pre></details>
                <button
                  className={`btn ${tool.enabled ? 'btn-danger-outline' : 'btn-secondary'}`}
                  disabled={busyKey === tool.name}
                  onClick={() => toggleTool(tool)}
                >
                  <Settings2 size={14} /> {tool.enabled ? '停用 Tool' : '恢复启用'}
                </button>
              </article>
            ))}
          </div>
        </div>
      )}

      {!loading && activeTab === 'prompts' && prompts && (
        <div className="resource-section prompt-admin-layout">
          <div className="prompt-admin-main">
            <div className="resource-section-heading">
              <div><h3>Prompt Bundle</h3><p>Bundle 按内容 Hash 不可变保存。</p></div>
              <button className="btn btn-primary" onClick={beginPromptCandidate}><Plus size={15} /> 基于生产版创建候选</button>
            </div>
            <div className="prompt-environments">
              {['production', 'staging'].map((environment) => {
                const bundle = prompts.effective[environment];
                return <div key={environment}><span>{environment}</span><strong>{bundle.version}</strong><code>{shortHash(bundle.bundle_id)}</code></div>;
              })}
            </div>
            <div className="prompt-bundle-list">
              {prompts.bundles.map((bundle) => (
                <details key={bundle.bundle_id}>
                  <summary><div><strong>{bundle.version}</strong><code>{shortHash(bundle.bundle_id)}</code></div><span>{Object.keys(bundle.payload.templates).length} 个节点</span></summary>
                  <pre>{JSON.stringify(bundle.payload, null, 2)}</pre>
                </details>
              ))}
            </div>
          </div>

          <aside className="prompt-governance-card">
            <ShieldCheck size={20} /><h3>发布边界</h3>
            <p>后台只能创建候选 Bundle，不能直接修改 production pointer。候选版必须经过 EvalOps 成对回放和质量门禁才能晋级。</p>
          </aside>

          {promptDraft && (
            <form className="prompt-editor" onSubmit={savePrompt}>
              <div className="resource-section-heading"><div><h3>新候选 Bundle</h3><p>占位符合同由 PromptOps 在后端严格验证。</p></div><button type="button" className="icon-button" onClick={() => setPromptDraft(null)}>×</button></div>
              <label><span>版本标签</span><input value={promptDraft.version} onChange={(event) => setPromptDraft({ ...promptDraft, version: event.target.value })} required /></label>
              {['analyzer', 'resolver', 'qa'].map((node) => (
                <fieldset key={node}><legend>{node}</legend>
                  {['system', 'user'].map((role) => <label key={role}><span>{role}</span><textarea rows={role === 'system' ? 5 : 3} value={promptDraft.templates[node][role]} onChange={(event) => updatePromptTemplate(node, role, event.target.value)} required /></label>)}
                </fieldset>
              ))}
              <div className="resource-form-actions"><button type="button" className="btn btn-secondary" onClick={() => setPromptDraft(null)}>取消</button><button className="btn btn-primary" disabled={busyKey === 'prompt'}><Save size={15} /> 保存不可变候选</button></div>
            </form>
          )}
        </div>
      )}

      {!loading && activeTab === 'rag' && (
        <div className="resource-section rag-admin-layout">
          <div className="rag-document-list">
            <div className="resource-section-heading"><div><h3>知识文档</h3><p>SQL 保存权威内容，ChromaDB 保存检索向量。</p></div><button className="btn btn-secondary" onClick={reindexDocuments} disabled={busyKey === 'reindex'}><RefreshCw size={14} className={busyKey === 'reindex' ? 'spin' : ''} /> 全量重建索引</button></div>
            {documents.length === 0 && <div className="resource-empty">尚无知识文档，可从右侧创建第一篇。</div>}
            {documents.map((document) => (
              <article className={editingDocumentId === document.id ? 'selected' : ''} key={document.id}>
                <button className="rag-document-main" onClick={() => beginDocument(document)}><strong>{document.title}</strong><span>{document.id}</span><p>{document.content.slice(0, 130)}{document.content.length > 130 ? '…' : ''}</p><div><em>{document.category}</em><em>{document.version}</em></div></button>
                <button className="rag-delete" title="删除文档" onClick={() => removeDocument(document)} disabled={busyKey === `delete:${document.id}`}><Trash2 size={15} /></button>
              </article>
            ))}
          </div>

          <form className="rag-document-editor" onSubmit={saveDocument}>
            <div className="resource-section-heading"><div><h3>{editingDocumentId ? '编辑文档' : '新建文档'}</h3><p>保存后自动切分并更新向量索引。</p></div>{editingDocumentId && <button type="button" className="btn btn-secondary" onClick={() => beginDocument()}><Plus size={14} /> 新建</button>}</div>
            <div className="rag-form-grid"><label><span>文档 ID</span><input value={documentDraft.id} disabled={Boolean(editingDocumentId)} onChange={(event) => setDocumentDraft({ ...documentDraft, id: event.target.value })} pattern="[a-zA-Z0-9][a-zA-Z0-9._-]*" required /></label><label><span>标题</span><input value={documentDraft.title} onChange={(event) => setDocumentDraft({ ...documentDraft, title: event.target.value })} required /></label><label><span>分类</span><input value={documentDraft.category} onChange={(event) => setDocumentDraft({ ...documentDraft, category: event.target.value })} required /></label><label><span>版本</span><input value={documentDraft.version} onChange={(event) => setDocumentDraft({ ...documentDraft, version: event.target.value })} required /></label></div>
            <label><span>文档内容</span><textarea rows="14" value={documentDraft.content} onChange={(event) => setDocumentDraft({ ...documentDraft, content: event.target.value })} required /></label>
            <label><span>Metadata JSON</span><textarea rows="5" value={documentDraft.metadata} onChange={(event) => setDocumentDraft({ ...documentDraft, metadata: event.target.value })} /></label>
            <div className="resource-form-actions"><button className="btn btn-primary" disabled={busyKey === 'document'}><Save size={15} /> 保存并更新索引</button></div>
          </form>
        </div>
      )}
    </section>
  );
}
