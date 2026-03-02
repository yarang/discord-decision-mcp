# Discord Decision MCP — 아키텍처 설계문서

## 1. 프로젝트 개요

### 1.1 목적

Claude Code가 tmux Teammate 모드로 자율 작업 중, 사용자 결정이 필요한 시점에 Discord를 통해 질문하고 응답을 받아 작업을 재개하는 MCP (Model Context Protocol) 서버입니다.

### 1.2 핵심 특징

| 특징 | 설명 |
|------|------|
| **프로젝트당 Bot 1개** | 각 프로젝트는 독립된 Discord Bot 사용 |
| **무한 대기 기본값** | Timeout 없이 사용자 응답 대기 (Claude가 독단 진행 금지) |
| **상태 영속화** | 프로세스 재시작 후에도 대기 상태 복원 |
| **한국어 친화적** | 한글 선택지, Yes/No 응답 지원 |
| **MCP 기반 통신** | 모든 Discord 통신은 MCP Tool을 통해 이루어짐 |

### 1.3 버전 정보

- **버전**: 1.0.0
- **Python 요구사항**: >= 3.11
- **MCP 프레임워크**: FastMCP >= 0.1.0

---

## 2. 디렉토리 구조

```
discord-decision/
├── discord_mcp/              # 메인 패키지
│   ├── __init__.py
│   ├── server.py             # MCP 서버 진입점
│   ├── config.py             # 환경변수 설정 관리
│   │
│   ├── bot/                  # Discord API 클라이언트
│   │   ├── __init__.py
│   │   ├── client.py         # REST API 클라이언트 (httpx)
│   │   └── gateway.py        # WebSocket 게이트웨이 (수신 전용)
│   │
│   ├── decision/             # 결정 요청 관리
│   │   ├── __init__.py
│   │   ├── manager.py        # 결정 요청 생명주기 관리
│   │   ├── poller.py         # Discord Polling 및 응답 대기
│   │   ├── parser.py         # 사용자 응답 파싱
│   │   └── state.py          # 상태 영속화 (JSON 파일)
│   │
│   ├── tools/                # MCP Tools 구현
│   │   ├── __init__.py
│   │   ├── ask.py            # discord_ask_decision
│   │   ├── notify.py         # discord_notify
│   │   ├── report.py         # discord_report_progress
│   │   ├── status.py         # discord_check_pending
│   │   ├── inbox.py          # discord_read_inbox, discord_clear_inbox
│   │   └── _templates.py     # Discord 메시지 템플릿
│   │
│   └── daemon/               # 감시 데몬
│       ├── __init__.py
│       ├── watcher.py        # Discord 채널 감시 (discord-watch CLI)
│       └── inbox.py          # Inbox 파일 관리
│
├── scripts/                  # 유틸리티 스크립트
│   └── start-discord-watch.sh
│
├── tests/                    # 테스트 스위트
│   ├── __init__.py
│   ├── test_parser.py
│   └── test_state.py
│
├── docs/                     # 문서
│   └── architecture.md       # 이 파일
│
├── CLAUDE.md                 # Claude Code 프로젝트 지침
├── README.md                 # 프로젝트 설명
├── pyproject.toml            # 프로젝트 설정 및 의존성
└── mcp.json.example          # MCP 설정 예시
```

---

## 3. 주요 모듈 설명

### 3.1 서버 진입점 (`server.py`)

**역할**: FastMCP 서버 생성 및 MCP Tool 등록

```python
mcp = FastMCP(name="discord-decision-mcp")
# Tool 등록
mcp.tool()(discord_ask_decision)
mcp.tool()(discord_notify)
mcp.tool()(discord_report_progress)
mcp.tool()(discord_check_pending)
mcp.tool()(discord_read_inbox)
mcp.tool()(discord_clear_inbox)
```

**실행 방법**:
```bash
discord-mcp  # 또는 python -m discord_mcp.server
```

### 3.2 설정 관리 (`config.py`)

**역할**: 환경변수에서 설정값 로드

| 환경변수 | 설명 | 기본값 |
|----------|------|--------|
| `DISCORD_BOT_TOKEN` | Discord Bot Token ("Bot " 접두사 포함) | 필수 |
| `DISCORD_CHANNEL_ID` | 기본 질문 채널 ID | 필수 |
| `PROJECT_NAME` | question_id 생성에 사용 | "project" |
| `PENDING_DIR` | 상태 파일 저장 경로 | `~/.claude/pending_decisions` |
| `POLL_INTERVAL_SECONDS` | Discord polling 간격 (초) | 5 |

### 3.3 Discord API 클라이언트 (`bot/`)

#### 3.3.1 REST API 클라이언트 (`client.py`)

**역할**: Discord REST API 호출 (httpx 기반)

