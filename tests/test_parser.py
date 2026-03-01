"""tests/test_parser.py — discord_mcp.decision.parser 테스트"""

import pytest
from discord_mcp.decision.parser import parse_response


OPTIONS_ABC = ["A) 지금 바로 실행", "B) 스테이징 먼저", "C) 보류"]
OPTIONS_YN  = ["A) 진행", "B) 취소"]


class TestOptionMatching:
    """선택지 매칭 테스트."""

    def test_single_letter(self):
        r = parse_response("A", OPTIONS_ABC)
        assert r.is_clear
        assert r.selected_option == OPTIONS_ABC[0]

    def test_letter_with_suffix(self):
        for text in ["A번", "A)", "A. ", "A로 해줘", "a"]:
            r = parse_response(text, OPTIONS_ABC)
            assert r.is_clear, f"Failed for: {text!r}"
            assert r.selected_option == OPTIONS_ABC[0]

    def test_number_selection(self):
        r = parse_response("2번", OPTIONS_ABC)
        assert r.is_clear
        assert r.selected_option == OPTIONS_ABC[1]

    def test_b_option(self):
        r = parse_response("B", OPTIONS_ABC)
        assert r.is_clear
        assert r.selected_option == OPTIONS_ABC[1]

    def test_c_option(self):
        r = parse_response("C로 진행해줘", OPTIONS_ABC)
        assert r.is_clear
        assert r.selected_option == OPTIONS_ABC[2]


class TestYesNo:
    """2개 선택지 Yes/No 테스트."""

    def test_yes_responses(self):
        for text in ["yes", "y", "네", "예", "맞아", "확인", "ok", "ㅇㅇ"]:
            r = parse_response(text, OPTIONS_YN)
            assert r.is_clear, f"Failed for: {text!r}"
            assert r.selected_option == OPTIONS_YN[0]

    def test_no_responses(self):
        for text in ["no", "n", "아니", "아니요", "취소", "보류"]:
            r = parse_response(text, OPTIONS_YN)
            assert r.is_clear, f"Failed for: {text!r}"
            assert r.selected_option == OPTIONS_YN[1]


class TestAmbiguous:
    """모호한 응답 테스트."""

    def test_ambiguous_korean(self):
        for text in ["모르겠어", "잘 모르겠는데", "흠...", "음", "글쎄"]:
            r = parse_response(text, OPTIONS_ABC)
            assert not r.is_clear, f"Should be ambiguous: {text!r}"

    def test_too_short(self):
        r = parse_response("?", OPTIONS_ABC)
        assert not r.is_clear

    def test_no_match_with_options(self):
        r = parse_response("일단 생각해볼게요", OPTIONS_ABC)
        assert not r.is_clear


class TestFreeText:
    """자유 텍스트 응답 (선택지 없음) 테스트."""

    def test_free_text_clear(self):
        r = parse_response("지금 바로 배포해줘", [])
        assert r.is_clear
        assert r.answer == "지금 바로 배포해줘"
        assert r.selected_option is None

    def test_free_text_short_ambiguous(self):
        r = parse_response("음", [])
        assert not r.is_clear
