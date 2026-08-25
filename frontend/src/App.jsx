import React, { useState, useEffect } from 'react';
import { fetchTickets, createTicket, login, register, logout } from './api/client';
import MetricsGrid from './components/MetricsGrid';
import TicketList from './components/TicketList';
import TicketDetails from './components/TicketDetails';
import ObservabilityPage from './components/ObservabilityPage';
import { translateRole } from './i18n';
import { Activity, Headphones, LogOut, Sparkles } from 'lucide-react';

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userRole, setUserRole] = useState('');
  const [username, setUsername] = useState('');
  const [loginUser, setLoginUser] = useState('');
  const [loginPass, setLoginPass] = useState('');
  const [activeView, setActiveView] = useState('workspace');

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

  return (
    <div className="app-container">
      {/* 页面头部 */}
      <header className="app-header">
        <div className="app-title-group">
          <h1>SupportGPT 企业版</h1>
          <p>多智能体 AI 客服工作台</p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
          {/* 知识库版本 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', color: '#9ca3af' }}>知识库版本：</span>
            <select
              value={kbVersion}
              onChange={(e) => setKbVersion(e.target.value)}
              style={{
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid var(--border-color)',
                borderRadius: '6px',
                color: '#fff',
                padding: '0.4rem',
                fontSize: '0.8rem'
              }}
            >
              <option value="v1">v1 - 当前生效政策</option>
              <option value="v2">v2 - 延长至 60 天政策</option>
              <option value="v3">v3 - 草稿版本</option>
            </select>
          </div>

          {/* 用户信息与退出 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', fontSize: '0.85rem' }}>
            <span style={{ color: '#8b5cf6', fontWeight: 'bold', textTransform: 'capitalize' }}>
              {username}（{translateRole(userRole)}）
            </span>
            <button onClick={handleLogout} className="btn btn-secondary" style={{ padding: '0.4rem', borderRadius: '50%' }} title="退出登录" aria-label="退出登录">
              <LogOut size={14} />
            </button>
          </div>
        </div>
      </header>

      <nav className="view-tabs" aria-label="主要功能">
        <button className={activeView === 'workspace' ? 'active' : ''} onClick={() => setActiveView('workspace')}>
          <Headphones size={16} /> 工单工作台
        </button>
        {['manager', 'admin'].includes(userRole) && (
          <button className={activeView === 'observability' ? 'active' : ''} onClick={() => setActiveView('observability')}>
            <Activity size={16} /> Agent 可观测性
          </button>
        )}
      </nav>

      {activeView === 'observability' && ['manager', 'admin'].includes(userRole) ? (
        <ObservabilityPage />
      ) : (
        <>
          {/* 指标概览 */}
          <MetricsGrid metrics={sysMetrics} />

          {/* 工单列表与详情 */}
          <main className="grid-dashboard">
            <TicketList
              tickets={tickets}
              selectedId={selectedTicket?.id}
              onSelect={(t) => setSelectedTicket(t)}
              onNewTicket={() => setShowModal(true)}
            />

            <TicketDetails
              ticket={selectedTicket ? { ...selectedTicket, kb_version: kbVersion } : null}
              onActionComplete={handleActionComplete}
            />
          </main>
        </>
      )}

      {/* 新建工单弹窗 */}
      {showModal && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.7)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          backdropFilter: 'blur(4px)'
        }}>
          <div className="glass-card" style={{ width: '450px', display: 'flex', flexDirection: 'column', gap: '1.2rem' }}>
            <h2 style={{ margin: 0, fontSize: '1.2rem', fontFamily: 'Outfit, sans-serif' }}>提交客户工单</h2>
            
            <form onSubmit={handleCreateTicket} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                <label style={{ fontSize: '0.8rem', color: '#9ca3af' }}>客户编号</label>
                <select
                  value={newCustId}
                  onChange={(e) => setNewCustId(e.target.value)}
                  style={{ padding: '0.6rem', background: '#0f172a', border: '1px solid var(--border-color)', borderRadius: '6px', color: '#fff' }}
                >
                  <option value="cust_101">cust_101（简·多伊 - VIP 客户）</option>
                  <option value="cust_102">cust_102（约翰·史密斯 - 标准客户）</option>
                  <option value="cust_103">cust_103（艾克米公司 - 企业客户）</option>
                </select>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                <label style={{ fontSize: '0.8rem', color: '#9ca3af' }}>工单主题</label>
                <input
                  type="text"
                  value={newSubject}
                  onChange={(e) => setNewSubject(e.target.value)}
                  style={{ padding: '0.6rem', background: '#0f172a', border: '1px solid var(--border-color)', borderRadius: '6px', color: '#fff' }}
                  required
                />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                <label style={{ fontSize: '0.8rem', color: '#9ca3af' }}>问题详情</label>
                <textarea
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  style={{ padding: '0.6rem', background: '#0f172a', border: '1px solid var(--border-color)', borderRadius: '6px', color: '#fff', height: '100px', resize: 'vertical' }}
                  required
                />
              </div>

              <div style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem' }}>
                <button type="submit" className="btn btn-primary" style={{ flex: 1 }}>
                  提交工单
                </button>
                <button type="button" onClick={() => setShowModal(false)} className="btn btn-secondary" style={{ flex: 1 }}>
                  取消
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
