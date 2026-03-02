# Discord Decision MCP — Claude Code 개발 지침

## 프로젝트 개요

이 프로젝트는 Claude Code가 tmux Teammate 모드로 자율 작업하는 중
사용자 결정이 필요한 시점에 Discord MCP를 통해 질문하고 응답을 받아 작업을
재개하는 시스템이다.

### 핵심 원칙
- **프로젝트당 Bot 1개**: 각 프로젝트는 독립된 Discord Bot을 사용한다
- **무한 대기 기본값**: Timeout 없이 사용자 응답을 기다린다. Claude가 독단으로 진행하지 않는다
- **상태 영속화**: 프로세스 재시작 후에도 대기 상태를 복원한다
- **MCP 기반 통신**: 모든 Discord 통신은 MCP Tool을 통해 이루어진다

---

## MCP 서버 설정

### 1. 환경변수 설정 (.env)

```bash
cp .env.example .env
# .env 파일을 열어 실제 값으로 수정
```

### 2. Claude Code MCP 설정

프로젝트 루트에 `.mcp.json` 파일 생성:

```json
{
  "$schema": "https://github.com/anthropics/claude-code/raw/main/schema/mcp.json",
  "mcpServers": {
    "discord-decision": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/discord-decision", "discord-mcp"],
      "env": {
        "DISCORD_BOT_TOKEN": "Bot YOUR_BOT_TOKEN",
        "DISCORD_CHANNEL_ID": "YOUR_CHANNEL_ID",
        "PROJECT_NAME": "your-project-name"
      }
    }
  }
}
```

**참고**: `~/.claude/settings.json`에 `enableAllProjectMcpServers: true`가 설정되어 있어야 프로젝트 MCP 서버가 자동으로 로드됩니다.

---

## 의사결정 트리거 (반드시 Discord에 질문할 것)

### 블로킹 결정 (응답 전까지 작업 중단)

아래 상황에서는 반드시 `mcp__discord_decision__discord_ask_decision`을 호출한 후 응답을 기다린다.
응답 없이 작업을 진행하는 것은 절대 금지다.

- 프로덕션 환경 배포 전
- 데이터베이스 스키마 변경 전 (마이그레이션 실행)
- 기존 파일 삭제 또는 덮어쓰기 전 (새로 생성하는 파일 제외)
- 외부 서비스 크리덴셜/API 키 변경 전
- 아키텍처 방향이 초기 계획과 달라질 것 같을 때
- 작업 범위가 예상보다 크게 확대될 때
- 두 가지 이상 접근법 중 하나를 선택해야 할 때 (트레이드오프가 비슷한 경우)
- 되돌리기 어려운 작업 전 (외부 API 호출, 과금 발생 등)

### Claude 자율 판단 기준

CLAUDE.md에 명시되지 않은 상황에서의 판단 기준:
- 되돌리기 어렵다 → 질문한다
- 요구사항이 모호하다 → 질문한다
- 확신이 없다 → 질문한다
- **의심스러우면 항상 질문하는 방향으로 결정한다**

### 금지 사항

```
❌ 블로킹 트리거 상황에서 Discord 질문 없이 작업 진행
❌ 모호한 응답을 임의 해석하여 위험 작업 실행
❌ 세션 시작 시 pending 상태 확인 생략
❌ 동일 question_id로 중복 질문 전송
❌ timeout 미설정 질문을 임의로 진행
```

---

## 세션 시작 시 필수 절차

Claude Code 세션이 시작될 때마다 반드시 아래 순서를 따른다:

### 1. Pending 상태 확인

```
mcp__discord_decision__discord_check_pending
```

반환값:
```json
{
  "has_pending": true/false,
  "pending_questions": [
    {
      "question_id": "...",
      "question": "...",
      "thread_id": "...",
      "asked_at": "...",
      "status": "pending"
    }
  ]
}
```

### 2. Pending 처리

`has_pending`이 `true`면:
- Discord Thread에서 이미 답변됐는지 확인
- 답변됨 → 해당 결정으로 작업 재개
- 미답변 → 대기 재개 (이전 질문에 대한 응답 대기)

### 3. 작업 시작 알림

```
mcp__discord_decision__discord_notify
```
- message: "작업을 시작합니다: {task}"
- level: "info"

---

## MCP Tool 사용 가이드

### discord_ask_decision — 사용자 결정 요청 (블로킹)

**언제 사용:** 사용자의 결정이 필요한 모든 블로킹 상황

**파라미터:**
| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| question | string | ✅ | 사용자에게 물어볼 질문 |
| context | string | ✅ | 현재 작업 상황. 판단에 충분한 정보 |
| options | string[] | ❌ | 선택지 목록. 빈 배열이면 자유 응답 |
| timeout_seconds | float | ❌ | 대기 Timeout(초). null이면 무한 대기 |
| thread_id | string | ❌ | 기존 Thread ID. null이면 새 Thread 생성 |

**반환값:**
```json
{
  "success": true,
  "answer": "A) 지금 바로 실행",
  "selected_option": "A) 지금 바로 실행",
  "question_id": "project_20260301_abc123",
  "timed_out": false,
  "aborted": false
}
```

