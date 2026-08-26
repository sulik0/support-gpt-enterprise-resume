const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
export const AUTH_EXPIRED_EVENT = 'supportgpt:auth-expired';

function getHeaders() {
  const token = localStorage.getItem('token');
  const headers = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

async function authenticatedFetch(url, options = {}) {
  const response = await fetch(url, { ...options, headers: options.headers || getHeaders() });
  if (response.status === 401) {
    logout();
    window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT));
  }
  return response;
}

export async function login(username, password) {
  const response = await fetch(`${BASE_URL}/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!response.ok) {
    throw new Error('身份验证失败');
  }
  const data = await response.json();
  localStorage.setItem('token', data.access_token);
  localStorage.setItem('role', data.role);
  localStorage.setItem('username', username);
  return data;
}

export function logout() {
  localStorage.clear();
}

export async function register(username, password, role = 'agent') {
  const response = await fetch(`${BASE_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, role }),
  });
  if (!response.ok) {
    throw new Error('注册失败，用户名可能已存在或输入不符合要求');
  }
  return response.json();
}

export async function fetchTickets() {
  const response = await authenticatedFetch(`${BASE_URL}/tickets`, {
    headers: getHeaders(),
  });
  if (!response.ok) throw new Error('加载工单失败');
  return response.json();
}

export async function fetchReviewQueue() {
  const response = await authenticatedFetch(`${BASE_URL}/staff/review-queue`, {
    headers: getHeaders(),
  });
  if (!response.ok) throw new Error('加载待人工处理队列失败');
  return response.json();
}

export async function submitSupportRequest(customerId, message, kbVersion = 'v1') {
  const response = await fetch(`${BASE_URL}/support/requests`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ customer_id: customerId, message, kb_version: kbVersion }),
  });
  if (!response.ok) throw new Error('问题提交失败，请稍后重试');
  return response.json();
}

export async function createTicket(customerId, subject, description, kbVersion = 'v1') {
  const response = await authenticatedFetch(`${BASE_URL}/tickets`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ customer_id: customerId, subject, description, kb_version: kbVersion }),
  });
  if (!response.ok) throw new Error('创建工单失败');
  return response.json();
}

export async function fetchTicketAgentResult(ticketId) {
  const response = await authenticatedFetch(`${BASE_URL}/tickets/${encodeURIComponent(ticketId)}/agent-result`, {
    headers: getHeaders(),
  });
  if (!response.ok) throw new Error(response.status === 404 ? '该工单暂无已保存的 Agent 处理结果' : '加载 Agent 处理结果失败');
  return response.json();
}

export async function fetchPendingApprovals() {
  const response = await authenticatedFetch(`${BASE_URL}/approvals/pending`, {
    headers: getHeaders(),
  });
  if (!response.ok) throw new Error('加载审批记录失败');
  return response.json();
}

export async function submitApproval(approvalId, status, modifiedResponse) {
  const response = await authenticatedFetch(`${BASE_URL}/approvals/${approvalId}`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ approval_id: approvalId, status, modified_response: modifiedResponse }),
  });
  if (!response.ok) throw new Error('处理审批请求失败');
  return response.json();
}

export async function submitChat(message, customerId, sessionId, kbVersion = 'v1') {
  const response = await authenticatedFetch(`${BASE_URL}/chat`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ message, customer_id: customerId, session_id: sessionId, kb_version: kbVersion }),
  });
  if (!response.ok) throw new Error('智能体对话请求失败');
  return response.json();
}

export async function fetchCustomerContext(customerId) {
  const response = await authenticatedFetch(`${BASE_URL}/customer-context`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ customer_id: customerId }),
  });
  if (!response.ok) throw new Error('加载客户画像失败');
  return response.json();
}

export async function evaluateResponse(query, context, responseText) {
  const response = await authenticatedFetch(`${BASE_URL}/evaluate-response`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ query, context, response: responseText }),
  });
  if (!response.ok) throw new Error('评测请求失败');
  return response.json();
}

export async function fetchAgentRuns(limit = 30, offset = 0) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  const response = await authenticatedFetch(`${BASE_URL}/observability/runs?${params}`, {
    headers: getHeaders(),
  });
  if (!response.ok) throw new Error('加载 Agent 运行记录失败');
  return response.json();
}

export async function fetchAgentRun(agentRunId) {
  const response = await authenticatedFetch(`${BASE_URL}/feedback/runs/${encodeURIComponent(agentRunId)}`, {
    headers: getHeaders(),
  });
  if (!response.ok) throw new Error('加载 Agent 运行详情失败');
  return response.json();
}
