"""
discord_mcp/decision/poller.py

Discord 채널을 polling하여 사용자 응답을 감지한다.
무한 대기가 기본값이며, timeout_seconds 설정 시 해당 시간 후 반환한다.
tmux pane에 실시간 대기 상태를 표시한다.
"""

from __future__ import annotations

import asyncio
import sys
import time
import logging
from dataclasses import dataclass

from discord_mcp.bot.client import get_client
from discord_mcp.config import config
from discord_mcp.decision.parser import ParseResult, build_clarify_message, parse_response
from discord_mcp.decision.state import DecisionState, store

log = logging.getLogger(__name__)


@dataclass
class PollResult:
    """Polling 결과."""
    success: bool
    answer: str | None
    selected_option: str | None
    question_id: str = ""
    timed_out: bool = False
    aborted: bool = False


class DecisionPoller:
    """
    Discord 채널을 polling하여 응답을 기다린다.

    - 기본값: 무한 대기 (timeout_seconds=None)
    - tmux pane에 실시간 상태 표시
    - 모호한 응답은 최대 max_clarify_attempts회 재질문
    """

    def __init__(self) -> None:
        self._client = get_client()

    async def wait(self, state: DecisionState) -> PollResult:
        """
        사용자 응답이 올 때까지 polling한다.

        Args:
            state: 현재 결정 요청 상태

        Returns:
            PollResult
        """
        started_at = time.monotonic()
        last_message_id = state.message_id  # 이 ID 이후 메시지만 감지
        clarify_attempts = state.clarify_attempts

        while True:
            # ── tmux pane 상태 업데이트 ──────────────────────────
            elapsed = time.monotonic() - started_at
            _print_waiting_status(state, elapsed)

            # ── Discord 메시지 polling ───────────────────────────
            try:
                messages = await self._client.get_messages(
                    channel_id=state.thread_id,
                    after=last_message_id,
                    limit=10,
                )
            except Exception as e:
                log.warning("Polling error: %s", e)
                await asyncio.sleep(config.POLL_INTERVAL)
                continue

            # 봇 메시지 제외, 사용자 메시지만
            user_msgs = [m for m in messages if not m.get("author", {}).get("bot", False)]

            if user_msgs:
                latest = user_msgs[-1]
                last_message_id = latest["id"]
                content = latest.get("content", "").strip()

                # 응답 파싱
                result = parse_response(content, state.options)

                if result.is_clear:
                    # 명확한 응답 → 완료
                    _print_resolved(state, content)
                    store.resolve(
                        state.question_id,
                        resolution=result.answer,
                        selected_option=result.selected_option,
                    )
                    return PollResult(
                        success=True,
                        answer=result.answer,
                        selected_option=result.selected_option,
                        question_id=state.question_id,
                    )

                else:
                    # 모호한 응답 → 재질문
                    clarify_attempts += 1
                    if clarify_attempts > config.MAX_CLARIFY_ATTEMPTS:
                        # 재질문 한계 초과 → 중단
                        await self._client.send_message(
                            state.thread_id,
                            "⚠️ 응답을 이해하지 못해 작업을 중단합니다.\n"
                            f"질문 ID: `{state.question_id}`\n"
                            "작업을 재개하려면 Claude Code를 다시 시작해주세요.",
                        )
                        store.mark_aborted(state.question_id)
                        return PollResult(
                            success=False,
                            answer=None,
                            selected_option=None,
                            question_id=state.question_id,
                            aborted=True,
                        )

                    # 재질문 전송
                    clarify_msg = build_clarify_message(
                        original_question=state.question,
                        user_answer=content,
                        interpreted=result.interpreted,
                        attempt=clarify_attempts,
                        max_attempts=config.MAX_CLARIFY_ATTEMPTS,
                        options=state.options,
                    )
                    await self._client.send_message(state.thread_id, clarify_msg)

                    # 상태 업데이트
                    state.clarify_attempts = clarify_attempts
                    store.save(state)

            # ── Timeout 체크 (설정된 경우만) ─────────────────────
            if state.timeout_seconds is not None:
                if (time.monotonic() - started_at) >= state.timeout_seconds:
                    await self._client.send_message(
                        state.thread_id,
                        f"⏰ 응답 대기 시간({int(state.timeout_seconds)}초)이 초과되었습니다.\n"
                        f"질문 ID: `{state.question_id}`\n"
                        "작업을 재개하려면 Claude Code를 다시 시작해주세요.",
                    )
                    store.mark_aborted(state.question_id)
                    return PollResult(
                        success=False,
                        answer=None,
                        selected_option=None,
                        question_id=state.question_id,
                        timed_out=True,
                    )

            await asyncio.sleep(config.POLL_INTERVAL)


# ── tmux Pane 상태 표시 ──────────────────────────────────────────

def _print_waiting_status(state: DecisionState, elapsed_seconds: float) -> None:
    """tmux pane에 대기 상태를 출력한다 (ANSI escape로 줄 덮어쓰기)."""
    elapsed_str = _format_elapsed(elapsed_seconds)
    timeout_str = f"{int(state.timeout_seconds)}초" if state.timeout_seconds else "없음 (무한 대기)"

    # 커서를 줄 처음으로 이동 후 덮어쓰기
    status = (
        f"\r\033[K"  # 현재 줄 지우기
        f"⏳ Discord 대기 | "
        f"경과: {elapsed_str} | "
        f"Timeout: {timeout_str} | "
        f"ID: {state.question_id[-12:]}"
    )
    sys.stdout.write(status)
    sys.stdout.flush()


def _print_resolved(state: DecisionState, answer: str) -> None:
    """응답 수신 시 완료 메시지를 출력한다."""
    sys.stdout.write(f"\r\033[K✅ Discord 응답 수신: {answer[:60]}\n")
    sys.stdout.flush()


def _format_elapsed(seconds: float) -> str:
    """초를 HH:MM:SS 형식으로 변환한다."""
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"
