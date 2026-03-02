"""
discord_mcp/bot/client.py

Discord REST API 클라이언트.
모든 Discord HTTP 요청은 이 클래스를 통한다.
Rate limit 헤더를 자동으로 처리한다.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from discord_mcp.config import config

log = logging.getLogger(__name__)


class DiscordClient:
    """Discord REST API 클라이언트 (싱글턴 사용 권장)."""

    def __init__(self) -> None:
        self._http = httpx.AsyncClient(
            base_url=config.API_BASE,
            headers={
                **config.auth_header,
                "Content-Type": "application/json",
                "User-Agent": "DiscordBot (discord-decision-mcp, 1.0.0)",
            },
            timeout=30.0,
        )

    # ── 메시지 ──────────────────────────────────────────────────

    async def send_message(
        self,
        channel_id: str,
        content: str,
        embeds: list[dict] | None = None,
    ) -> dict[str, Any]:
        """채널(또는 Thread)에 메시지를 전송한다."""
        payload: dict[str, Any] = {"content": content}
        if embeds:
            payload["embeds"] = embeds

        return await self._request(
            "POST", f"/channels/{channel_id}/messages", json=payload
        )

    async def get_messages(
        self,
        channel_id: str,
        after: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """채널의 메시지 목록을 가져온다. after: 해당 message_id 이후 메시지만."""
        params: dict[str, Any] = {"limit": min(limit, 100)}
        if after:
            params["after"] = after

        return await self._request(
            "GET", f"/channels/{channel_id}/messages", params=params
        )

    async def delete_message(
        self,
        channel_id: str,
        message_id: str,
    ) -> bool:
        """메시지를 삭제한다. 성공 시 True 반환."""
        await self._request(
            "DELETE", f"/channels/{channel_id}/messages/{message_id}"
        )
        return True

    async def delete_messages(
        self,
        channel_id: str,
        message_ids: list[str],
    ) -> int:
        """여러 메시지를 일괄 삭제한다 (2-100개). 삭제된 개수 반환."""
        if len(message_ids) < 2 or len(message_ids) > 100:
            raise ValueError("일괄 삭제는 2-100개 메시지만 가능합니다.")

        await self._request(
            "POST",
            f"/channels/{channel_id}/messages/bulk-delete",
            json={"messages": message_ids},
        )
        return len(message_ids)

    # ── Thread ──────────────────────────────────────────────────

    async def create_thread(
        self,
        channel_id: str,
        name: str,
        first_message: str,
        auto_archive_minutes: int = 1440,
    ) -> dict[str, Any]:
        """채널에 새 Thread를 생성하고 첫 메시지를 전송한다."""
        # 먼저 메시지를 전송하고 그 메시지에 Thread를 생성
        msg = await self.send_message(channel_id, first_message)
        thread = await self._request(
            "POST",
            f"/channels/{channel_id}/messages/{msg['id']}/threads",
            json={
                "name": name,
                "auto_archive_duration": auto_archive_minutes,
            },
        )
        return {"thread": thread, "message": msg}

    async def create_standalone_thread(
        self,
        channel_id: str,
        name: str,
        auto_archive_minutes: int = 1440,
    ) -> dict[str, Any]:
        """메시지 없이 Thread를 생성한다 (Forum 채널용)."""
        return await self._request(
            "POST",
            f"/channels/{channel_id}/threads",
            json={
                "name": name,
                "auto_archive_duration": auto_archive_minutes,
                "type": 11,  # PUBLIC_THREAD
            },
        )

    async def archive_thread(self, thread_id: str) -> dict[str, Any]:
        """Thread를 아카이브한다."""
        return await self._request(
            "PATCH",
            f"/channels/{thread_id}",
            json={"archived": True},
        )

    # ── 내부 ────────────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Any:
        """HTTP 요청 실행. Rate limit 발생 시 자동 대기 후 재시도."""
        for attempt in range(5):
            resp = await self._http.request(method, path, **kwargs)

            if resp.status_code == 429:
                # Rate limit
                data = resp.json()
                retry_after = float(data.get("retry_after", 1.0))
                log.warning("Rate limited. Retrying after %.1fs", retry_after)
                await asyncio.sleep(retry_after)
                continue

            resp.raise_for_status()

            if resp.status_code == 204:
                return {}

            return resp.json()

        raise RuntimeError(f"Discord API request failed after 5 attempts: {method} {path}")

    async def close(self) -> None:
        await self._http.aclose()


# 모듈 레벨 싱글턴
_client: DiscordClient | None = None


def get_client() -> DiscordClient:
    global _client
    if _client is None:
        _client = DiscordClient()
    return _client
