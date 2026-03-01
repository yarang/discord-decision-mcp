"""discord_mcp/tools/status.py — discord_check_pending MCP Tool"""

from __future__ import annotations

from discord_mcp.decision.state import store


async def discord_check_pending() -> dict:
    """
    세션 시작 시 미해결 pending 질문이 있는지 확인한다.
    pending이 있으면 반드시 처리 후 새 작업을 시작해야 한다.

    Returns:
        {
            "has_pending": bool,
            "pending_questions": list of {
                question_id, question, thread_id, asked_at, status
            }
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
