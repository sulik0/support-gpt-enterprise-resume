import logging
import datetime
from typing import List, Dict, Any

logger = logging.getLogger("supportgpt.tools.ticketing")

class TicketingTool:
    """模拟工单系统的历史记录查询能力。"""
    def __init__(self):
        # Stub data for past tickets
        self.ticket_history: Dict[str, List[Dict[str, Any]]] = {
            "cust_101": [
                {
                    "ticket_id": 401,
                    "subject": "Billing issue on monthly SaaS charge",
                    "description": "Double billed on my subscription plan.",
                    "status": "resolved",
                    "resolution": "Refunded the duplicate invoice charge.",
                    "created_at": datetime.datetime.utcnow() - datetime.timedelta(days=15)
                }
            ],
            "cust_102": [],
            "cust_103": [
                {
                    "ticket_id": 501,
                    "subject": "API connectivity timeouts",
                    "description": "Getting 504 errors on /v1/chat endpoint.",
                    "status": "resolved",
                    "resolution": "Updated DNS settings to point to fallback cluster.",
                    "created_at": datetime.datetime.utcnow() - datetime.timedelta(days=3)
                }
            ]
        }

    def get_past_tickets(self, customer_id: str) -> List[Dict[str, Any]]:
        """Fetch historical tickets for a customer."""
        logger.info(f"Retrieving ticketing history logs for customer: {customer_id}")
        return self.ticket_history.get(customer_id, [])

ticketing_tool = TicketingTool()
