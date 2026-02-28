"""Synapse Agent — Entry Point.

Starts the FastAPI server with uvicorn.
"""

import os
import sys
import logging
import asyncio
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

# Fix Windows asyncio event loop policy
# Prevents "RuntimeError: Event loop is closed" on shutdown
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    print(f"""
╔══════════════════════════════════════════════╗
║          🧠 SYNAPSE AGENT v1.0               ║
║     Autonomous AI that Thinks Plans Delivers ║
╠══════════════════════════════════════════════╣
║  API:       http://{host}:{port}                ║
║  Docs:      http://{host}:{port}/docs            ║
║  WebSocket: ws://{host}:{port}/ws                ║
╚══════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "backend.app:app",
        host=host,
        port=port,
        reload=True,
        log_level="info",
    )
