"""
discord_mcp/decision/parser.py

사용자의 Discord 응답을 파싱하여 구조화된 결과를 반환한다.
선택지 매칭, 자연어 파싱, 모호성 감지를 처리한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ParseResult:
    """파싱 결과."""
    is_clear: bool               # 명확하게 파싱됐는지
    answer: str                  # 원본 응답 텍스트
    selected_option: str | None  # 매칭된 선택지 (A/B/C 등)
    interpreted: str             # Claude가 해석한 내용 (재확인용)


# 선택지 패턴: A, a, 1, 1번, "A번", "A로 해줘" 등
_OPTION_PATTERNS = [
    r"^([A-Za-z])\s*[번호]?\s*$",                    # "A", "a", "A번"
    r"^([A-Za-z])[)\.\s]",                           # "A)", "A. ", "A "
    r"([A-Za-z])\s*(?:로|으로|번|호)\s*(?:해|진행|실행|선택)",  # "A로 해줘"
    r"^(\d+)\s*[번호]?\s*$",                          # "1", "2번"
    r"^(\d+)[)\.\s]",                                # "1)", "2. "
]

# 명확한 긍정/부정
_YES = re.compile(r"^(yes|y|네|예|맞아|맞습니다|확인|ok|ㅇㅇ|ㄴㄴ)$", re.I)
_NO  = re.compile(r"^(no|n|아니|아니요|아니오|취소|cancel|보류)$", re.I)

# 모호성 키워드
_AMBIGUOUS = re.compile(
    r"(모르겠|잘 모르|뭔가|어떡|고민|글쎄|흠+|음+|어...|잠깐)", re.I
)


def parse_response(
    text: str,
    options: list[str],
) -> ParseResult:
    """
    사용자 응답을 파싱한다.

    Args:
        text: 사용자 응답 원문
        options: 질문에 제시된 선택지 목록 (["A) ...", "B) ...", "C) ..."])

    Returns:
        ParseResult
    """
    cleaned = text.strip()

    # 1. 선택지 직접 매칭
    matched = _match_option(cleaned, options)
    if matched:
        return ParseResult(
            is_clear=True,
            answer=cleaned,
            selected_option=matched,
            interpreted=f"선택: {matched}",
        )

    # 2. 명확한 긍정/부정 (선택지가 2개인 경우)
    if len(options) == 2:
        if _YES.match(cleaned):
            return ParseResult(
                is_clear=True,
                answer=cleaned,
                selected_option=options[0],
                interpreted=f"긍정 → {options[0]}",
            )
        if _NO.match(cleaned):
            return ParseResult(
                is_clear=True,
                answer=cleaned,
                selected_option=options[1],
                interpreted=f"부정 → {options[1]}",
            )

    # 3. 자연어 응답 (선택지 없는 자유 응답)
    if not options:
        return ParseResult(
            is_clear=True,
            answer=cleaned,
            selected_option=None,
            interpreted=cleaned[:100],
        )

    # 4. 긴 텍스트는 자유 명령으로 처리 (15자 이상 또는 한글 문장)
    if len(cleaned) >= 15 or re.search(r'[가-힣]{3,}', cleaned):
        return ParseResult(
            is_clear=True,
            answer=cleaned,
            selected_option=None,
            interpreted=f"자유 명령: {cleaned[:100]}",
        )

    # 5. 모호성 감지
    if _AMBIGUOUS.search(cleaned) or len(cleaned) < 3:
        return ParseResult(
            is_clear=False,
            answer=cleaned,
            selected_option=None,
            interpreted="응답이 모호합니다",
        )

    # 6. 선택지가 있는데 매칭 안 됨 → 자유 텍스트로 처리 (불명확 대신)
    return ParseResult(
        is_clear=True,
        answer=cleaned,
        selected_option=None,
        interpreted=f"선택지 외 응답: {cleaned[:100]}",
    )


def _match_option(text: str, options: list[str]) -> str | None:
    """선택지 중 하나와 매칭되는지 확인한다."""
    text_upper = text.upper().strip()

    for pattern in _OPTION_PATTERNS:
        m = re.search(pattern, text, re.I)
        if not m:
            continue
        token = m.group(1).upper()

        # 알파벳 선택지 (A/B/C)
        for opt in options:
            opt_key = opt.strip()[0].upper()
            if opt_key == token:
                return opt

        # 숫자 선택지 (1/2/3)
        try:
            idx = int(token) - 1
            if 0 <= idx < len(options):
                return options[idx]
        except ValueError:
            pass

    # 선택지 전체 텍스트 포함 여부
    for opt in options:
        opt_clean = re.sub(r"^[A-Za-z\d][)\.\s]+", "", opt).strip()
        if opt_clean and opt_clean.lower() in text.lower():
            return opt

    return None


def build_clarify_message(
    original_question: str,
    user_answer: str,
    interpreted: str,
    attempt: int,
    max_attempts: int,
    options: list[str],
) -> str:
    """모호한 응답에 대한 재질문 메시지를 생성한다."""
    options_text = "\n".join(f"  {o}" for o in options) if options else "  (자유 응답)"

    return (
        f"응답을 정확히 이해하지 못했습니다. 다시 확인해주세요.\n\n"
        f"**받은 응답:** `{user_answer}`\n"
        f"**이해한 내용:** {interpreted}\n\n"
        f"**선택지:**\n{options_text}\n\n"
        f"선택지 번호 또는 문자(A/B/C)로 답해주시거나, 다시 설명해주세요.\n"
        f"*(재질문 {attempt}/{max_attempts})*"
    )
