import React from 'react';
import { DollarSign, Cpu, Clock, ShieldAlert } from 'lucide-react';

export default function MetricsGrid({ metrics = {} }) {
  const items = [
    {
      title: '预估接口成本',
      value: `$${(metrics.cost || 0.0).toFixed(4)}`,
      desc: '根据令牌用量估算',
      icon: DollarSign,
      color: '#10b981',
    },
    {
      title: '大模型令牌消耗',
      value: (metrics.tokens || 0).toLocaleString(),
      desc: '输入与生成令牌合计',
      icon: Cpu,
      color: '#3b82f6',
    },
    {
      title: '智能体平均延迟',
      value: `${(metrics.latency || 0).toFixed(2)}s`,
      desc: 'LangGraph 执行链路耗时',
      icon: Clock,
      color: '#eab308',
    },
    {
      title: '安全护栏拦截次数',
      value: metrics.violations || 0,
      desc: '个人敏感信息、提示词注入与越狱攻击',
      icon: ShieldAlert,
      color: '#ef4444',
    },
  ];

  return (
    <div className="metrics-panel">
      {items.map((item, idx) => (
        <div key={idx} className="glass-card" style={{ borderLeft: `4px solid ${item.color}` }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.85rem', color: '#9ca3af', fontWeight: '500' }}>{item.title}</span>
            <item.icon size={18} color={item.color} />
          </div>
          <div style={{ fontSize: '1.5rem', fontWeight: '700', fontFamily: 'Outfit, sans-serif', marginBottom: '0.2rem' }}>
            {item.value}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>{item.desc}</div>
        </div>
      ))}
    </div>
  );
}
