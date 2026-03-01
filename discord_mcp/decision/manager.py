"""
discord_mcp/decision/manager.py

결정 요청의 전체 생명주기를 관리한다.
- Discord Thread 생성
- 질문 메시지 포맷 및 전송
- 상태 파일 생성
- Poller 실행
"""

from __future__ import annotations

import logging
import signal

from discord_mcp.bot.client import get_client
from discord_mcp.config import config
from discord_mcp.decision.poller import DecisionPoller, PollResult
from discord_mcp.decision.state import DecisionState, store

log = logging.getLogger(__name__)


class DecisionManager:
    """결정 요청의 전체 흐름을 조율한다."""

    def __init__(self) -> None:
        self._client = get_client()
        self._poller = DecisionPoller()
        self._register_signal_handlers()

    # ── 공개 API ────────────────────────────────────────────────

    async def ask(
        self,
        question: str,
        context: str,
        options: list[str],
        timeout_seconds: float | None = None,
        thread_id: str | None = None,
    ) -> PollResult:
        """
        Discord에 결정 질문을 전송하고 응답을 기다린다 (블로킹).

        Args:
            question: 질문 내용
            context: 현재 작업 상황 설명
            options: 선택지 목록 (빈 리스트면 자유 응답)
            timeout_seconds: None이면 무한 대기
            thread_id: 기존 Thread ID. None이면 새 Thread 생성

        Returns:
            PollResult
        """
        # 중복 질문 방지
        if store.is_duplicate(question):
            log.warning("Duplicate question detected, skipping: %s", question[:50])
            existing = next(
                (s for s in store.load_all_pending() if s.question.strip() == question.strip()),
                None,
            )
            if existing:
                log.info("Resuming existing pending question: %s", existing.question_id)
                return await self._poller.wait(existing)

        # Thread 준비
        target_thread_id, first_message_id = await self._prepare_thread(
            question, context, options, timeout_seconds, thread_id
        )

        # 상태 파일 생성
        state = DecisionState.create(
            question=question,
            context=context,
            options=options,
            timeout_seconds=timeout_seconds,
            thread_id=target_thread_id,
            message_id=first_message_id,
        )
        store.save(state)

        log.info("Decision created: %s", state.question_id)

        # 응답 대기 (블로킹)
        return await self._poller.wait(state)

    async def restore_pending(self) -> list[DecisionState]:
        """
        세션 시작 시 pending 상태를 복원한다.
        이미 Discord에서 답변됐으면 자동 해결 처리.

        Returns:
            여전히 미해결인 상태 목록
        """
        pending = store.load_all_pending()
        still_pending = []

        for state in pending:
            # Discord에서 해당 Thread의 새 메시지 확인
            try:
                messages = await self._client.get_messages(
                    channel_id=state.thread_id,
                    after=state.message_id,
                    limit=20,
                )
                user_msgs = [m for m in messages if not m.get("author", {}).get("bot", False)]

                if user_msgs:
                    # 이미 답변됨 → 자동 해결
                    latest = user_msgs[-1]
                    content = latest.get("content", "")
                    store.resolve(state.question_id, resolution=content)
                    log.info("Auto-resolved pending: %s → %s", state.question_id, content[:50])
                else:
                    # 미답변 → Discord에 재시작 알림 후 계속 대기
                    await self._client.send_message(
                        state.thread_id,
                        f"🔄 Claude Code가 재시작되었습니다.\n"
                        f"이전 질문이 아직 대기 중입니다.\n\n"
                        f"**질문:** {state.question}\n\n"
                        f"응답해주시면 작업을 재개합니다.\n"
                        f"*(질문 ID: `{state.question_id}`)*",
                    )
                    state.status = "pending"
                    store.save(state)
                    still_pending.append(state)

            except Exception as e:
                log.error("Failed to check pending %s: %s", state.question_id, e)
                still_pending.append(state)

        return still_pending

    # ── 내부 ────────────────────────────────────────────────────

    async def _prepare_thread(
        self,
        question: str,
        context: str,
        options: list[str],
        timeout_seconds: float | None,
        thread_id: str | None,
    ) -> tuple[str, str]:
        """Thread를 준비하고 질문 메시지를 전송한다. (thread_id, message_id) 반환."""
        msg_content = _format_question(question, context, options, timeout_seconds)

        if thread_id:
            # 기존 Thread에 질문 전송
            msg = await self._client.send_message(thread_id, msg_content)
            return thread_id, msg["id"]
        else:
            # 새 Thread 생성
            thread_name = f"[결정요청] {question[:40]}"
            result = await self._client.create_thread(
                channel_id=config.CHANNEL_ID,
                name=thread_name,
                first_message=msg_content,
                auto_archive_minutes=config.AUTO_ARCHIVE_MINUTES,
            )
            return result["thread"]["id"], result["message"]["id"]

    def _register_signal_handlers(self) -> None:
        """tmux 세션 끊김(SIGHUP) 시 pending 상태를 disconnected로 표시."""
        def _on_sighup(signum, frame):
            for state in store.load_all_pending():
                store.mark_disconnected(state.question_id)
                log.warning("Marked disconnected: %s", state.question_id)

        try:
            signal.signal(signal.SIGHUP, _on_sighup)
        except (OSError, ValueError):
            pass  # 일부 환경에서 SIGHUP 미지원


# ── 메시지 포맷 ──────────────────────────────────────────────────

def _format_question(
    question: str,
    context: str,
    options: list[str],
    timeout_seconds: float | None = None,
) -> str:
    """Discord 질문 메시지를 포맷한다."""
    lines = [
        "🤔 **결정 요청**",
        "",
        f"**📋 질문**",
        f"> {question}",
        "",
        f"**📌 현재 상황**",
        f"> {context}",
    ]

    if options:
        lines += ["", "**🔵 선택지**"]
        lines += [f"> {opt}" for opt in options]

    timeout_str = "없음 (무한 대기)" if timeout_seconds is None else f"{int(timeout_seconds)}초"
    lines += [
        "",
        "⏳ *응답 시까지 작업이 중단됩니다.*",
        f"*(Timeout: {timeout_str})*",
    ]

    return "\n".join(lines)
