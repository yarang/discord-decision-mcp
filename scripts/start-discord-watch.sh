#!/bin/bash
#
# start-discord-watch.sh
#
# Discord 감시 데몬을 tmux 세션에서 시작합니다.
# Claude Code 세션과 무관하게 백그라운드에서 계속 실행됩니다.
#
# 사용법:
#   ./scripts/start-discord-watch.sh [--interval 10] [--channel 1234567890]
#
# 중지:
#   tmux kill-session -t discord-watch
#
# 상태 확인:
#   tmux attach -t discord-watch
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SESSION_NAME="discord-watch"

# 기본값
INTERVAL="${DISCORD_WATCH_INTERVAL:-10}"
CHANNEL="${DISCORD_CHANNEL_ID:-}"

# 인자 파싱
while [[ $# -gt 0 ]]; do
    case $1 in
        --interval|-i)
            INTERVAL="$2"
            shift 2
            ;;
        --channel|-c)
            CHANNEL="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# 이미 실행 중인지 확인
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "⚠️  Session '$SESSION_NAME' already running"
    echo "To attach: tmux attach -t $SESSION_NAME"
    echo "To stop: tmux kill-session -t $SESSION_NAME"
    exit 1
fi

# 명령어 구성
CMD="cd $PROJECT_DIR && uv run discord-watch --interval $INTERVAL"
if [[ -n "$CHANNEL" ]]; then
    CMD="$CMD --channel $CHANNEL"
fi

# tmux 세션 생성
echo "🚀 Starting Discord watcher in tmux session '$SESSION_NAME'..."
echo "   Interval: ${INTERVAL}s"
echo "   Channel: ${CHANNEL:-<from env>}"
echo ""

tmux new-session -d -s "$SESSION_NAME" "$CMD"

echo "✅ Discord watcher started"
echo ""
echo "Commands:"
echo "  Attach:  tmux attach -t $SESSION_NAME"
echo "  Stop:    tmux kill-session -t $SESSION_NAME"
echo "  Logs:    tmux capture-pane -t $SESSION_NAME -p"