**주요 메서드**:
```python
class DiscordClient:
    async def send_message(channel_id, content, embeds=None)
    async def get_messages(channel_id, after=None, limit=50)
    async def create_thread(channel_id, name, first_message)
    async def archive_thread(thread_id)
```

**특징**:
- Rate limit 자동 처리 (429 응답 시 재시도)
- 싱글턴 패턴 (`get_client()`)

#### 3.3.2 WebSocket 게이트웨이 (`gateway.py`)

**역할**: Discord Gateway WebSocket 연결 (수신 전용)

**특징**:
- MESSAGE_CREATE 이벤트 실시간 수신
- Polling 방식의 지연을 5초 → 즉시로 단축
- Gateway 없이도 시스템 정상 동작 (Polling fallback)
- 자동 재연결 (Exponential backoff)

```python
class GatewayClient:
    async def run()     # 이벤트 수신 시작
    async def stop()    # 연결 종료
```

### 3.4 결정 요청 관리 (`decision/`)

#### 3.4.1 DecisionManager (`manager.py`)

**역할**: 결정 요청의 전체 생명주기 조율

```python
class DecisionManager:
    async def ask(question, context, options, timeout_seconds, thread_id) -> PollResult
    async def restore_pending() -> list[DecisionState]
```

**흐름**:
1. 중복 질문 확인
2. Thread 생성 (또는 기존 Thread 재사용)
3. 상태 파일 생성 (`~/.claude/pending_decisions/{question_id}.json`)
4. Poller 실행하여 응답 대기
5. SIGHUP 시그널 핸들러로 disconnected 상태 표시

#### 3.4.2 DecisionPoller (`poller.py`)

**역할**: Discord 채널을 polling하여 응답 대기

```python
class DecisionPoller:
    async def wait(state: DecisionState) -> PollResult
```

**특징**:
- 기본값: 무한 대기 (`timeout_seconds=None`)
- tmux pane에 실시간 대기 상태 표시 (ANSI escape)
- 모호한 응답 시 최대 2회 재질문

#### 3.4.3 응답 파서 (`parser.py`)

**역할**: 사용자 Discord 응답 파싱

**지원 패턴**:
- 선택지 매칭: "A", "a", "A번", "A로 해줘", "1", "1번"
- 긍정/부정: "yes", "네", "예", "no", "아니요"
- 자연어: 15자 이상 또는 한글 3자 이상

```python
def parse_response(text: str, options: list[str]) -> ParseResult
def build_clarify_message(...) -> str  # 재질문 메시지 생성
```

#### 3.4.4 상태 저장소 (`state.py`)

**역할**: 결정 요청 상태를 JSON 파일로 영속화

**상태 파일 위치**: `~/.claude/pending_decisions/{question_id}.json`

```python
class DecisionState(BaseModel):
    question_id: str
    project: str
    question: str
    context: str
    options: list[str]
    timeout_seconds: float | None
    thread_id: str
    message_id: str
    asked_at: str
    status: Literal["pending", "disconnected", "resolved", "aborted", "timeout"]
    clarify_attempts: int
    resolved_at: str | None
    resolution: str | None
    selected_option: str | None

class StateStore:
    def save(state: DecisionState)
    def load(question_id: str) -> DecisionState | None
    def load_all_pending() -> list[DecisionState]
    def resolve(question_id, resolution, selected_option)
    def is_duplicate(question: str) -> bool
```

### 3.5 MCP Tools (`tools/`)

| Tool | 블로킹 | 설명 |
|------|--------|------|
| `discord_ask_decision` | ✅ | 사용자 결정 요청 |
| `discord_notify` | ❌ | 진행 상황 알림 |
| `discord_report_progress` | ❌ | 작업 완료 리포트 |
| `discord_check_pending` | ❌ | 미해결 질문 확인 |
| `discord_read_inbox` | ❌ | Inbox 메시지 조회 |
| `discord_clear_inbox` | ❌ | Inbox 메시지 삭제 |

### 3.6 감시 데몬 (`daemon/`)

#### 3.6.1 DiscordWatcher (`watcher.py`)

**역할**: Discord 채널을 감시하여 새 메시지를 inbox 파일에 기록

**실행 방법**:
```bash
discord-watch --interval 10
# 또는
tmux new-session -d -s discord-watch 'uv run discord-watch'
```

**특징**:
- 지정된 채널(들)을 주기적으로 polling
- 새로운 사용자 메시지 감지 시 inbox에 기록
- tmux pane에 상태 표시

#### 3.6.2 InboxStore (`inbox.py`)

**역할**: Discord 메시지를 저장하는 JSON 파일 기반 저장소

**Inbox 파일 위치**: `~/.claude/discord_inbox.json`

