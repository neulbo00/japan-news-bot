import json
import re
import requests
from datetime import datetime
from config import GEMINI_API_KEY

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-3.1-flash-lite-preview:generateContent?key=" + (GEMINI_API_KEY or "")
)

BRIEFING_PROMPT = """
너는 일본에 거주하는 한국인 독자를 위해 일본 뉴스 브리핑을 작성하는 전문 에디터야.
아래는 일본 미디어(Yahoo Japan, NHK, Google News 일본판)에서 수집한 뉴스야.

[편집 방향]
- 메인 섹션: **일본 미디어가 한국을 어떻게 보고 있는가** (한일 외교, 한국 정치·경제·문화에 대한 일본의 시각)
- 서브 섹션: 오늘 일본 국내외 주요 뉴스 (정치·경제·사회·재해 등)
- 독자는 일본 거주 한국인 — 일본어는 이해하지만 한국어로 읽고 싶어 함

[작성 규칙]
1. 한국 관련 뉴스는 가장 먼저, 가장 자세하게. "일본에서 이렇게 보도했다"는 뉘앙스를 살릴 것
2. 한국 관련 뉴스가 없으면 korea_section은 빈 배열로 두고 has_korea_news는 false
3. 일본 뉴스는 오늘의 핵심 이슈 위주로, 중복·유사 뉴스는 하나로 통합
4. 문체: 신문 브리핑 스타일 — 간결하고 객관적, 과장 없이
5. 뉴스당 분량: 한국관련 3~4문장 / 일본뉴스 1~2문장
6. 제목은 오늘 날짜 포함

[수집된 뉴스]
=== 한국·일본 관련 뉴스 (일본 미디어 보도) ===
{korea_news}

=== 일본 주요 뉴스 ===
{general_news}

[응답 형식] 반드시 아래 JSON으로만 응답하고 다른 텍스트는 절대 포함하지 마:
{{
  "title": "날짜 포함 브리핑 제목 (예: {today} 일본 뉴스 브리핑)",
  "lead": "오늘 브리핑의 핵심을 1~2문장으로 요약",
  "has_korea_news": true 또는 false,
  "korea_section": [
    {{"headline": "소제목", "body": "3~4문장 설명 (일본 미디어의 시각 반영)"}}
  ],
  "japan_section": [
    {{"headline": "소제목", "body": "1~2문장 설명"}}
  ],
  "labels": ["브리핑", "일본뉴스"]
}}
"""


def _format_news_for_prompt(articles, max_items=10):
    """기사 목록을 프롬프트용 텍스트로 변환"""
    if not articles:
        return "없음"
    lines = []
    for i, a in enumerate(articles[:max_items], 1):
        content = (a.get("content") or "")[:200]
        lines.append(f"{i}. 【{a['source']}】{a['title']}\n   {content}")
    return "\n".join(lines)


def _strip_json_fence(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def generate_briefing(news_dict):
    """
    수집된 뉴스 딕셔너리를 받아 Gemini로 브리핑 1편 생성.
    반환: {title, lead, has_korea_news, korea_section, japan_section, labels}
    또는 실패 시 None
    """
    korea_text   = _format_news_for_prompt(news_dict.get("korea", []),   max_items=10)
    general_text = _format_news_for_prompt(news_dict.get("general", []), max_items=10)
    now   = datetime.now()
    today = f"{now.month}월 {now.day}일"

    prompt = BRIEFING_PROMPT.format(
        korea_news=korea_text,
        general_news=general_text,
        today=today,
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4},
    }

    try:
        res = requests.post(GEMINI_URL, json=payload, timeout=30)
        res.raise_for_status()
        raw  = res.json()
        text = raw["candidates"][0]["content"]["parts"][0]["text"].strip()
        text = _strip_json_fence(text)
        briefing = json.loads(text)
        print(f"[Gemini] 브리핑 생성 완료: {briefing.get('title', '(제목없음)')}")
        return briefing
    except Exception as e:
        print(f"[Gemini 실패] 브리핑 생성 오류: {e}")
        return None
