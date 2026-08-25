import React from 'react';
import { Clock3, Coins, Cpu, ShieldCheck } from 'lucide-react';

export default function MetricsGrid({ metrics = {} }) {
  const items = [
    { label: '本次预估成本', value: `$${(metrics.cost || 0).toFixed(4)}`, hint: '按令牌用量估算', icon: Coins, tone: 'green' },
    { label: '大模型令牌', value: (metrics.tokens || 0).toLocaleString(), hint: '输入与输出合计', icon: Cpu, tone: 'blue' },
    { label: 'Agent 平均响应', value: `${(metrics.latency || 0).toFixed(2)}s`, hint: '完整工作流耗时', icon: Clock3, tone: 'amber' },
    { label: '安全护栏', value: metrics.violations ? `${metrics.violations} 次拦截` : '运行正常', hint: '注入、越权与敏感信息', icon: ShieldCheck, tone: metrics.violations ? 'red' : 'purple' },
  ];

  return (
    <div className="metrics-strip" aria-label="Agent 运行概览">
      {items.map((item) => (
        <div className="metric-item" key={item.label}>
          <span className={`metric-icon tone-${item.tone}`}><item.icon size={17} /></span>
          <div><span>{item.label}</span><strong>{item.value}</strong><small>{item.hint}</small></div>
        </div>
      ))}
    </div>
  );
}