```python
class InboxMessage:
    message_id: str
    channel_id: str
    thread_id: str | None
    author: str
    author_id: str
    content: str
    timestamp: str
    read: bool

class InboxStore:
    def add_message(msg: InboxMessage)
    def get_unread() -> list[InboxMessage]
    def mark_read(message_id: str)
    def clear_read()  # 읽은 메시지 삭제
```

---

## 4. 데이터 흐름도

### 4.1 결정 요청 흐름

```
┌─────────────────┐
│  Claude Code    │
└────────┬────────┘
         │ discord_ask_decision()
         ▼
┌─────────────────────────────────────┐
│  MCP Server (server.py)             │
│  ┌───────────────────────────────┐  │
│  │ DecisionManager.ask()         │  │
│  │  1. 중복 확인                  │  │
│  │  2. Thread 생성               │  │
│  │  3. 상태 파일 저장             │  │
│  └───────────────┬───────────────┘  │
└──────────────────┼──────────────────┘
                   ▼
┌─────────────────────────────────────┐
│  DecisionPoller.wait()              │
│  ┌───────────────────────────────┐  │
│  │ Polling 루프                   │  │
│  │  1. tmux 상태 업데이트         │  │
│  │  2. Discord API 호출          │  │
│  │  3. 응답 파싱                  │  │
│  │  4. 모호하면 재질문            │  │
│  └───────────────┬───────────────┘  │
└──────────────────┼──────────────────┘
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
┌───────────────────┐  ┌──────────────────┐
│  Discord REST API │  │  Discord Thread  │
│    (client.py)    │  │                  │
└───────────────────┘  └────────┬─────────┘
                                 │
                        ┌────────▼────────┐
                        │  사용자 응답    │
                        └────────┬────────┘
                                 ▼
                        ┌─────────────────┐
                        │  parser.py      │
                        │  - 선택지 매칭  │
                        │  - 모호성 감지  │
                        └────────┬────────┘
                                 ▼
                        ┌─────────────────┐
                        │  store.resolve()│
                        └────────┬────────┘
                                 ▼
                        ┌─────────────────┐
                        │  PollResult     │
                        │  반환           │
                        └─────────────────┘
```

### 4.2 감시 데몬 흐름

```
┌─────────────────────────────────────────────┐
│  DiscordWatcher (daemon/watcher.py)         │
│  ┌───────────────────────────────────────┐  │
│  │ 1. 초기 메시지 ID 설정                 │  │
│  │ 2. 주기적 Polling (기본 10초)         │  │
│  │ 3. 새 메시지 감지                     │  │
│  │ 4. InboxStore.add_message()           │  │
│  └───────────────────┬───────────────────┘  │
└──────────────────────┼──────────────────────┘
                       ▼
┌─────────────────────────────────────────────┐
│  ~/.claude/discord_inbox.json               │
│  {                                          │
│    "last_message_id": "...",                │
│    "messages": [                            │
│      { "message_id": "...", ... }           │
│    ]                                        │
│  }                                          │
└──────────────────────┬──────────────────────┘
                       ▲
                       │ discord_read_inbox()
┌──────────────────────┴──────────────────────┐
│  Claude Code                                │
└─────────────────────────────────────────────┘
```

### 4.3 세션 복원 흐름

