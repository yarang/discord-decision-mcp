"""
discord_mcp/daemon/inbox.py

Discord 메시지를 저장하는 inbox 파일 관리.
Claude Code는 이 파일을 읽어서 새 메시지를 확인한다.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# 기본 inbox 경로
DEFAULT_INBOX_PATH = Path("~/.claude/discord_inbox.json").expanduser()


@dataclass
class InboxMessage:
    """Inbox에 저장되는 메시지."""

    message_id: str
    channel_id: str
    thread_id: str | None
    author: str
    author_id: str
    content: str
    timestamp: str
    read: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InboxMessage":
        return cls(**data)


class InboxStore:
    """
    Discord 메시지를 저장하는 JSON 파일 기반 저장소.

    파일 구조:
    {
        "last_message_id": "1234567890",
        "messages": [
            {
                "message_id": "...",
                "channel_id": "...",
                "thread_id": "...",
                "author": "username",
                "author_id": "...",
                "content": "...",
                "timestamp": "2024-01-01T00:00:00Z",
                "read": false
            }
        ]
    }
    """

    def __init__(self, path: Path = DEFAULT_INBOX_PATH) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._ensure_file()

    def _ensure_file(self) -> None:
        """파일이 없으면 생성."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._write({"last_message_id": None, "messages": []})

    def _read(self) -> dict[str, Any]:
        """파일 읽기."""
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"last_message_id": None, "messages": []}

    def _write(self, data: dict[str, Any]) -> None:
        """파일 쓰기."""
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_message(self, msg: InboxMessage) -> None:
        """새 메시지 추가."""
        with self._lock:
            data = self._read()
            # 중복 방지
            existing_ids = {m["message_id"] for m in data["messages"]}
            if msg.message_id not in existing_ids:
                data["messages"].append(msg.to_dict())
                data["last_message_id"] = msg.message_id
                self._write(data)
                log.info("Added message %s to inbox", msg.message_id)

    def get_unread(self) -> list[InboxMessage]:
        """읽지 않은 메시지 조회."""
        with self._lock:
            data = self._read()
            return [
                InboxMessage.from_dict(m)
                for m in data["messages"]
                if not m.get("read", False)
            ]

    def get_all(self) -> list[InboxMessage]:
        """모든 메시지 조회."""
        with self._lock:
            data = self._read()
            return [InboxMessage.from_dict(m) for m in data["messages"]]

    def mark_read(self, message_id: str) -> None:
        """메시지를 읽음으로 표시."""
        with self._lock:
            data = self._read()
            for msg in data["messages"]:
                if msg["message_id"] == message_id:
                    msg["read"] = True
            self._write(data)

    def mark_all_read(self) -> None:
        """모든 메시지를 읽음으로 표시."""
        with self._lock:
            data = self._read()
            for msg in data["messages"]:
                msg["read"] = True
            self._write(data)

    def clear_read(self) -> None:
        """읽은 메시지 삭제."""
        with self._lock:
            data = self._read()
            data["messages"] = [m for m in data["messages"] if not m.get("read", False)]
            self._write(data)

    def get_last_message_id(self) -> str | None:
        """마지막 메시지 ID 조회."""
        with self._lock:
            data = self._read()
            return data.get("last_message_id")


# 싱글턴
_inbox: InboxStore | None = None


def get_inbox() -> InboxStore:
    global _inbox
    if _inbox is None:
        _inbox = InboxStore()
    return _inbox
