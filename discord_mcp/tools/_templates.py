"""
discord_mcp/tools/notify.py   — discord_notify
discord_mcp/tools/report.py   — discord_report_progress
discord_mcp/tools/status.py   — discord_check_pending

논블로킹 알림 및 상태 확인 Tools.
"""

# ── notify.py 내용 ────────────────────────────────────────────────
NOTIFY_CONTENT = '''
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
        Field(description="알림 레벨", default="info"),
    ] = "info",
    thread_id: Annotated[
        str | None,
        Field(description="전송할 Thread ID. None이면 기본 채널에 전송.", default=None),
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
'''

# ── report.py 내용 ────────────────────────────────────────────────
REPORT_CONTENT = '''
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
    ] = [],
    thread_id: Annotated[
        str | None,
        Field(description="전송할 Thread ID. None이면 기본 채널.", default=None),
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

    content = "\\n".join(lines)
    target = thread_id or config.CHANNEL_ID

    client = get_client()
    msg = await client.send_message(target, content)
    return {"message_id": msg.get("id"), "channel_id": target}
'''

# ── status.py 내용 ────────────────────────────────────────────────
STATUS_CONTENT = '''
from __future__ import annotations
from discord_mcp.decision.state import store
from discord_mcp.bot.client import get_client

async def discord_check_pending() -> dict:
    """
    세션 시작 시 미해결 pending 질문이 있는지 확인한다.
    pending이 있으면 반드시 처리 후 새 작업을 시작해야 한다.

    Returns:
        {
            "has_pending": bool,
            "pending_questions": [
                {
                    "question_id": str,
                    "question": str,
                    "thread_id": str,
                    "asked_at": str,
                    "status": str,
                }
            ]
        }
    """
    pending = store.load_all_pending()
    return {
        "has_pending": len(pending) > 0,
        "pending_questions": [
            {
                "question_id": s.question_id,
                "question": s.question,
                "thread_id": s.thread_id,
                "asked_at": s.asked_at,
                "status": s.status,
            }
            for s in pending
        ],
    }
'''
