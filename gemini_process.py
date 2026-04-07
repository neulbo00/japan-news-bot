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
아래 수집된 뉴스들을 바탕으로, 오늘의 뉴스 브리핑 기사 1편을 한국어로 작성해줘.

[작성 규칙]
1. 한국·일본 관련 뉴스를 가장 먼저, 가장 자세하게 다룰 것 (없으면 생략)
2. 나머지는 오늘 일본의 주요 뉴스로 채울 것
3. 전체 분량: 뉴스당 2~4문장, 총 800~1500자 (한국어 기준)
4. 문체: 신문 브리핑 스타일 — 객관적이고 간결하게
5. 중복/유사 뉴스는 하나로 합쳐서 정리할 것

[수집된 뉴스]
=== 한국·일본 관련 뉴스 ===
{korea_news}

=== 일본 주요 뉴스 ===
{general_news}

[응답 형식] 반드시 아래 JSON으로만 응답하고 다른 텍스트는 절대 포함하지 마:
{{
  "title": "브리핑 제목 (예: 4월 7일 일본 뉴스 브리핑)",
  "lead": "오늘 브리핑의 핵심을 1~2문장으로 요약",
  "has_korea_news": true 또는 false,
  "korea_section": [
    {{"headline": "소제목", "body": "2~4문장 설명"}}
  ],
  "japan_section": [
    {{"headline": "소제목", "body": "1~3문장 설명"}}
  ],
  "labels": ["브리핑", "일본뉴스"]
}}
"""


def _format_news_for_prompt(articles, max_items=8):
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
    korea_text   = _format_news_for_prompt(news_dict.get("korea", []),   max_items=6)
    general_text = _format_news_for_prompt(news_dict.get("general", []), max_items=8)
    now   = datetime.now()
    today = f"{now.month}월 {now.day}일"

    prompt = BRIEFING_PROMPT.format(
        korea_news=korea_text,
        general_news=general_text,
    ).replace("브리핑 제목 (예: 4월 7일 일본 뉴스 브리핑)",
               f"브리핑 제목 (예: {today} 일본 뉴스 브리핑)")

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
