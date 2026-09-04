"""独立运行 Tool Governance V2.2 Outbox Worker。"""

import asyncio
import signal
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.database import init_db
from src.observability.logging_config import configure_logging
from src.tools.outbox import tool_outbox_worker


async def main() -> None:
    """初始化表后持续消费 Outbox，收到终止信号时优雅退出。"""
    configure_logging()
    await init_db()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    await tool_outbox_worker.start(force=True)
    await stop.wait()
    await tool_outbox_worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
