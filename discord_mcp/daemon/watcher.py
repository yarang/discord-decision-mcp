"""
discord_mcp/daemon/watcher.py

Discord 감시 데몬 - 지정된 채널을 polling하여 새 메시지를 감지하고
inbox 파일에 기록한다.

실행 방법:
    uv run discord-watch
    또는
    python -m discord_mcp.daemon.watcher

tmux에서 실행:
    tmux new-session -d -s discord-watch 'uv run discord-watch'
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone

from discord_mcp.bot.client import DiscordClient
from discord_mcp.config import config
from discord_mcp.daemon.inbox import InboxStore, InboxMessage

log = logging.getLogger(__name__)

# 기본 polling 간격 (초)
DEFAULT_INTERVAL = 10.0


class DiscordWatcher:
    """
    Discord 채널을 감시하는 데몬.

    - 지정된 채널(들)을 주기적으로 polling
    - 새로운 사용자 메시지 감지
    - inbox 파일에 기록
    - tmux pane에 상태 표시
    """

    def __init__(
        self,
        channel_ids: list[str],
        interval: float = DEFAULT_INTERVAL,
    ) -> None:
        self._channel_ids = channel_ids
        self._interval = interval
        self._client = DiscordClient()
        self._inbox = InboxStore()
        self._running = False
        self._last_ids: dict[str, str] = {}

    async def run(self) -> None:
        """감시 시작."""
        self._running = True
        log.info("Starting Discord watcher...")
        log.info("Watching channels: %s", self._channel_ids)
        log.info("Polling interval: %.1fs", self._interval)
        log.info("Inbox path: %s", self._inbox._path)

        # 초기 메시지 ID 설정 (기존 메시지는 무시)
        await self._init_last_ids()

        # 메인 루프
        while self._running:
            try:
                await self._poll_all()
            except Exception as e:
                log.error("Polling error: %s", e)

            await asyncio.sleep(self._interval)

    async def _init_last_ids(self) -> None:
        """각 채널의 마지막 메시지 ID를 초기화."""
        for channel_id in self._channel_ids:
            try:
                messages = await self._client.get_messages(channel_id, limit=1)
                if messages:
                    self._last_ids[channel_id] = messages[0]["id"]
                    log.info("Channel %s: last message ID = %s", channel_id, self._last_ids[channel_id])
            except Exception as e:
                log.warning("Failed to get initial messages for channel %s: %s", channel_id, e)

    async def _poll_all(self) -> None:
        """모든 채널 polling."""
        for channel_id in self._channel_ids:
            await self._poll_channel(channel_id)

    async def _poll_channel(self, channel_id: str) -> None:
        """단일 채널 polling."""
        last_id = self._last_ids.get(channel_id)

        try:
            messages = await self._client.get_messages(
                channel_id,
                after=last_id,
                limit=50,
            )
        except Exception as e:
            log.warning("Failed to get messages from channel %s: %s", channel_id, e)
            return

        if not messages:
            return

        # 시간순 정렬 (오래된 것부터)
        messages.reverse()

        for msg in messages:
            # 봇 메시지 제외
            author = msg.get("author", {})
            if author.get("bot", False):
                continue

            # inbox에 저장
            inbox_msg = InboxMessage(
                message_id=msg["id"],
                channel_id=channel_id,
                thread_id=msg.get("thread_id"),  # Thread 메시지인 경우
                author=author.get("global_name") or author.get("username", "Unknown"),
                author_id=author.get("id", ""),
                content=msg.get("content", ""),
                timestamp=msg.get("timestamp", datetime.now(timezone.utc).isoformat()),
            )
            self._inbox.add_message(inbox_msg)
            log.info(
                "New message from %s: %s",
                inbox_msg.author,
                inbox_msg.content[:50] + "..." if len(inbox_msg.content) > 50 else inbox_msg.content,
            )

        # 마지막 ID 업데이트
        self._last_ids[channel_id] = messages[-1]["id"]

    def stop(self) -> None:
        """감시 중단."""
        self._running = False
        log.info("Stopping Discord watcher...")


async def main(channel_ids: list[str], interval: float) -> None:
    """메인 진입점."""
    watcher = DiscordWatcher(channel_ids, interval)

    # 시그널 핸들러
    loop = asyncio.get_event_loop()

    def handle_signal():
        watcher.stop()
        loop.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    try:
        await watcher.run()
    finally:
        await watcher._client.close()


def cli() -> None:
    """CLI 진입점."""
    parser = argparse.ArgumentParser(description="Discord channel watcher daemon")
    parser.add_argument(
        "--channel", "-c",
        action="append",
        dest="channels",
        help="Channel ID to watch (can be specified multiple times)",
    )
    parser.add_argument(
        "--interval", "-i",
        type=float,
        default=DEFAULT_INTERVAL,
        help=f"Polling interval in seconds (default: {DEFAULT_INTERVAL})",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # 로깅 설정
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 채널 ID 결정
    channel_ids = args.channels or [config.CHANNEL_ID]
    if not channel_ids:
        log.error("No channel ID specified. Set DISCORD_CHANNEL_ID env or use --channel")
        sys.exit(1)

    # 실행
    asyncio.run(main(channel_ids, args.interval))


if __name__ == "__main__":
    cli()
