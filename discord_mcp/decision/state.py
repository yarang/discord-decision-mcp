"""
discord_mcp/decision/state.py

결정 요청 상태를 로컬 JSON 파일로 영속화한다.
프로세스 재시작 후에도 pending 상태를 복원할 수 있다.

상태 파일 위치: ~/.claude/pending_decisions/{question_id}.json
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from discord_mcp.config import config

# 상태 타입 정의
Status = Literal["pending", "disconnected", "resolved", "aborted", "timeout"]


class DecisionState(BaseModel):
    """결정 요청 하나의 전체 상태."""

    question_id: str
    project: str
    question: str
    context: str
    options: list[str]
    timeout_seconds: float | None = None
    thread_id: str
    message_id: str
    asked_at: str  # ISO 8601
    status: Status = "pending"
    clarify_attempts: int = 0
    resolved_at: str | None = None
    resolution: str | None = None
    selected_option: str | None = None

    @classmethod
    def create(
        cls,
        question: str,
        context: str,
        options: list[str],
        thread_id: str,
        message_id: str,
        timeout_seconds: float | None = None,
    ) -> "DecisionState":
        """새 DecisionState를 생성한다."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        rand = uuid.uuid4().hex[:4]
        question_id = f"{config.PROJECT_NAME}_{ts}_{rand}"

        return cls(
            question_id=question_id,
            project=config.PROJECT_NAME,
            question=question,
            context=context,
            options=options,
            timeout_seconds=timeout_seconds,
            thread_id=thread_id,
            message_id=message_id,
            asked_at=datetime.now(timezone.utc).isoformat(),
        )


class StateStore:
    """상태 파일 CRUD."""

    def __init__(self) -> None:
        config.PENDING_DIR.mkdir(parents=True, exist_ok=True)

    def _path(self, question_id: str) -> Path:
        return config.PENDING_DIR / f"{question_id}.json"

    def save(self, state: DecisionState) -> None:
        """상태를 파일로 저장한다."""
        self._path(state.question_id).write_text(
            state.model_dump_json(indent=2), encoding="utf-8"
        )

    def load(self, question_id: str) -> DecisionState | None:
        """question_id로 상태를 로드한다. 없으면 None."""
        path = self._path(question_id)
        if not path.exists():
            return None
        return DecisionState.model_validate_json(path.read_text())

    def load_all_pending(self) -> list[DecisionState]:
        """pending 또는 disconnected 상태인 모든 파일을 로드한다."""
        results = []
        for path in config.PENDING_DIR.glob("*.json"):
            try:
                state = DecisionState.model_validate_json(path.read_text())
                if state.status in ("pending", "disconnected"):
                    results.append(state)
            except Exception:
                pass  # 손상된 파일은 무시
        return results

    def resolve(
        self,
        question_id: str,
        resolution: str,
        selected_option: str | None = None,
    ) -> None:
        """질문이 해결됐음을 기록한다."""
        state = self.load(question_id)
        if state:
            state.status = "resolved"
            state.resolution = resolution
            state.selected_option = selected_option
            state.resolved_at = datetime.now(timezone.utc).isoformat()
            self.save(state)

    def mark_disconnected(self, question_id: str) -> None:
        state = self.load(question_id)
        if state:
            state.status = "disconnected"
            self.save(state)

    def mark_aborted(self, question_id: str) -> None:
        state = self.load(question_id)
        if state:
            state.status = "aborted"
            state.resolved_at = datetime.now(timezone.utc).isoformat()
            self.save(state)

    def is_duplicate(self, question: str) -> bool:
        """동일한 질문이 이미 pending 상태인지 확인한다."""
        for state in self.load_all_pending():
            if state.question.strip() == question.strip():
                return True
        return False


# 모듈 레벨 싱글턴
store = StateStore()
