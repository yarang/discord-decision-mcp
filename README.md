# Discord Decision MCP

Claude Code가 tmux Teammate 모드로 자율 작업 중, 사용자 결정이 필요한 시점에 Discord를 통해 질문하고 응답을 받아 작업을 재개하는 MCP 서버입니다.

## 특징

- **프로젝트당 Bot 1개**: 각 프로젝트는 독립된 Discord Bot 사용
- **무한 대기 기본값**: Timeout 없이 사용자 응답 대기 (Claude가 독단 진행 금지)
- **상태 영속화**: 프로세스 재시작 후에도 대기 상태 복원
- **한국어 친화적**: 한글 선택지, Yes/No 응답 지원

## 설치

```bash
# 저장소 클론
git clone <repo-url>
cd discord-decision

# 의존성 설치
uv sync  # 개발용 가상환경 생성 및 의존성 설치

# (권장) `uv` 명령을 사용하세요; pip는 내부적으로 `uv`가 관리합니다.
```

## 설정

### 1. Discord Bot 생성

1. [Discord Developer Portal](https://discord.com/developers/applications) 접속
2. "New Application" 클릭하여 앱 생성
3. "Bot" 탭에서 봇 생성 및 Token 복사
4. "OAuth2 > URL Generator"에서 봇 초대 링크 생성
   - Scopes: `bot`
   - Permissions: `Send Messages`, `Create Public Threads`, `Send Messages in Threads`, `Read Message History`

### 2. 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일 수정:
```bash
DISCORD_BOT_TOKEN=Bot YOUR_BOT_TOKEN
DISCORD_CHANNEL_ID=123456789012345678
PROJECT_NAME=my-project
```

### 3. Claude Code MCP 설정

프로젝트 루트에 `.mcp.json` 생성:

```json
{
  "$schema": "https://github.com/anthropics/claude-code/raw/main/schema/mcp.json",
  "mcpServers": {
    "discord-decision": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/discord-decision", "discord-mcp"],
      "env": {
        "DISCORD_BOT_TOKEN": "Bot YOUR_BOT_TOKEN",
        "DISCORD_CHANNEL_ID": "123456789012345678",
        "PROJECT_NAME": "my-project"
      }
    }
  }
}
```

**참고**: `enableAllProjectMcpServers: true` 설정이 `~/.claude/settings.json`에 있으면 `.mcp.json`의 서버들이 자동으로 로드됩니다.

## MCP Tools

### discord_ask_decision (블로킹)

사용자 결정이 필요할 때 Discord Thread에 질문 전송 후 응답 대기.

```python
result = discord_ask_decision(
    question="DB 마이그레이션을 실행할까요?",
    context="v1→v2 스키마 변경. ⚠️ 되돌리기 어려움",
    options=["A) 지금 실행", "B) 스테이징 먼저", "C) 보류"]
)
# result.answer → "A) 지금 실행"
```

### discord_notify (논블로킹)

진행 상황 알림.

```python
discord_notify(
    message="테스트 실행 중...",
    level="info"  # info/warning/success/error
)
```

### discord_report_progress

작업 완료 리포트.

```python
discord_report_progress(
    title="배포 완료",
    summary="v2.0.0 배포 성공",
    details=["✅ 테스트 통과", "✅ DB 마이그레이션 완료"]
)
```

### discord_check_pending

세션 시작 시 미해결 질문 확인.

```python
result = discord_check_pending()
# result.has_pending → True/False
# result.pending_questions → [...]
```

## 개발

```bash
# 테스트 실행
DISCORD_BOT_TOKEN="Bot test" DISCORD_CHANNEL_ID="123" pytest tests/ -v

# 타입 체크
pyright discord_mcp/

# 포맷팅
ruff format discord_mcp/
```

## 라이선스

MIT
