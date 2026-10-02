"""中文演示客户及关联数据，全部虚构，不包含真实个人信息。"""

from datetime import datetime, timedelta, timezone

_now = datetime.now(timezone.utc)

CUSTOMERS = {
    "cust_201": {"customer_id": "cust_201", "name": "张晓雨", "tier": "Standard", "open_tickets_count": 1, "email": "zhang.xiaoyu@example.com"},
    "cust_202": {"customer_id": "cust_202", "name": "李明", "tier": "VIP", "open_tickets_count": 0, "email": "li.ming@example.com"},
    "cust_203": {"customer_id": "cust_203", "name": "星河科技（联系人：陈晨）", "tier": "Enterprise", "open_tickets_count": 1, "email": "chen.chen@example.com"},
}

ORDERS = {
    "cust_201": [{"order_id": "ORD-12001", "status": "shipped", "items": ["智能客服桌面终端"], "total_amount": 699.0, "currency": "CNY", "order_date": _now - timedelta(days=4)}],
    "cust_202": [{"order_id": "ORD-12002", "status": "delivered", "items": ["企业网络网关设备"], "total_amount": 1299.0, "currency": "CNY", "order_date": _now - timedelta(days=90)}],
    "cust_203": [{"order_id": "ORD-12003", "status": "delivered", "items": ["企业 API 服务套餐"], "total_amount": 3999.0, "currency": "CNY", "order_date": _now - timedelta(days=10)}],
}

TICKETS = {
    "cust_201": [{"ticket_id": 1201, "subject": "配送延迟查询", "description": "订单配送进度两天未更新。", "status": "in_progress", "resolution": "已登记承运商核查，尚未确认到达日期。", "created_at": _now - timedelta(days=1)}],
    "cust_202": [{"ticket_id": 1202, "subject": "网关设备安装咨询", "description": "询问网络配置步骤。", "status": "resolved", "resolution": "已提供安装指南，用户确认设备可以联网。", "created_at": _now - timedelta(days=85)}],
    "cust_203": [{"ticket_id": 1203, "subject": "API 请求限流", "description": "调用接口返回 429。", "status": "in_progress", "resolution": "建议遵守 Retry-After 并降低并发，等待客户补充脱敏请求记录。", "created_at": _now - timedelta(days=1)}],
}

SERVICE_RECORDS = {
    "cust_201": {
        "shipments": [{"order_id": "ORD-12001", "status": "in_transit", "carrier": "演示物流", "tracking_id": "DEMO-CN-12001", "exception": "delivery_delayed", "next_step": "carrier_investigation"}],
        "warranties": [],
        "billing": [{"order_id": "ORD-12001", "payment_status": "paid", "amount": 699.0, "currency": "CNY", "invoice_status": "not_requested"}],
    },
    "cust_202": {
        "shipments": [{"order_id": "ORD-12002", "status": "delivered", "carrier": "演示物流", "tracking_id": "DEMO-CN-12002", "exception": None}],
        "warranties": [{"order_id": "ORD-12002", "product": "企业网络网关设备", "coverage": "hardware_warranty", "status": "active", "repair_request_status": "not_created", "note": "模拟保修权益；具体故障、维修范围和费用需人工核查。"}],
        "billing": [{"order_id": "ORD-12002", "payment_status": "paid", "amount": 1299.0, "currency": "CNY", "invoice_status": "issued", "invoice_id": "INV-DEMO-CN-12002"}],
    },
    "cust_203": {
        "shipments": [],
        "warranties": [{"order_id": "ORD-12003", "product": "企业 API 服务套餐", "coverage": "support_service", "status": "active", "repair_request_status": "not_applicable", "note": "数字服务支持权益，不是实体设备保修。"}],
        "billing": [{"order_id": "ORD-12003", "payment_status": "paid", "amount": 3999.0, "currency": "CNY", "invoice_status": "processing", "invoice_id": "INV-DEMO-CN-12003"}],
    },
}
