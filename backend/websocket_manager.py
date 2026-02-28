"""WebSocket Manager for real-time agent status streaming."""

import json
import logging
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections and broadcasts agent status updates."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Active: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Active: {len(self.active_connections)}")

    async def send_to(self, websocket: WebSocket, event: str, data: dict):
        """Send a message to a specific WebSocket."""
        try:
            message = json.dumps({"event": event, "data": data}, default=str)
            await websocket.send_text(message)
        except Exception as e:
            logger.warning(f"Failed to send WebSocket message: {e}")
            await self.disconnect(websocket)

    async def broadcast(self, event: str, data: dict):
        """Broadcast a message to all connected WebSockets."""
        disconnected = []
        for ws in self.active_connections:
            try:
                message = json.dumps({"event": event, "data": data}, default=str)
                await ws.send_text(message)
            except Exception as e:
                logger.warning(f"Broadcast failed for a connection: {e}")
                disconnected.append(ws)

        for ws in disconnected:
            await self.disconnect(ws)

    async def create_status_callback(self, websocket: WebSocket):
        """Create a callback function for the agent to emit status updates.

        Returns a callable that the AutonomousAgent can use as on_status.
        """
        async def callback(event: str, data: dict):
            await self.send_to(websocket, event, data)
        return callback
