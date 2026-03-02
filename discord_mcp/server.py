"""
discord_mcp/server.py

FastMCP 서버 진입점.
모든 MCP Tool을 등록하고 서버를 시작한다.

실행 방법:
    python -m discord_mcp.server
    또는
    discord-mcp  (pyproject.toml scripts 설정 시)

Claude Code MCP 설정 (.claude/mcp.json):
    {
        "mcpServers": {
            "discord-decision": {
                "command": "python",
                "args": ["-m", "discord_mcp.server"],
                "cwd": "/path/to/project",
                "env": {
                    "DISCORD_BOT_TOKEN": "Bot xxxx",
                    "DISCORD_CHANNEL_ID": "1234567890",
                    "PROJECT_NAME": "my-project"
                }
            }
        }
    }
"""

from __future__ import annotations

import asyncio
import logging

from fastmcp import FastMCP

from discord_mcp.tools.ask import discord_ask_decision
from discord_mcp.tools.notify import discord_notify
from discord_mcp.tools.report import discord_report_progress
from discord_mcp.tools.status import discord_check_pending
from discord_mcp.tools.inbox import discord_read_inbox, discord_clear_inbox
from discord_mcp.tools.delete import discord_delete_message, discord_delete_messages

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

# ── MCP 서버 생성 ────────────────────────────────────────────────
mcp = FastMCP(
    name="discord-decision-mcp",
    instructions=(
        "Discord를 통해 사용자와 의사결정을 주고받는 MCP 서버입니다.\n\n"
        "## 필수 사용 규칙\n"
        "1. 세션 시작 시 항상 discord_check_pending()을 먼저 호출하세요.\n"
        "2. CLAUDE.md의 '의사결정 트리거' 상황에서는 반드시 discord_ask_decision()을 사용하세요.\n"
        "3. 의심스러우면 항상 질문하는 방향으로 결정하세요.\n\n"
        "## Tool 사용 가이드\n"
        "- discord_ask_decision: 블로킹 결정 요청 (사용자 응답 전까지 대기)\n"
        "- discord_notify: 논블로킹 알림 (결정 불필요한 상태 공유)\n"
        "- discord_report_progress: 작업 완료/단계 완료 리포트\n"
        "- discord_check_pending: 세션 시작 시 미해결 질문 확인\n"
    ),
)

# ── Tool 등록 ────────────────────────────────────────────────────
mcp.tool()(discord_ask_decision)
mcp.tool()(discord_notify)
mcp.tool()(discord_report_progress)
mcp.tool()(discord_check_pending)
mcp.tool()(discord_read_inbox)
mcp.tool()(discord_clear_inbox)
mcp.tool()(discord_delete_message)
mcp.tool()(discord_delete_messages)


# ── 진입점 ──────────────────────────────────────────────────────
def main() -> None:
    log.info("Starting Discord Decision MCP server...")
    mcp.run()


if __name__ == "__main__":
    main()
