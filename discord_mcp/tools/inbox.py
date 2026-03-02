"""
discord_mcp/tools/inbox.py

MCP Tool: discord_read_inbox
Inbox에 저장된 Discord 메시지를 조회한다.
"""

from __future__ import annotations

import logging
from typing import Annotated

from pydantic import Field

from discord_mcp.daemon.inbox import get_inbox

log = logging.getLogger(__name__)


async def discord_read_inbox(
    unread_only: Annotated[
        bool,
        Field(description="true면 읽지 않은 메시지만 반환, false면 모든 메시지 반환"),
    ] = True,
    mark_read: Annotated[
        bool,
        Field(description="true면 조회한 메시지를 읽음으로 표시"),
    ] = False,
) -> dict:
    """
    Discord inbox에 저장된 메시지를 조회한다.

    감시 데몬(discord-watch)이 수집한 Discord 메시지를 조회합니다.
    Claude Code는 이 Tool을 호출하여 사용자가 Discord에서 보낸 메시지를 확인할 수 있습니다.

    Returns:
        {
            "success": true,
            "messages": [
                {
                    "message_id": "1234567890",
                    "channel_id": "1234567890",
                    "thread_id": null,
                    "author": "username",
                    "author_id": "1234567890",
                    "content": "메시지 내용",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "read": false
                }
            ],
            "count": 1,
            "unread_count": 1
        }
    """
    try:
        inbox = get_inbox()

        if unread_only:
            messages = inbox.get_unread()
        else:
            messages = inbox.get_all()

        # 읽음 표시
        if mark_read and messages:
            if unread_only:
                inbox.mark_all_read()
            else:
                for msg in messages:
                    inbox.mark_read(msg.message_id)

        unread_count = len(inbox.get_unread())

        return {
            "success": True,
            "messages": [msg.to_dict() for msg in messages],
            "count": len(messages),
            "unread_count": unread_count,
        }

    except Exception as e:
        log.error("Failed to read inbox: %s", e)
        return {
            "success": False,
            "error": str(e),
            "messages": [],
            "count": 0,
            "unread_count": 0,
        }


async def discord_clear_inbox(
    read_only: Annotated[
        bool,
        Field(description="true면 읽은 메시지만 삭제, false면 모든 메시지 삭제"),
    ] = True,
) -> dict:
    """
    Discord inbox에서 메시지를 삭제한다.

    Args:
        read_only: true면 읽은 메시지만 삭제

    Returns:
        {"success": true, "deleted_count": 5}
    """
    try:
        inbox = get_inbox()

        if read_only:
            inbox.clear_read()
            return {"success": True, "message": "Read messages cleared"}
        else:
            inbox._write({"last_message_id": None, "messages": []})
            return {"success": True, "message": "All messages cleared"}

    except Exception as e:
        log.error("Failed to clear inbox: %s", e)
        return {"success": False, "error": str(e)}
