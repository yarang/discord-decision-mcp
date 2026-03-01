"""discord_mcp/tools/notify.py — discord_notify MCP Tool"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from discord_mcp.bot.client import get_client
from discord_mcp.config import config

LEVEL_EMOJI = {
    "info":    "ℹ️",
    "warning": "⚠️",
    "success": "✅",
    "error":   "❌",
}


async def discord_notify(
    message: Annotated[str, Field(description="알림 메시지 내용")],
    level: Annotated[
        Literal["info", "warning", "success", "error"],
        Field(description="알림 레벨"),
    ] = "info",
    thread_id: Annotated[
        str | None,
        Field(description="전송할 Thread ID. None이면 기본 채널에 전송."),
    ] = None,
) -> dict:
    """
    진행 상황을 Discord에 알린다 (논블로킹).
    결정이 필요 없는 상태 업데이트, 경고, 완료 알림에 사용한다.
    """
    emoji = LEVEL_EMOJI.get(level, "ℹ️")
    content = f"{emoji} {message}"
    target = thread_id or config.CHANNEL_ID

    client = get_client()
    msg = await client.send_message(target, content)
    return {"message_id": msg.get("id"), "channel_id": target}
