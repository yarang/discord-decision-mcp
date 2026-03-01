"""tests/test_state.py — discord_mcp.decision.state 테스트"""

import pytest
from pathlib import Path
from unittest.mock import patch

from discord_mcp.decision.state import DecisionState, StateStore


@pytest.fixture
def tmp_store(tmp_path):
    """임시 디렉토리를 사용하는 StateStore."""
    with patch("discord_mcp.decision.state.config") as mock_cfg:
        mock_cfg.PENDING_DIR = tmp_path / "pending"
        mock_cfg.PROJECT_NAME = "test-project"
        store = StateStore()
        yield store


@pytest.fixture
def sample_state():
    with patch("discord_mcp.decision.state.config") as mock_cfg:
        mock_cfg.PROJECT_NAME = "test-project"
        return DecisionState.create(
            question="배포할까요?",
            context="v2.0.0 릴리즈 준비 완료",
            options=["A) 배포", "B) 보류"],
            thread_id="thread-123",
            message_id="msg-456",
        )


class TestStateStore:

    def test_save_and_load(self, tmp_store, sample_state):
        tmp_store.save(sample_state)
        loaded = tmp_store.load(sample_state.question_id)
        assert loaded is not None
        assert loaded.question_id == sample_state.question_id
        assert loaded.status == "pending"

    def test_load_nonexistent(self, tmp_store):
        result = tmp_store.load("nonexistent-id")
        assert result is None

    def test_resolve(self, tmp_store, sample_state):
        tmp_store.save(sample_state)
        tmp_store.resolve(sample_state.question_id, "A) 배포", "A) 배포")
        loaded = tmp_store.load(sample_state.question_id)
        assert loaded.status == "resolved"
        assert loaded.resolution == "A) 배포"
        assert loaded.resolved_at is not None

    def test_mark_disconnected(self, tmp_store, sample_state):
        tmp_store.save(sample_state)
        tmp_store.mark_disconnected(sample_state.question_id)
        loaded = tmp_store.load(sample_state.question_id)
        assert loaded.status == "disconnected"

    def test_mark_aborted(self, tmp_store, sample_state):
        tmp_store.save(sample_state)
        tmp_store.mark_aborted(sample_state.question_id)
        loaded = tmp_store.load(sample_state.question_id)
        assert loaded.status == "aborted"

    def test_load_all_pending(self, tmp_store, sample_state):
        tmp_store.save(sample_state)
        pending = tmp_store.load_all_pending()
        assert len(pending) == 1
        assert pending[0].question_id == sample_state.question_id

    def test_load_all_pending_excludes_resolved(self, tmp_store, sample_state):
        tmp_store.save(sample_state)
        tmp_store.resolve(sample_state.question_id, "A", "A")
        pending = tmp_store.load_all_pending()
        assert len(pending) == 0

    def test_is_duplicate_true(self, tmp_store, sample_state):
        tmp_store.save(sample_state)
        assert tmp_store.is_duplicate("배포할까요?") is True

    def test_is_duplicate_false(self, tmp_store, sample_state):
        tmp_store.save(sample_state)
        assert tmp_store.is_duplicate("다른 질문") is False

    def test_question_id_format(self, sample_state):
        """question_id가 {project}_{timestamp}_{rand} 형식인지 확인."""
        parts = sample_state.question_id.split("_")
        assert parts[0] == "test-project"
        assert len(parts) >= 3