**질문 작성 원칙:**
- context에 사용자가 판단하기 충분한 정보를 담는다
- 선택지는 A/B/C로 명확하게 구분한다
- 각 선택지에 결과를 함께 설명한다
- 되돌리기 어려운 작업은 ⚠️ 를 붙인다
- 질문은 하나씩만 한다 (여러 결정을 묶지 않는다)

**예시:**
```json
{
  "question": "DB 마이그레이션을 실행할까요?",
  "context": "v1→v2 스키마 변경. user 테이블에 email_verified 컬럼 추가. 기존 데이터 영향 없음. ⚠️ 되돌리기 어려움",
  "options": [
    "A) 지금 바로 실행",
    "B) 스테이징 확인 후 실행",
    "C) 보류"
  ]
}
```

---

### discord_notify — 진행 상황 알림 (논블로킹)

**언제 사용:** 결정이 필요 없는 상태 업데이트, 경고, 완료 알림

**파라미터:**
| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| message | string | ✅ | 알림 메시지 내용 |
| level | string | ❌ | info / warning / success / error (기본값: info) |
| thread_id | string | ❌ | 전송할 Thread ID. null이면 기본 채널 |

**예시:**
```json
{
  "message": "테스트 스위트 실행 중... (예상 소요: 3분)",
  "level": "info"
}
```

---

### discord_report_progress — 작업 완료 리포트

**언제 사용:** 작업 완료 또는 단계 완료 시 결과 공유

**파라미터:**
| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| title | string | ✅ | 리포트 제목 |
| summary | string | ✅ | 작업 결과 요약 |
| details | string[] | ❌ | 세부 항목 목록 |
| thread_id | string | ❌ | 전송할 Thread ID. null이면 기본 채널 |

**예시:**
```json
{
  "title": "DB 마이그레이션 완료",
  "summary": "v1→v2 마이그레이션 성공적으로 완료.",
  "details": [
    "✅ email_verified 컬럼 추가",
    "✅ 기존 데이터 무결성 검증",
    "소요 시간: 2분 34초"
  ]
}
```

---

### discord_check_pending — 미해결 질문 확인

**언제 사용:** 세션 시작 시

**파라미터:** 없음

**반환값:**
```json
{
  "has_pending": true,
  "pending_questions": [
    {
      "question_id": "project_20260301_abc123",
      "question": "배포할까요?",
      "thread_id": "1234567890",
      "asked_at": "2026-03-01T10:30:00Z",
      "status": "pending"
    }
  ]
}
```

---

## 환경변수 (.env)

```bash
# 필수
DISCORD_BOT_TOKEN=Bot xxxxxxxxxxxx      # Discord Bot Token ("Bot " 접두사 포함)
DISCORD_CHANNEL_ID=1234567890            # 기본 질문 채널 ID

# 선택
PROJECT_NAME=my-project                  # question_id 생성에 사용 (기본값: project)
PENDING_DIR=~/.claude/pending_decisions  # 상태 파일 저장 경로
POLL_INTERVAL_SECONDS=5                  # Discord polling 간격 (초)
```

---

## 감시 데몬 (Discord Watcher)

Claude Code 세션과 무관하게 Discord 채널을 감시하는 별도 프로세스다.
사용자가 Discord에 보낸 메시지를 수집하여 inbox 파일에 저장한다.

### 시작하기

```bash
# tmux 세션에서 감시 데몬 시작
./scripts/start-discord-watch.sh

# 또는 직접 실행
uv run discord-watch --interval 10

# 상태 확인
tmux attach -t discord-watch

# 중지
tmux kill-session -t discord-watch
```

### Inbox 확인

Claude Code에서 `discord_read_inbox` Tool로 메시지를 확인한다:

```
mcp__discord_decision__discord_read_inbox
```

**파라미터:**
| 이름 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| unread_only | bool | true | 읽지 않은 메시지만 반환 |
| mark_read | bool | false | 조회한 메시지를 읽음으로 표시 |

**반환값:**
```json
{
  "success": true,
  "messages": [
    {
      "message_id": "1234567890",
      "channel_id": "1234567890",
      "thread_id": null,
      "author": "username",
      "content": "메시지 내용",
      "timestamp": "2024-01-01T00:00:00Z",
      "read": false
    }
  ],
  "count": 1,
  "unread_count": 1
}
```

### Inbox 정리

```
mcp__discord_decision__discord_clear_inbox
```

**파라미터:**
| 이름 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| read_only | bool | true | 읽은 메시지만 삭제 |

### 아키텍처

```
[Discord API]
     ↓ polling (10초 간격)
[discord-watch 데몬] → ~/.claude/discord_inbox.json
                              ↓
                    [Claude Code] discord_read_inbox()
```

---

## 개발 시 참고

- 모든 Discord API 호출은 `discord_mcp/bot/client.py`의 `DiscordClient`를 통한다
- 상태 파일은 `~/.claude/pending_decisions/{question_id}.json`에 저장된다
- Inbox 파일은 `~/.claude/discord_inbox.json`에 저장된다
- WebSocket은 수신 전용이며 `discord_mcp/bot/gateway.py`가 관리한다
- 응답 파싱 실패 시 재질문은 최대 2회까지만 한다
- 테스트는 `pytest tests/`로 실행한다
