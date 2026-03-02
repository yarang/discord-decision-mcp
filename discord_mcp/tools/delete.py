"""
discord_mcp/tools/delete.py

Discord 메시지 삭제 도구.
"""

from __future__ import annotations

import logging
from typing import Annotated

from pydantic import Field

from discord_mcp.bot.client import get_client

log = logging.getLogger(__name__)


async def discord_delete_message(
    channel_id: Annotated[str, Field(description="채널 ID 또는 Thread ID")],
    message_id: Annotated[str, Field(description="삭제할 메시지 ID")],
) -> dict:
    """
    Discord에서 메시지를 삭제한다.

    ⚠️ 주의: 삭제된 메시지는 복구할 수 없습니다.
    """
    client = get_client()

    try:
        await client.delete_message(channel_id, message_id)
        log.info("Message deleted: %s in %s", message_id, channel_id)
        return {
            "success": True,
            "message_id": message_id,
            "channel_id": channel_id,
        }
    except Exception as e:
        log.error("Failed to delete message %s: %s", message_id, e)
        return {
            "success": False,
            "error": str(e),
            "message_id": message_id,
            "channel_id": channel_id,
        }


async def discord_delete_messages(
    channel_id: Annotated[str, Field(description="채널 ID")],
    message_ids: Annotated[list[str], Field(description="삭제할 메시지 ID 목록 (2-100개)")],
) -> dict:
    """
    Discord에서 여러 메시지를 일괄 삭제한다.

    ⚠️ 주의: 삭제된 메시지는 복구할 수 없습니다.
    """
    client = get_client()

    try:
        count = await client.delete_messages(channel_id, message_ids)
        log.info("Deleted %d messages in %s", count, channel_id)
        return {
            "success": True,
            "deleted_count": count,
            "channel_id": channel_id,
        }
    except Exception as e:
        log.error("Failed to delete messages: %s", e)
        return {
            "success": False,
            "error": str(e),
            "channel_id": channel_id,
        }
