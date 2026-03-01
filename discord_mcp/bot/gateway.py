"""
discord_mcp/bot/gateway.py

Discord Gateway WebSocket — 수신 전용.
MESSAGE_CREATE 이벤트를 수신하여 콜백으로 전달한다.

Polling 방식이 기본이지만, Gateway를 함께 운영하면
응답 지연을 5초 → 즉시로 단축할 수 있다.
Gateway 없이도 시스템은 정상 동작한다 (Polling fallback).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable, Coroutine
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed

from discord_mcp.config import config

log = logging.getLogger(__name__)

MessageCallback = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class GatewayClient:
    """
    Discord Gateway WebSocket 클라이언트 (수신 전용).

    사용법:
        gw = GatewayClient(on_message=my_handler)
        asyncio.create_task(gw.run())
        ...
        await gw.stop()
    """

    def __init__(self, on_message: MessageCallback) -> None:
        self._on_message = on_message
        self._ws: Any = None
        self._heartbeat_task: asyncio.Task | None = None
        self._sequence: int | None = None
        self._session_id: str | None = None
        self._heartbeat_interval: float = 41.25
        self._running = False
        self._last_ack: float = 0.0

    # ── 공개 API ────────────────────────────────────────────────

    async def run(self) -> None:
        """Gateway에 연결하고 이벤트를 수신한다. 재연결 자동 처리."""
        self._running = True
        backoff = 1.0

        while self._running:
            try:
                await self._connect()
                backoff = 1.0  # 성공 시 backoff 초기화
            except ConnectionClosed as e:
                log.warning("Gateway disconnected: %s", e)
            except Exception as e:
                log.error("Gateway error: %s", e)

            if not self._running:
                break

            log.info("Reconnecting in %.1fs...", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60.0)  # Exponential backoff, 최대 60초

    async def stop(self) -> None:
        """Gateway 연결을 종료한다."""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._ws:
            await self._ws.close()

    # ── 내부 연결 로직 ───────────────────────────────────────────

    async def _connect(self) -> None:
        async with websockets.connect(config.GATEWAY_URL) as ws:
            self._ws = ws
            log.info("Gateway connected")

            async for raw in ws:
                payload = json.loads(raw)
                await self._handle_payload(payload)

    async def _handle_payload(self, payload: dict) -> None:
        op: int = payload.get("op", -1)
        data: Any = payload.get("d")
        seq: int | None = payload.get("s")
        event: str | None = payload.get("t")

        if seq is not None:
            self._sequence = seq

        match op:
            case 10:  # HELLO
                self._heartbeat_interval = data["heartbeat_interval"] / 1000
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                await self._identify()

            case 11:  # HEARTBEAT_ACK
                self._last_ack = time.monotonic()

            case 1:   # HEARTBEAT request
                await self._send_heartbeat()

            case 7:   # RECONNECT
                log.info("Gateway requested reconnect")
                await self._ws.close()

            case 9:   # INVALID_SESSION
                log.warning("Invalid session, re-identifying")
                self._session_id = None
                self._sequence = None
                await asyncio.sleep(2)
                await self._identify()

            case 0:   # DISPATCH
                await self._handle_event(event, data)

    async def _handle_event(self, event: str | None, data: Any) -> None:
        if event == "READY":
            self._session_id = data.get("session_id")
            log.info("Gateway ready. Session: %s", self._session_id)

        elif event == "MESSAGE_CREATE":
            # 봇 메시지 제외
            author = data.get("author", {})
            if not author.get("bot", False):
                await self._on_message(data)

    async def _identify(self) -> None:
        await self._ws.send(json.dumps({
            "op": 2,
            "d": {
                "token": config.BOT_TOKEN.removeprefix("Bot "),
                "intents": (1 << 9) | (1 << 15),  # GUILD_MESSAGES + MESSAGE_CONTENT
                "properties": {
                    "os": "linux",
                    "browser": "discord-decision-mcp",
                    "device": "discord-decision-mcp",
                },
            },
        }))

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            await self._send_heartbeat()

            # ACK 미수신 시 재연결
            if time.monotonic() - self._last_ack > self._heartbeat_interval * 2:
                log.warning("Heartbeat ACK not received, reconnecting")
                await self._ws.close()
                return

    async def _send_heartbeat(self) -> None:
        if self._ws:
            await self._ws.send(json.dumps({"op": 1, "d": self._sequence}))
