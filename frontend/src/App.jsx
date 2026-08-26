import React, { useEffect, useMemo, useState } from 'react';
import { AUTH_EXPIRED_EVENT, fetchReviewQueue, login, register, logout } from './api/client';
import CustomerSupportPage from './components/CustomerSupportPage';
import TicketList from './components/TicketList';
import TicketDetails from './components/TicketDetails';
import ObservabilityPage from './components/ObservabilityPage';
import { translateRole } from './i18n';
import {
  Activity,
  ArrowLeft,
  Headphones,
  LayoutDashboard,
  LogOut,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(() => Boolean(localStorage.getItem('token')));
  const [entryMode, setEntryMode] = useState(() => (
    window.location.hash === '#support' ? 'customer' : localStorage.getItem('token') ? 'staff' : 'customer'
  ));
  const [userRole, setUserRole] = useState(() => localStorage.getItem('role') || '');
  const [username, setUsername] = useState(() => localStorage.getItem('username') || '');
  const [loginUser, setLoginUser] = useState('');
  const [loginPass, setLoginPass] = useState('');
  const [activeView, setActiveView] = useState('workspace');
  const [authNotice, setAuthNotice] = useState('');
  const [tickets, setTickets] = useState([]);
  const [selectedTicket, setSelectedTicket] = useState(null);

  useEffect(() => {
    if (isAuthenticated && entryMode === 'staff') {
      setUserRole(localStorage.getItem('role') || 'agent');
      setUsername(localStorage.getItem('username') || '');
      loadTickets();
    }
  }, [entryMode, isAuthenticated]);

  useEffect(() => {
    function handleAuthExpired() {
      setIsAuthenticated(false);
      setUserRole('');
      setUsername('');
      setTickets([]);
      setSelectedTicket(null);
      setActiveView('workspace');
      setEntryMode('staff');
      setAuthNotice('登录已过期，请重新登录。');
    }
    window.addEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired);
  }, []);

  async function loadTickets() {
    try {
      const list = await fetchReviewQueue();
      setTickets(list);
      setSelectedTicket((current) => list.find((ticket) => ticket.id === current?.id) || null);
      return list;
    } catch (error) {
      console.error('加载待人工处理队列失败：', error);
      return [];
    }
  }

  async function handleLogin(event) {
    event.preventDefault();
    try {
      await login(loginUser, loginPass);
      setAuthNotice('');
      setEntryMode('staff');
      setIsAuthenticated(true);
    } catch (error) {
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
    } catch (error) {
      alert(error.message);
    }
  }

  function handleLogout() {
    logout();
    setIsAuthenticated(false);
    setTickets([]);
    setSelectedTicket(null);
    setActiveView('workspace');
    window.location.hash = 'support';
    setEntryMode('customer');
  }

  // 审批完成后刷新人工队列，已处理工单会自动移出。
  function handleActionComplete() {
    loadTickets();
    setSelectedTicket(null);
  }

  const workspaceStats = useMemo(() => ({
    total: tickets.length,
    active: tickets.filter((ticket) => ticket.status === 'pending_approval').length,
    attention: tickets.filter((ticket) => ['urgent', 'high'].includes(ticket.priority)).length,
  }), [tickets]);

  if (entryMode === 'customer') {
    return <CustomerSupportPage onStaffEntry={() => {
      window.location.hash = 'staff';
      setEntryMode('staff');
    }} />;
  }

  if (!isAuthenticated) {
    return (
      <div className="staff-login-page">
        <div className="glass-card staff-login-card">
          <button type="button" className="back-to-customer" onClick={() => {
            window.location.hash = 'support';
            setEntryMode('customer');
          }}>
            <ArrowLeft size={15} /> 返回用户咨询
          </button>
          <div className="staff-login-heading">
            <h1><Sparkles color="#8b5cf6" size={24} /> SupportGPT</h1>
            <p>客服员工后台</p>
          </div>

          {authNotice && <div className="auth-notice" role="alert">{authNotice}</div>}

          <form onSubmit={handleLogin} className="staff-login-form">
            <label><span>用户名</span><input type="text" value={loginUser} onChange={(event) => setLoginUser(event.target.value)} required /></label>
            <label><span>密码</span><input type="password" value={loginPass} onChange={(event) => setLoginPass(event.target.value)} required /></label>
            <button type="submit" className="btn btn-primary">登录客服后台</button>
          </form>

          <div className="staff-register">
            <span>首次使用可注册演示账号</span>
            <div>
              <button onClick={() => handleRegister('agent')} className="btn btn-secondary">注册客服</button>
              <button onClick={() => handleRegister('admin')} className="btn btn-secondary">注册管理员</button>
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
          <div><strong>SupportGPT</strong><small>客服员工后台</small></div>
        </div>

        <nav className="sidebar-nav" aria-label="主要功能">
          <span className="sidebar-nav-label">工作空间</span>
          <button className={activeView === 'workspace' ? 'active' : ''} onClick={() => setActiveView('workspace')}>
            <LayoutDashboard size={18} /><span>人工处理台</span><em>{workspaceStats.active}</em>
          </button>
          {canViewObservability && (
            <button className={activeView === 'observability' ? 'active' : ''} onClick={() => setActiveView('observability')}>
              <Activity size={18} /><span>Agent 可观测性</span>
            </button>
          )}
        </nav>

        <div className="sidebar-runtime">
          <div className="runtime-title"><ShieldCheck size={15} /> Agent 服务正常</div>
          <p>普通问题自动处理，异常请求进入当前人工队列。</p>
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
            <span className="topbar-eyebrow">{isObservabilityView ? '系统运行洞察' : '人工审核中心'}</span>
            <h1>{isObservabilityView ? 'Agent 可观测性' : '异常与待审批工单'}</h1>
          </div>
          {!isObservabilityView && (
            <button className="icon-button" onClick={loadTickets} title="刷新工单" aria-label="刷新工单">
              <RefreshCw size={17} />
            </button>
          )}
        </header>

        <div className="app-content">
          {isObservabilityView ? (
            <ObservabilityPage />
          ) : (
            <section className="workspace-page">
              <div className="workspace-hero">
                <div>
                  <span className="workspace-eyebrow"><Headphones size={14} /> 人工处理队列</span>
                  <h2>{workspaceStats.active > 0 ? `还有 ${workspaceStats.active} 张异常工单等待确认` : '当前没有需要人工处理的工单'}</h2>
                  <p>普通问题已由 Agent 自动回复；这里仅保留高风险、低置信度、质量异常或需要人工审批的工单。</p>
                </div>
                <div className="workspace-hero-actions">
                  {workspaceStats.attention > 0 && <span className="attention-pill">{workspaceStats.attention} 张高优工单</span>}
                  <span className="review-queue-count"><ShieldCheck size={16} /> {workspaceStats.total} 张待审核</span>
                </div>
              </div>

              <main className="grid-dashboard">
                <TicketList tickets={tickets} selectedId={selectedTicket?.id} onSelect={setSelectedTicket} />
                <TicketDetails ticket={selectedTicket} onActionComplete={handleActionComplete} />
              </main>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