```
┌─────────────────────────────────────────────┐
│  Claude Code 세션 시작                      │
└──────────────────────┬──────────────────────┘
                       ▼
┌─────────────────────────────────────────────┐
│  discord_check_pending()                    │
└──────────────────────┬──────────────────────┘
                       ▼
┌─────────────────────────────────────────────┐
│  DecisionManager.restore_pending()          │
│  ┌───────────────────────────────────────┐  │
│  │ 1. ~/.claude/pending_decisions/*.json │  │
│  │ 2. Discord API로 Thread 확인          │  │
│  │ 3. 답변 있으면 → 자동 해결            │  │
│  │ 4. 답변 없으면 → 재시작 알림          │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

---

## 5. MCP 도구 목록

### 5.1 discord_ask_decision

**설명**: 사용자 결정이 필요할 때 Discord Thread에 질문 전송 후 응답 대기 (블로킹)

**파라미터**:
| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `question` | string | ✅ | 질문 내용 |
| `context` | string | ✅ | 현재 작업 상황 |
| `options` | string[] | ❌ | 선택지 목록 (빈 배열이면 자유 응답) |
| `timeout_seconds` | float | ❌ | 대기 Timeout (null이면 무한 대기) |
| `thread_id` | string | ❌ | 기존 Thread ID (null이면 새 Thread 생성) |

**반환값**:
```json
{
  "success": true,
  "answer": "A) 지금 실행",
  "selected_option": "A) 지금 실행",
  "question_id": "project_20260301_abc123",
  "timed_out": false,
  "aborted": false
}
```

### 5.2 discord_notify

**설명**: 진행 상황을 Discord에 알림 (논블로킹)

**파라미터**:
| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `message` | string | ✅ | 알림 메시지 |
| `level` | string | ❌ | info/warning/success/error (기본값: info) |
| `thread_id` | string | ❌ | 전송할 Thread ID (null이면 기본 채널) |

### 5.3 discord_report_progress

**설명**: 작업 완료 또는 단계 완료 시 결과 리포트 (논블로킹)

**파라미터**:
| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `title` | string | ✅ | 리포트 제목 |
| `summary` | string | ✅ | 작업 결과 요약 |
| `details` | string[] | ❌ | 세부 항목 목록 |
| `thread_id` | string | ❌ | 전송할 Thread ID |

### 5.4 discord_check_pending

**설명**: 세션 시작 시 미해결 질문 확인 (논블로킹)

**파라미터**: 없음

**반환값**:
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

### 5.5 discord_read_inbox

**설명**: Inbox에 저장된 메시지 조회 (논블로킹)

**파라미터**:
| 이름 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `unread_only` | boolean | true | 읽지 않은 메시지만 반환 |
| `mark_read` | boolean | false | 조회한 메시지를 읽음으로 표시 |

### 5.6 discord_clear_inbox

**설명**: Inbox 메시지 삭제 (논블로킹)

**파라미터**:
| 이름 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `read_only` | boolean | true | 읽은 메시지만 삭제 |

---

## 6. 의존성 정보

### 6.1 핵심 의존성

| 패키지 | 버전 | 용도 |
|--------|------|------|
| `fastmcp` | >= 0.1.0 | MCP 서버 프레임워크 |
| `httpx` | >= 0.27.0 | 비동기 HTTP 클라이언트 |
| `websockets` | >= 12.0 | WebSocket 클라이언트 |
| `python-dotenv` | >= 1.0.0 | 환경변수 로드 |
| `pydantic` | >= 2.0.0 | 데이터 모델 검증 |
| `anyio` | >= 4.0.0 | 비동기 실행 |

### 6.2 개발 의존성

| 패키지 | 용도 |
|--------|------|
| `pytest` | 테스트 프레임워크 |
| `pytest-asyncio` | 비동기 테스트 지원 |
| `pytest-mock` | Mock 지원 |
| `respx` | httpx mocking |

### 6.3 CLI 명령어

```bash
discord-mcp      # MCP 서버 실행
discord-watch    # 감시 데몬 실행
```

---

## 7. 상태 파일 형식

### 7.1 결정 상태 파일

**위치**: `~/.claude/pending_decisions/{question_id}.json`

```json
{
  "question_id": "project_20260301_abc123",
  "project": "my-project",
  "question": "DB 마이그레이션을 실행할까요?",
  "context": "v1→v2 스키마 변경",
  "options": ["A) 지금 실행", "B) 스테이징 먼저", "C) 보류"],
  "timeout_seconds": null,
  "thread_id": "1234567890",
  "message_id": "0987654321",
  "asked_at": "2026-03-01T10:30:00Z",
  "status": "pending",
  "clarify_attempts": 0,
  "resolved_at": null,
  "resolution": null,
  "selected_option": null
}
```

### 7.2 Inbox 파일

**위치**: `~/.claude/discord_inbox.json`

```json
{
  "last_message_id": "1234567890",
  "messages": [
    {
      "message_id": "1234567890",
      "channel_id": "1234567890",
      "thread_id": null,
      "author": "username",
      "author_id": "1234567890",
      "content": "메시지 내용",
      "timestamp": "2026-03-01T00:00:00Z",
      "read": false
    }
  ]
}
```

---

## 8. 아키텍처 원칙

### 8.1 설계 원칙

1. **싱글톤 패턴**: DiscordClient, StateStore, InboxStore는 모듈 레벨 싱글턴
2. **상태 영속화**: 모든 결정 요청 상태는 파일로 영속화
3. **무한 대기 기본값**: Claude가 독단적으로 진행하지 않도록 timeout 기본값은 None
4. **재질문 제한**: 모호한 응답은 최대 2회까지만 재질문
5. **Rate Limit 처리**: Discord API 429 응답 시 자동 대기 후 재시도

### 8.2 에러 handling

| 상황 | 처리 방법 |
|------|----------|
| Discord API 429 | 자동 대기 후 재시도 (최대 5회) |
| WebSocket 연결 끊김 | Exponential backoff로 재연결 |
| 응답 파싱 실패 | 최대 2회 재질문 후 중단 |
| Timeout 발생 | 작업 중단 알림 후 aborted 상태 |
| 세션 끊김 (SIGHUP) | disconnected 상태로 저장 |

---

*문서 버전: 1.0.0*
*마지막 수정: 2026-03-01*
