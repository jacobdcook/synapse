"""Collaboration: WebSocket server/client for session sharing."""
__all__ = ["SessionServer", "SessionClient", "MSG_CHAT", "MSG_TYPING", "MSG_MODEL_RESPONSE"]

import asyncio
import json
import logging
from typing import Optional, Callable, Set

log = logging.getLogger(__name__)

try:
    import websockets
except ImportError:
    websockets = None


MSG_CHAT = "CHAT_MESSAGE"
MSG_TYPING = "TYPING_INDICATOR"
MSG_MODEL_RESPONSE = "MODEL_RESPONSE"


class SessionServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self._clients: Set = set()
        self._server = None
        self._on_message: Optional[Callable] = None

    def set_message_handler(self, handler: Callable):
        self._on_message = handler

    async def _handle_client(self, ws, path):
        self._clients.add(ws)
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                    if self._on_message:
                        self._on_message(msg)
                    for c in self._clients:
                        if c != ws:
                            await c.send(raw)
                except json.JSONDecodeError:
                    pass
        finally:
            self._clients.discard(ws)

    async def start(self):
        if not websockets:
            log.warning("websockets not installed; collaboration disabled")
            return
        self._server = await websockets.serve(self._handle_client, self.host, self.port)
        log.info(f"Collaboration server on {self.host}:{self.port}")

    def stop(self):
        if self._server:
            self._server.close()


class SessionClient:
    def __init__(self, url: str = "ws://127.0.0.1:8765"):
        self.url = url
        self._ws = None
        self._on_message: Optional[Callable] = None

    def set_message_handler(self, handler: Callable):
        self._on_message = handler

    async def connect(self) -> bool:
        if not websockets:
            return False
        try:
            self._ws = await websockets.connect(self.url)
            asyncio.create_task(self._recv_loop())
            return True
        except Exception as e:
            log.warning(f"Collaboration connect failed: {e}")
            return False

    async def _recv_loop(self):
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                if self._on_message:
                    self._on_message(msg)
        except Exception as e:
            log.debug(f"Collaboration recv ended: {e}")

    async def send(self, msg_type: str, payload: dict):
        if self._ws:
            await self._ws.send(json.dumps({"type": msg_type, **payload}))
