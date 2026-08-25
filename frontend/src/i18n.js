const PRIORITY_LABELS = {
  urgent: '紧急',
  high: '高',
  medium: '中',
  low: '低',
};

const SENTIMENT_LABELS = {
  positive: '正向',
  neutral: '中性',
  negative: '负向',
};

const STATUS_LABELS = {
  open: '处理中',
  in_progress: '处理中',
  pending: '待处理',
  pending_approval: '待审批',
  approved: '已批准',
  modified: '已修改',
  rejected: '已拒绝',
  closed: '已关闭',
  resolved: '已解决',
  shipped: '已发货',
  delivered: '已送达',
  cancelled: '已取消',
};

const ROLE_LABELS = {
  agent: '客服',
  manager: '主管',
  admin: '管理员',
};

const TIER_LABELS = {
  VIP: 'VIP 客户',
  Standard: '标准客户',
  Enterprise: '企业客户',
};

const SUBJECT_LABELS = {
  'Active Chat Conversation': '在线客服对话',
};

const ORDER_ITEM_LABELS = {
  'Enterprise SaaS User Pack (10)': '企业版 SaaS 用户包（10 个账号）',
  'Developer API Key Pack': '开发者 API Key 套餐',
  'Dedicated AWS Gateway Cluster': 'AWS 专属网关集群',
  'Enterprise Premium support SLA addon': '企业高级支持 SLA 附加服务',
};

// 将后端枚举值转换为中文，未知值保持原样，便于兼容后续扩展。
function translateValue(labels, value, fallback = '') {
  if (!value) return fallback;
  return labels[value] || value;
}

export const translatePriority = (value) => translateValue(PRIORITY_LABELS, value, '中');
export const translateSentiment = (value) => translateValue(SENTIMENT_LABELS, value, '中性');
export const translateStatus = (value) => translateValue(STATUS_LABELS, value, '未知');
export const translateRole = (value) => translateValue(ROLE_LABELS, value, '客服');
export const translateTier = (value) => translateValue(TIER_LABELS, value, value);
export const translateSubject = (value) => translateValue(SUBJECT_LABELS, value, value);
export const translateOrderItem = (value) => translateValue(ORDER_ITEM_LABELS, value, value);

export function translateEscalationReason(value) {
  if (!value) return '';
  if (value === 'Security guardrails violation block.' || value === 'Security violation block') {
    return '安全护栏检测到高风险请求。';
  }
  if (value === 'Ticket designated as Urgent priority.') return '工单被判定为紧急优先级。';
  if (value === 'Negative customer sentiment combined with high priority.') {
    return '客户情绪负向且工单优先级较高。';
  }
  if (value.startsWith('AI quality assurance score')) {
    const score = value.match(/\(([^)]+)\)/)?.[1];
    return `AI 质量评分${score ? `（${score}）` : ''}低于阈值或检测到幻觉。`;
  }
  return value;
}
