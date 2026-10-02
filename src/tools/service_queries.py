"""演示售后查询适配器；不连接真实物流、财务或维修系统。"""

from copy import deepcopy
from typing import Any


class ServiceQueryAdapter:
    """提供客户隔离的物流、保修和账务查询。

    返回明确的模拟来源；未知客户不返回其他客户的数据。
    """

    _records = {
        "cust_101": {
            "shipments": [{"order_id": "ORD-7001", "status": "delivered", "carrier": "demo_carrier", "tracking_id": "DEMO-7001", "exception": None}],
            "warranties": [],
            "billing": [{"order_id": "ORD-7001", "payment_status": "paid", "amount": 150.0, "currency": "USD", "invoice_status": "issued", "invoice_id": "INV-DEMO-7001"}],
        },
        "cust_102": {
            "shipments": [{"order_id": "ORD-8002", "status": "in_transit", "carrier": "demo_carrier", "tracking_id": "DEMO-8002", "exception": "delivery_delayed", "next_step": "carrier_investigation"}],
            "warranties": [],
            "billing": [{"order_id": "ORD-8002", "payment_status": "paid", "amount": 25.0, "currency": "USD", "invoice_status": "not_requested"}],
        },
        "cust_103": {
            "shipments": [{"order_id": "ORD-9003", "status": "delivered", "carrier": "demo_carrier", "tracking_id": "DEMO-9003", "exception": None}],
            "warranties": [{"order_id": "ORD-9003", "product": "Dedicated AWS Gateway Cluster", "coverage": "support_service", "status": "active", "repair_request_status": "not_created", "note": "这是服务支持权益，不代表实体设备保修资格。"}],
            "billing": [{"order_id": "ORD-9003", "payment_status": "paid", "amount": 5400.0, "currency": "USD", "invoice_status": "issued", "invoice_id": "INV-DEMO-9003"}],
        },
    }

    def _query(self, customer_id: str, resource: str) -> dict[str, Any]:
        # 无记录与不存在分开表达，不能据此承诺退款或维修。
        record = self._records.get(customer_id)
        return {
            "customer_id": customer_id,
            "status": "found" if record is not None else "not_found",
            "records": deepcopy(record.get(resource, [])) if record else [],
            "source": "local_demo_adapter",
            "mocked": True,
        }

    def get_shipments(self, customer_id: str) -> dict[str, Any]:
        """查询该客户的配送状态和物流异常。"""
        return self._query(customer_id, "shipments")

    def get_warranties(self, customer_id: str) -> dict[str, Any]:
        """查询已有权益，不执行维修申请或判定赔付。"""
        return self._query(customer_id, "warranties")

    def get_billing(self, customer_id: str) -> dict[str, Any]:
        """查询支付和开票状态，不返回银行卡或税务身份信息。"""
        return self._query(customer_id, "billing")

    def get_service_status(self, customer_id: str) -> dict[str, Any]:
        """返回模拟服务健康状态，不将未知故障判定为已修复。"""
        known = customer_id in self._records
        return {
            "status": "found" if known else "not_found",
            "records": [{"service": "support_api", "status": "operational", "active_incidents": [], "note": "演示状态；用户端故障仍需错误码与请求时间排查。"}] if known else [],
            "source": "local_demo_adapter", "mocked": True,
        }


service_query_adapter = ServiceQueryAdapter()
