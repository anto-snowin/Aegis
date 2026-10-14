"""
Aegis Flow - WebSocket Connection Manager
Handles real-time communication for ambulance tracking, emergency updates, and signal states.
"""

from fastapi import WebSocket
from typing import Dict, Set
import json
import asyncio


class ConnectionManager:
    """Manages WebSocket connections organized by channels."""

    def __init__(self):
        # channel -> set of websocket connections
        self.channels: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, channel: str = "general"):
        """Accept a WebSocket connection and add to channel."""
        await websocket.accept()
        async with self._lock:
            if channel not in self.channels:
                self.channels[channel] = set()
            self.channels[channel].add(websocket)

    async def disconnect(self, websocket: WebSocket, channel: str = "general"):
        """Remove a WebSocket from its channel."""
        async with self._lock:
            if channel in self.channels:
                self.channels[channel].discard(websocket)
                if not self.channels[channel]:
                    del self.channels[channel]

    async def send_to_channel(self, channel: str, data: dict):
        """Send data to all connections in a channel."""
        if channel not in self.channels:
            return
        disconnected = set()
        for ws in self.channels.get(channel, set()):
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.add(ws)
        # Clean up dead connections
        if disconnected:
            async with self._lock:
                for ws in disconnected:
                    self.channels.get(channel, set()).discard(ws)

    async def broadcast(self, data: dict):
        """Send data to all channels."""
        for channel in list(self.channels.keys()):
            await self.send_to_channel(channel, data)

    async def send_personal(self, websocket: WebSocket, data: dict):
        """Send data to a specific WebSocket."""
        try:
            await websocket.send_json(data)
        except Exception:
            pass

    def get_connection_count(self, channel: str = None) -> int:
        """Get number of active connections."""
        if channel:
            return len(self.channels.get(channel, set()))
        return sum(len(conns) for conns in self.channels.values())


# Singleton instance
ws_manager = ConnectionManager()
