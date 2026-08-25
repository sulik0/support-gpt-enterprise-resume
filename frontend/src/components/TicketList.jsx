import React, { useMemo, useState } from 'react';
import { AlertCircle, ChevronRight, Inbox, MessageSquare, Plus, Search } from 'lucide-react';
import { translatePriority, translateSentiment, translateStatus, translateSubject } from '../i18n';

const ACTIVE_STATUSES = new Set(['open', 'in_progress', 'pending', 'pending_approval']);

export default function TicketList({ tickets = [], selectedId, onSelect, onNewTicket }) {
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('active');

  // 搜索与状态筛选只作用于当前已加载的工单队列。
  const filteredTickets = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return tickets.filter((ticket) => {
      const status = ticket.status || 'open';
      const matchesStatus = statusFilter === 'all'
        || (statusFilter === 'active' && ACTIVE_STATUSES.has(status))
        || status === statusFilter;
      const searchable = `${ticket.id} ${ticket.customer_id} ${ticket.subject} ${ticket.description}`.toLowerCase();
      return matchesStatus && (!normalizedQuery || searchable.includes(normalizedQuery));
    });
  }, [query, statusFilter, tickets]);

  return (
    <aside className="ticket-queue">
      <div className="queue-heading">
        <div>
          <span className="section-label">处理队列</span>
          <h2>客户工单 <em>{tickets.length}</em></h2>
        </div>
        <button onClick={onNewTicket} className="queue-add-button" title="新建工单" aria-label="新建工单">
          <Plus size={18} />
        </button>
      </div>

      <div className="queue-filters">
        <label className="queue-search">
          <Search size={15} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索客户、主题或编号" />
        </label>
        <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} aria-label="筛选工单状态">
          <option value="active">待处理</option>
          <option value="all">全部状态</option>
          <option value="pending_approval">待审批</option>
          <option value="resolved">已解决</option>
          <option value="closed">已关闭</option>
        </select>
      </div>

      <div className="ticket-list" aria-live="polite">
        {filteredTickets.length === 0 ? (
          <div className="queue-empty">
            <Inbox size={28} />
            <strong>{tickets.length === 0 ? '暂无工单' : '没有匹配的工单'}</strong>
            <span>{tickets.length === 0 ? '新建工单后将出现在这里' : '请调整搜索词或状态筛选'}</span>
          </div>
        ) : filteredTickets.map((ticket) => {
          const isSelected = ticket.id === selectedId;
          const priority = ticket.priority || 'medium';
          const status = ticket.status || 'open';
          return (
            <button
              type="button"
              key={ticket.id}
              className={`ticket-row ${isSelected ? 'selected' : ''}`}
              onClick={() => onSelect(ticket)}
              aria-pressed={isSelected}
            >
              <span className={`priority-rail priority-${priority}`} />
              <span className="ticket-row-body">
                <span className="ticket-row-meta">
                  <span>#{ticket.id}</span>
                  <span>{ticket.customer_id}</span>
                  <span className={`status-dot status-${status}`} />
                  <span>{translateStatus(status)}</span>
                </span>
                <strong>{translateSubject(ticket.subject)}</strong>
                <span className="ticket-row-preview">{ticket.description || '未填写问题描述'}</span>
                <span className="ticket-row-footer">
                  <span className={`mini-priority priority-text-${priority}`}>
                    {['urgent', 'high'].includes(priority) && <AlertCircle size={12} />}
                    {translatePriority(priority)}优先级
                  </span>
                  <span><MessageSquare size={12} /> {translateSentiment(ticket.sentiment)}</span>
                </span>
              </span>
              <ChevronRight className="ticket-row-arrow" size={17} />
            </button>
          );
        })}
      </div>

      <div className="queue-footer">当前显示 {filteredTickets.length} / {tickets.length} 张工单</div>
    </aside>
  );
}
