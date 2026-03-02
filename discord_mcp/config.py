"""
discord_mcp/config.py
설정값을 환경변수에서 로드한다. 모든 모듈은 이 Config를 통해 설정에 접근한다.
"""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class ConfigError(Exception):
    """설정 누락 에러."""
    pass


class _ConfigMeta(type):
    """설정값에 지연 접근하는 메타클래스."""

    @property
    def BOT_TOKEN(cls) -> str:
        return cls._get_required("DISCORD_BOT_TOKEN")

    @property
    def CHANNEL_ID(cls) -> str:
        return cls._get_required("DISCORD_CHANNEL_ID")

    @property
    def auth_header(cls) -> dict[str, str]:
        return {"Authorization": cls.BOT_TOKEN}


class Config(metaclass=_ConfigMeta):
    """
    환경변수 기반 설정.

    필수 환경변수가 누락된 경우 ConfigError를 발생시킨다.
    """

    # Discord API
    API_BASE: str = "https://discord.com/api/v10"
    GATEWAY_URL: str = "wss://gateway.discord.gg/?v=10&encoding=json"

    # ── 프로젝트 ─────────────────────────────────────────────────
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "project")

    # ── 상태 영속화 ──────────────────────────────────────────────
    PENDING_DIR: Path = Path(
        os.getenv("PENDING_DIR", "~/.claude/pending_decisions")
    ).expanduser()

    # ── Polling ──────────────────────────────────────────────────
    POLL_INTERVAL: float = float(os.getenv("POLL_INTERVAL_SECONDS", "5"))

    # ── 재질문 제한 ──────────────────────────────────────────────
    MAX_CLARIFY_ATTEMPTS: int = 2

    # ── Thread 자동 아카이브 (분) ────────────────────────────────
    AUTO_ARCHIVE_MINUTES: int = 1440  # 24시간

    @classmethod
    def _get_required(cls, name: str) -> str:
        """필수 환경변수를 가져온다. 누락 시 ConfigError."""
        value = os.environ.get(name)
        if not value:
            raise ConfigError(
                f"필수 환경변수가 설정되지 않았습니다: {name}\n"
                f".env 파일을 생성하거나 환경변수를 설정하세요.\n"
                f"예시:\n"
                f"  DISCORD_BOT_TOKEN=Bot YOUR_BOT_TOKEN\n"
                f"  DISCORD_CHANNEL_ID=123456789012345678"
            )
        return value


# 싱글턴
config = Config
