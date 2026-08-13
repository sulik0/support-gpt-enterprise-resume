import React from 'react';
import { translatePriority, translateSentiment, translateStatus, translateSubject } from '../i18n';

export default function TicketList({ tickets = [], selectedId, onSelect, onNewTicket }) {
  return (
    <div className="glass-card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem', height: 'fit-content' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ margin: 0, fontSize: '1.1rem', fontFamily: 'Outfit, sans-serif' }}>客户工单</h2>
        <button onClick={onNewTicket} className="btn btn-primary" style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}>
          + 新建工单
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '550px', overflowY: 'auto', paddingRight: '0.2rem' }}>
        {tickets.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#6b7280', padding: '2rem 0', fontSize: '0.9rem' }}>
            暂无工单记录
          </div>
        ) : (
          tickets.map((t) => {
            const isSelected = t.id === selectedId;
            return (
              <div
                key={t.id}
                onClick={() => onSelect(t)}
                style={{
                  padding: '0.8rem',
                  borderRadius: '8px',
                  background: isSelected ? 'rgba(59, 130, 246, 0.12)' : 'rgba(255, 255, 255, 0.02)',
                  border: isSelected ? '1px solid rgba(59, 130, 246, 0.4)' : '1px solid rgba(255, 255, 255, 0.04)',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                  <span style={{ fontSize: '0.75rem', color: '#6b7280', fontWeight: '600' }}>#{t.id} - {t.customer_id}</span>
                  <span className={`badge badge-priority-${t.priority || 'medium'}`} style={{ fontSize: '0.65rem' }}>
                    {translatePriority(t.priority)}
                  </span>
                </div>
                <div style={{ fontSize: '0.9rem', fontWeight: '600', color: '#f3f4f6', marginBottom: '0.4rem', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                  {translateSubject(t.subject)}
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                  <span className={`badge badge-sentiment-${t.sentiment || 'neutral'}`} style={{ fontSize: '0.65rem' }}>
                    {translateSentiment(t.sentiment)}
                  </span>
                  <span style={{ fontSize: '0.7rem', color: '#9ca3af', textTransform: 'capitalize' }}>
                    {translateStatus(t.status)}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
