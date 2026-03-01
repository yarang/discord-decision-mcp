"""
discord_mcp/tools/ask.py

discord_ask_decision MCP Tool.
사용자 결정이 필요할 때 Discord에 질문하고 응답을 기다린다 (블로킹).
"""

from __future__ import annotations

from typing import Annotated

from fastmcp import Context
from pydantic import Field

from discord_mcp.decision.manager import DecisionManager

_manager: DecisionManager | None = None


def _get_manager() -> DecisionManager:
    global _manager
    if _manager is None:
        _manager = DecisionManager()
    return _manager


async def discord_ask_decision(
    question: Annotated[str, Field(description="사용자에게 물어볼 질문 내용")],
    context: Annotated[str, Field(description="현재 작업 상황. 사용자가 판단하기 충분한 정보를 담는다")],
    options: Annotated[
        list[str],
        Field(
            description=(
                "선택지 목록. 예: ['A) 지금 실행', 'B) 스테이징 먼저', 'C) 보류']. "
                "자유 응답이면 빈 리스트."
            ),
            default_factory=list,
        ),
    ],
    timeout_seconds: Annotated[
        float | None,
        Field(
            description="응답 대기 Timeout(초). None이면 무한 대기 (기본값). 설정 시 해당 시간 후 작업 중단.",
        ),
    ] = None,
    thread_id: Annotated[
        str | None,
        Field(
            description="기존 Discord Thread ID. None이면 새 Thread를 자동 생성한다.",
        ),
    ] = None,
    ctx: Context = None,
) -> dict:
    """
    사용자의 결정이 필요할 때 Discord Thread에 질문을 전송하고
    응답이 올 때까지 블로킹 대기한다.

    - timeout_seconds=None: 무한 대기 (기본값, 권장)
    - options=[] : 자유 텍스트 응답
    - options=[...]: 선택지 제시 (A/B/C 형식 권장)

    Returns:
        {
            "success": bool,
            "answer": str | None,
            "selected_option": str | None,
            "question_id": str,
            "timed_out": bool,
            "aborted": bool,
        }
    """
    manager = _get_manager()

    result = await manager.ask(
        question=question,
        context=context,
        options=options,
        timeout_seconds=timeout_seconds,
        thread_id=thread_id,
    )

    return {
        "success": result.success,
        "answer": result.answer,
        "selected_option": result.selected_option,
        "question_id": result.question_id,
        "timed_out": result.timed_out,
        "aborted": result.aborted,
    }
