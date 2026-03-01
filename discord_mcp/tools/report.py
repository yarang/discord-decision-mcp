"""discord_mcp/tools/report.py — discord_report_progress MCP Tool"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from discord_mcp.bot.client import get_client
from discord_mcp.config import config


async def discord_report_progress(
    title: Annotated[str, Field(description="리포트 제목")],
    summary: Annotated[str, Field(description="작업 결과 요약")],
    details: Annotated[
        list[str],
        Field(description="세부 항목 목록", default_factory=list),
    ],
    thread_id: Annotated[
        str | None,
        Field(description="전송할 Thread ID. None이면 기본 채널."),
    ] = None,
) -> dict:
    """
    작업 완료 또는 단계 완료 시 결과를 Discord에 리포트한다.
    결정 질문 없이 진행 상황만 공유할 때 사용한다.
    """
    lines = [
        f"📊 **{title}**",
        "",
        f"> {summary}",
    ]
    if details:
        lines.append("")
        lines.extend(f"- {d}" for d in details)

    content = "\n".join(lines)
    target = thread_id or config.CHANNEL_ID

    client = get_client()
    msg = await client.send_message(target, content)
    return {"message_id": msg.get("id"), "channel_id": target}
