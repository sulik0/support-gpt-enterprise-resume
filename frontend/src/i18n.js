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
  const reasonLabels = {
    security_threat_detected: '安全检测发现可疑提示词注入或越权指令。',
    semantic_safety_unsafe: '语义安全模型将请求判定为不安全。',
    semantic_safety_controversial: '语义安全模型识别到争议性内容，需要人工确认。',
    semantic_guard_degraded: '语义安全检测服务降级，无法完成自动安全判定。',
    untrusted_context_guard_unavailable: '外部知识或工具结果未能完成可信检查。',
    dependency_partially_degraded: '部分依赖服务降级，自动处理结果需要复核。',
    dependency_requires_human: '外部依赖异常，系统已切换为人工处理。',
    dependency_failed: '关键依赖调用失败，无法安全完成自动回复。',
    urgent_priority: '工单被判定为紧急优先级。',
    high_priority: '工单优先级较高，需要人工关注。',
    negative_high_priority: '客户情绪负向且工单优先级较高。',
    high_risk_business_intent: '请求涉及退款争议或订单取消等高风险业务操作。',
    low_analyzer_confidence: '工单意图识别置信度低于安全阈值。',
    medium_analyzer_confidence: '工单意图识别置信度不高。',
    authoritative_answer_unavailable: '系统未找到可支撑回复的权威业务依据。',
    hallucination_detected: 'QA 检测到回复可能包含无依据内容。',
    qa_score_below_threshold: 'AI 回复质量分低于自动发送阈值。',
    workflow_error: 'Agent 执行过程中出现异常，需要人工确认结果。',
    manual_review_policy: '工单命中当前人工审批策略。',
  };
  if (reasonLabels[value]) return reasonLabels[value];
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
  if (value.startsWith('Authoritative business guidance is unavailable')) {
    return reasonLabels.authoritative_answer_unavailable;
  }
  if (value.startsWith('Risk Engine classified ticket as')) {
    const level = value.match(/as ([a-z]+)/i)?.[1]?.toLowerCase();
    const levelLabel = level === 'critical' ? '严重' : level === 'high' ? '高' : level === 'medium' ? '中' : '低';
    return `Risk Engine 将该工单判定为${levelLabel}风险。`;
  }
  if (/^[a-z0-9_.-]+:[a-z0-9_.-]+$/i.test(value)) {
    return `依赖环节 ${value} 发生降级。`;
  }
  return value;
}
