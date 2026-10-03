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
import { translateRisk, translateRole } from '../i18n';

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
      setNotice({ type: 'error', text: error.message || '工具、提示词或知识文档加载失败。' });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadResources(); }, []);

  async function toggleTool(tool) {
    const enabled = !tool.enabled;
    let reason = '管理员恢复启用';
    if (!enabled) {
      reason = window.prompt(`请输入停用 ${tool.name} 的原因：`, '临时维护')?.trim();
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
      setNotice({ type: 'success', text: `已保存提示词候选版本 ${created.version}。正式发布前，还需通过 EvalOps 评测和发布检查。` });
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
      setNotice({ type: 'error', text: '文档附加信息必须使用有效的 JSON 格式。' });
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
    if (!window.confirm(`确认删除「${document.title}」及其全部检索索引片段？`)) return;
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
      setNotice({ type: 'success', text: `已根据数据库中保存的原文，为 ${result.indexed_documents} 篇文档重建向量索引。` });
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
          <h2>管理工具、提示词和知识文档</h2>
          <p>管理员可以启停工具、创建提示词候选版本，以及编辑知识文档。工具权限和提示词发布规则仍按现有配置执行。</p>
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
          <Wrench size={16} /> 业务工具 <span>{tools.length}</span>
        </button>
        <button className={activeTab === 'prompts' ? 'active' : ''} onClick={() => setActiveTab('prompts')}>
          <FileCode2 size={16} /> 提示词版本 <span>{prompts?.bundles?.length || 0}</span>
        </button>
        <button className={activeTab === 'rag' ? 'active' : ''} onClick={() => setActiveTab('rag')}>
          <BookOpen size={16} /> 知识文档 <span>{documents.length}</span>
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
                    {tool.enabled ? '已启用' : '已停用'}
                  </span>
                </div>
                <div className="tool-admin-tags">
                  <span>{tool.operation_type === 'write' ? '修改业务数据' : '只查询数据'}</span>
                  <span>{translateRisk(tool.risk_level)}风险</span><span>{translateRole(tool.min_role)}及以上</span><span>{tool.version}</span>
                </div>
                {tool.disabled_reason && <p className="tool-disabled-reason">停用原因：{tool.disabled_reason}</p>}
                <details><summary>查看参数 Schema（结构）和适用的问题分类</summary><pre>{JSON.stringify({ input: tool.input_schema, output: tool.output_schema, allowed_intents: tool.allowed_intents }, null, 2)}</pre></details>
                <button
                  className={`btn ${tool.enabled ? 'btn-danger-outline' : 'btn-secondary'}`}
                  disabled={busyKey === tool.name}
                  onClick={() => toggleTool(tool)}
                >
                  <Settings2 size={14} /> {tool.enabled ? '停用工具' : '恢复启用'}
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
              <div><h3>Prompt Bundle（提示词版本包）</h3><p>每个版本包按内容 Hash（摘要）保存。保存后不能覆盖原版本，需要创建新版本。</p></div>
              <button className="btn btn-primary" onClick={beginPromptCandidate}><Plus size={15} /> 从当前生产版创建候选版本</button>
            </div>
            <div className="prompt-environments">
              {['production', 'staging'].map((environment) => {
                const bundle = prompts.effective[environment];
                return <div key={environment}><span>{environment === 'production' ? '生产环境' : '预发布环境'}</span><strong>{bundle.version}</strong><code>{shortHash(bundle.bundle_id)}</code></div>;
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
            <ShieldCheck size={20} /><h3>怎样发布新版本？</h3>
            <p>这个页面只能保存候选版本，不能直接切换生产环境的提示词。发布前，需要通过 EvalOps，在同一测试集上比较当前版本和候选版本，并检查是否符合发布要求。</p>
          </aside>

          {promptDraft && (
            <form className="prompt-editor" onSubmit={savePrompt}>
              <div className="resource-section-heading"><div><h3>新建提示词候选版本</h3><p>保存时，后端会检查模板中的占位符是否符合 PromptOps 要求。</p></div><button type="button" className="icon-button" onClick={() => setPromptDraft(null)}>×</button></div>
              <label><span>版本标签</span><input value={promptDraft.version} onChange={(event) => setPromptDraft({ ...promptDraft, version: event.target.value })} required /></label>
              {['analyzer', 'resolver', 'qa'].map((node) => (
                <fieldset key={node}><legend>{{ analyzer: 'Analyzer（问题分析）', resolver: 'Resolver（回复生成）', qa: 'QA（回复检查）' }[node]}</legend>
                  {['system', 'user'].map((role) => <label key={role}><span>{role === 'system' ? 'System（系统提示词）' : 'User（用户输入模板）'}</span><textarea rows={role === 'system' ? 5 : 3} value={promptDraft.templates[node][role]} onChange={(event) => updatePromptTemplate(node, role, event.target.value)} required /></label>)}
                </fieldset>
              ))}
              <div className="resource-form-actions"><button type="button" className="btn btn-secondary" onClick={() => setPromptDraft(null)}>取消</button><button className="btn btn-primary" disabled={busyKey === 'prompt'}><Save size={15} /> 保存候选版本</button></div>
            </form>
          )}
        </div>
      )}

      {!loading && activeTab === 'rag' && (
        <div className="resource-section rag-admin-layout">
          <div className="rag-document-list">
            <div className="resource-section-heading"><div><h3>知识文档</h3><p>数据库保存文档原文，ChromaDB 保存用于检索的向量索引。</p></div><button className="btn btn-secondary" onClick={reindexDocuments} disabled={busyKey === 'reindex'}><RefreshCw size={14} className={busyKey === 'reindex' ? 'spin' : ''} /> 重建全部文档索引</button></div>
            {documents.length === 0 && <div className="resource-empty">还没有知识文档，可以在新建表单中添加第一篇。</div>}
            {documents.map((document) => (
              <article className={editingDocumentId === document.id ? 'selected' : ''} key={document.id}>
                <button className="rag-document-main" onClick={() => beginDocument(document)}><strong>{document.title}</strong><span>{document.id}</span><p>{document.content.slice(0, 130)}{document.content.length > 130 ? '…' : ''}</p><div><em>{document.category}</em><em>{document.version}</em></div></button>
                <button className="rag-delete" title="删除文档" onClick={() => removeDocument(document)} disabled={busyKey === `delete:${document.id}`}><Trash2 size={15} /></button>
              </article>
            ))}
          </div>

          <form className="rag-document-editor" onSubmit={saveDocument}>
            <div className="resource-section-heading"><div><h3>{editingDocumentId ? '编辑文档' : '新建文档'}</h3><p>保存后，系统会将文档分成片段，并更新检索索引。</p></div>{editingDocumentId && <button type="button" className="btn btn-secondary" onClick={() => beginDocument()}><Plus size={14} /> 新建</button>}</div>
            <div className="rag-form-grid"><label><span>文档 ID</span><input value={documentDraft.id} disabled={Boolean(editingDocumentId)} onChange={(event) => setDocumentDraft({ ...documentDraft, id: event.target.value })} pattern="[a-zA-Z0-9][a-zA-Z0-9._-]*" required /></label><label><span>标题</span><input value={documentDraft.title} onChange={(event) => setDocumentDraft({ ...documentDraft, title: event.target.value })} required /></label><label><span>分类</span><input value={documentDraft.category} onChange={(event) => setDocumentDraft({ ...documentDraft, category: event.target.value })} required /></label><label><span>版本</span><input value={documentDraft.version} onChange={(event) => setDocumentDraft({ ...documentDraft, version: event.target.value })} required /></label></div>
            <label><span>文档内容</span><textarea rows="14" value={documentDraft.content} onChange={(event) => setDocumentDraft({ ...documentDraft, content: event.target.value })} required /></label>
            <label><span>文档附加信息（JSON）</span><textarea rows="5" value={documentDraft.metadata} onChange={(event) => setDocumentDraft({ ...documentDraft, metadata: event.target.value })} /></label>
            <div className="resource-form-actions"><button className="btn btn-primary" disabled={busyKey === 'document'}><Save size={15} /> 保存并更新索引</button></div>
          </form>
        </div>
      )}
    </section>
  );
}
