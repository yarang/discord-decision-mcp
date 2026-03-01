"""
discord_mcp/config.py
설정값을 환경변수에서 로드한다. 모든 모듈은 이 Config를 통해 설정에 접근한다.
"""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ── Discord ───────────────────────────────────────────────────
    BOT_TOKEN: str = os.environ["DISCORD_BOT_TOKEN"]
    CHANNEL_ID: str = os.environ["DISCORD_CHANNEL_ID"]

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
    def auth_header(cls) -> dict[str, str]:
        return {"Authorization": cls.BOT_TOKEN}


# 싱글턴
config = Config()
