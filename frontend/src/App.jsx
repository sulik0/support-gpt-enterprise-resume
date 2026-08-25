import React, { useEffect, useMemo, useState } from 'react';
import { AUTH_EXPIRED_EVENT, fetchTickets, createTicket, login, register, logout } from './api/client';
import MetricsGrid from './components/MetricsGrid';
import TicketList from './components/TicketList';
import TicketDetails from './components/TicketDetails';
import ObservabilityPage from './components/ObservabilityPage';
import { translateRole } from './i18n';
import {
  Activity,
  BookOpen,
  Headphones,
  LayoutDashboard,
  LogOut,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userRole, setUserRole] = useState('');
  const [username, setUsername] = useState('');
  const [loginUser, setLoginUser] = useState('');
  const [loginPass, setLoginPass] = useState('');
  const [activeView, setActiveView] = useState('workspace');
  const [authNotice, setAuthNotice] = useState('');

  // 页面主体状态
  const [tickets, setTickets] = useState([]);
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [kbVersion, setKbVersion] = useState('v1');
  const [showModal, setShowModal] = useState(false);
  const [newCustId, setNewCustId] = useState('cust_101');
  const [newSubject, setNewSubject] = useState('');
  const [newDesc, setNewDesc] = useState('');

  // 性能观测指标
  const [sysMetrics, setSysMetrics] = useState({
    cost: 0.0035,
    tokens: 1450,
    latency: 1.25,
    violations: 0
  });

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      setIsAuthenticated(true);
      setUserRole(localStorage.getItem('role') || 'agent');
      setUsername(localStorage.getItem('username') || '');
      loadTickets();
    }
  }, [isAuthenticated]);

  useEffect(() => {
    function handleAuthExpired() {
      setIsAuthenticated(false);
      setUserRole('');
      setUsername('');
      setTickets([]);
      setSelectedTicket(null);
      setActiveView('workspace');
      setAuthNotice('登录已过期，请重新登录。');
    }
    window.addEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired);
  }, []);

  async function loadTickets() {
    try {
      const list = await fetchTickets();
      setTickets(list);
    } catch (err) {
      console.error('加载工单失败：', err);
    }
  }

  async function handleLogin(e) {
    e.preventDefault();
    try {
      await login(loginUser, loginPass);
      setAuthNotice('');
      setIsAuthenticated(true);
    } catch (err) {
      alert('登录失败，请检查用户名和密码。');
    }
  }

  async function handleRegister(role) {
    if (!loginUser || !loginPass) {
      alert('请先填写用户名和密码。');
      return;
    }
    try {
      await register(loginUser, loginPass, role);
      alert(`用户 ${loginUser} 已注册为${translateRole(role)}，请登录。`);
    } catch (err) {
      alert(err.message);
    }
  }

  function handleLogout() {
    logout();
    setIsAuthenticated(false);
    setTickets([]);
    setSelectedTicket(null);
    setActiveView('workspace');
  }

  async function handleCreateTicket(e) {
    e.preventDefault();
    try {
      await createTicket(newCustId, newSubject, newDesc);
      setShowModal(false);
      setNewSubject('');
      setNewDesc('');
      loadTickets();
      alert('工单提交成功！');
    } catch (err) {
      alert(err.message);
    }
  }

  // 工单处理完成后更新当前页面的演示指标。
  function handleActionComplete() {
    loadTickets();
    setSelectedTicket(null);
    setSysMetrics(prev => ({
      ...prev,
      cost: prev.cost + 0.0012,
      tokens: prev.tokens + 450,
      latency: (prev.latency + 0.85) / 2
    }));
  }

  const workspaceStats = useMemo(() => {
    const activeStatuses = new Set(['open', 'in_progress', 'pending', 'pending_approval']);
    return {
      total: tickets.length,
      active: tickets.filter((ticket) => activeStatuses.has(ticket.status || 'open')).length,
      attention: tickets.filter((ticket) => ['urgent', 'high'].includes(ticket.priority)).length,
    };
  }, [tickets]);

  if (!isAuthenticated) {
    return (
      <div style={{ display: 'flex', minHeight: '100vh', alignItems: 'center', justifyContent: 'center' }}>
        <div className="glass-card" style={{ width: '400px', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div style={{ textAlign: 'center' }}>
            <h1 style={{ margin: 0, fontFamily: 'Outfit, sans-serif', fontSize: '1.6rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}>
              <Sparkles color="#8b5cf6" size={24} /> SupportGPT
            </h1>
            <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.8rem', color: '#9ca3af' }}>企业级 AI 客服平台</p>
          </div>

          {authNotice && (
            <div className="auth-notice" role="alert">{authNotice}</div>
          )}

          <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              <label style={{ fontSize: '0.8rem', fontWeight: '500', color: '#9ca3af' }}>用户名</label>
              <input
                type="text"
                value={loginUser}
                onChange={(e) => setLoginUser(e.target.value)}
                style={{ padding: '0.6rem', background: '#0f172a', border: '1px solid var(--border-color)', borderRadius: '6px', color: '#fff' }}
                required
              />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              <label style={{ fontSize: '0.8rem', fontWeight: '500', color: '#9ca3af' }}>密码</label>
              <input
                type="password"
                value={loginPass}
                onChange={(e) => setLoginPass(e.target.value)}
                style={{ padding: '0.6rem', background: '#0f172a', border: '1px solid var(--border-color)', borderRadius: '6px', color: '#fff' }}
                required
              />
            </div>

            <button type="submit" className="btn btn-primary" style={{ marginTop: '0.5rem' }}>
              登录
            </button>
          </form>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', borderTop: '1px solid var(--border-color)', paddingTop: '1rem' }}>
            <div style={{ fontSize: '0.75rem', color: '#6b7280', textAlign: 'center' }}>首次使用可注册演示账号</div>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button onClick={() => handleRegister('agent')} className="btn btn-secondary" style={{ flex: 1, padding: '0.4rem', fontSize: '0.75rem' }}>
                注册客服
              </button>
              <button onClick={() => handleRegister('admin')} className="btn btn-secondary" style={{ flex: 1, padding: '0.4rem', fontSize: '0.75rem' }}>
                注册管理员
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const canViewObservability = ['manager', 'admin'].includes(userRole);
  const isObservabilityView = activeView === 'observability' && canViewObservability;

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="sidebar-brand">
          <span className="brand-mark"><Sparkles size={20} /></span>
          <div><strong>SupportGPT</strong><small>企业客服智能体</small></div>
        </div>

        <nav className="sidebar-nav" aria-label="主要功能">
          <span className="sidebar-nav-label">工作空间</span>
          <button className={activeView === 'workspace' ? 'active' : ''} onClick={() => setActiveView('workspace')}>
            <LayoutDashboard size={18} /><span>工单工作台</span><em>{workspaceStats.active}</em>
          </button>
          {canViewObservability && (
            <button className={activeView === 'observability' ? 'active' : ''} onClick={() => setActiveView('observability')}>
              <Activity size={18} /><span>Agent 可观测性</span>
            </button>
          )}
        </nav>

        <div className="sidebar-runtime">
          <div className="runtime-title"><ShieldCheck size={15} /> Agent 服务正常</div>
          <p>工作流、知识检索和安全护栏均已就绪。</p>
        </div>

        <div className="sidebar-account">
          <span className="account-avatar">{(username || '客').slice(0, 1).toUpperCase()}</span>
          <div><strong>{username || '当前用户'}</strong><small>{translateRole(userRole)}</small></div>
          <button onClick={handleLogout} title="退出登录" aria-label="退出登录"><LogOut size={17} /></button>
        </div>
      </aside>

      <div className="app-main">
        <header className="app-topbar">
          <div>
            <span className="topbar-eyebrow">{isObservabilityView ? '系统运行洞察' : '客服运营中心'}</span>
            <h1>{isObservabilityView ? 'Agent 可观测性' : '工单工作台'}</h1>
          </div>
          {!isObservabilityView && (
            <div className="topbar-actions">
              <label className="kb-selector">
                <BookOpen size={15} />
                <span>知识库</span>
                <select value={kbVersion} onChange={(e) => setKbVersion(e.target.value)}>
                  <option value="v1">v1 · 当前政策</option>
                  <option value="v2">v2 · 60 天政策</option>
                  <option value="v3">v3 · 草稿</option>
                </select>
              </label>
              <button className="icon-button" onClick={loadTickets} title="刷新工单" aria-label="刷新工单">
                <RefreshCw size={17} />
              </button>
            </div>
          )}
        </header>

        <div className="app-content">
          {isObservabilityView ? (
            <ObservabilityPage />
          ) : (
            <section className="workspace-page">
              <div className="workspace-hero">
                <div>
                  <span className="workspace-eyebrow"><Headphones size={14} /> 今日客服队列</span>
                  <h2>{workspaceStats.active > 0 ? `还有 ${workspaceStats.active} 张工单等待处理` : '当前工单已全部处理'}</h2>
                  <p>选择左侧工单后，Agent 会自动补全客户上下文、检索政策并生成可审核回复。</p>
                </div>
                <div className="workspace-hero-actions">
                  {workspaceStats.attention > 0 && <span className="attention-pill">{workspaceStats.attention} 张高优工单</span>}
                  <button className="btn btn-primary" onClick={() => setShowModal(true)}><Plus size={17} /> 新建工单</button>
                </div>
              </div>

              <MetricsGrid metrics={sysMetrics} />

              <main className="grid-dashboard">
                <TicketList
                  tickets={tickets}
                  selectedId={selectedTicket?.id}
                  onSelect={(ticket) => setSelectedTicket(ticket)}
                  onNewTicket={() => setShowModal(true)}
                />
                <TicketDetails
                  ticket={selectedTicket ? { ...selectedTicket, kb_version: kbVersion } : null}
                  onActionComplete={handleActionComplete}
                />
              </main>
            </section>
          )}
        </div>
      </div>

      {showModal && (
        <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && setShowModal(false)}>
          <div className="modal-card" role="dialog" aria-modal="true" aria-labelledby="new-ticket-title">
            <div className="modal-heading">
              <div><span>创建新任务</span><h2 id="new-ticket-title">提交客户工单</h2></div>
              <button className="icon-button" type="button" onClick={() => setShowModal(false)} aria-label="关闭">×</button>
            </div>
            <form onSubmit={handleCreateTicket} className="ticket-form">
              <label><span>客户</span><select value={newCustId} onChange={(e) => setNewCustId(e.target.value)}>
                <option value="cust_101">cust_101（简·多伊 · VIP 客户）</option>
                <option value="cust_102">cust_102（约翰·史密斯 · 标准客户）</option>
                <option value="cust_103">cust_103（艾克米公司 · 企业客户）</option>
              </select></label>
              <label><span>工单主题</span><input type="text" value={newSubject} onChange={(e) => setNewSubject(e.target.value)} placeholder="例如：订单退款进度咨询" required /></label>
              <label><span>客户问题</span><textarea value={newDesc} onChange={(e) => setNewDesc(e.target.value)} placeholder="请完整描述客户诉求、订单信息和期望结果……" required /></label>
              <div className="modal-actions">
                <button type="button" onClick={() => setShowModal(false)} className="btn btn-secondary">取消</button>
                <button type="submit" className="btn btn-primary"><Plus size={16} /> 创建并进入队列</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
