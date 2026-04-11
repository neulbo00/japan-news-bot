import json
import re
import requests
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
    JST = ZoneInfo("Asia/Tokyo")
except ImportError:
    import pytz
    JST = pytz.timezone("Asia/Tokyo")

from config import GEMINI_API_KEY

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-3.1-flash-lite-preview:generateContent?key=" + (GEMINI_API_KEY or "")
)

BRIEFING_PROMPT = """
당신은 도쿄에서 활동하는 한국인 저널리스트로서 일본 뉴스를 한국어로 정리하는 뉴스 에디터입니다.
여러 일본 매체(Yahoo Japan, NHK, Google News 등)에서 수집한 뉴스입니다.

[방향성]
- 메인 타겟: **재일 한국인 및 한일 관계에 관심 있는 독자**
- 부가 타겟: 일본 뉴스의 전반적 흐름 파악
- 한국어로 자연스럽게 작성하되 전문성과 신뢰감이 느껴지도록

[작성 규칙]
1. 한국 관련 뉴스가 있으면 별도 섹션으로 구성, 없으면 생략. "없음" 같은 표현 사용 금지
2. 한국 관련 뉴스가 없으면 korea_section은 빈 배열로 하고 has_korea_news는 false
3. 각 뉴스의 핵심을 파악해 중복·유사 기사는 하나로 통합
4. 리드: 이날 브리핑의 핵심을 한눈에 파악할 수 있게, 간결하게 작성
5. 기사 분량: 한국관련 3~4문장 / 일반뉴스 1~2문장
6. 제목은 내용을 잘 반영해 작성

[지명·인명 표기 기준] ※ 반드시 준수
- 일본 지명은 현지 발음(히라가나 읽기) 기준으로 한국어 표기. 한자 음돁(한국식) 절대 사용 금지.
  예시(올바른 표기): 東京→도쿄, 大阪→오사카, 京都→교토, 名古屋→나고야,
        横浜→요코하마, 札幌→삿포로, 福岡→후쿠오카, 広島→히로시마,
        神戸→고베, 仙台→센다이, 渋谷→시부야, 新宿→신주쿠
  예시(틀린 표기): 동경(✗), 대판(✗), 경도(✗), 명고옥(✗)
- 일본 인명도 반드시 현지 발음 기준으로 표기 (예: 石破茂→이시바 시게루, 한자 음돁 금지)
- 일본 기업·단체명도 공식 한국어명이 있으면 사용, 없으면 발음 기준으로 표기

[수집된 뉴스]
=== 한국·한일 관련 뉴스 (별도 섹션 구성) ===
{korea_news}

=== 일본 일반 뉴스 ===
{general_news}

[답변 형식] 마크다운 없이 JSON으로만 답하고 설명 텍스트는 절대 포함하지 말 것:
{{
  "title": "뉴스 브리핑 제목",
  "lead": "이번 브리핑의 핵심을 1~2문장으로 요약",
  "has_korea_news": true 또는 false,
  "korea_section": [
    {{"headline": "기사제목", "body": "3~4문장 본문 (한국 독자를 위한 상세 설명)"}}
  ],
  "japan_section": [
    {{"headline": "기사제목", "body": "1~2문장 본문"}}
  ],
  "labels": ["브리핑", "일본뉴스브리핑"]
}}
"""


def _format_news_for_prompt(articles, max_items=20):
    """뉴스 기사를 프롬프트용 텍스트로 변환"""
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


def generate_briefing(news_dict, slot="아침"):
    """
    수집된 뉴스 딕셔너리를 받아 Gemini로 브리핑 1편 생성.
    반환: {title, lead, has_korea_news, korea_section, japan_section, labels}
    실패 시 None
    """
    korea_text   = _format_news_for_prompt(news_dict.get("korea", []),   max_items=20)
    general_text = _format_news_for_prompt(news_dict.get("general", []), max_items=20)

    # JST(일본 표준시) 기준으로 날짜 문자열 생성
    now   = datetime.now(tz=JST)
    today = f"{now.month}월 {now.day}일"

    prompt = BRIEFING_PROMPT.format(
        korea_news=korea_text,
        general_news=general_text,
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

        # 타이틀을 Python(JST)에서 직접 덮어쓰으로써 Gemini 월(月) 할루시네이션 방지
        # 형식: "4월 11일 아침 브리핑 / [Gemini가 생성한 메인 타이틀]"
        gemini_title = briefing.get("title", "일본 뉴스 브리핑")
        briefing["title"] = f"{today} {slot} 브리핑 / {gemini_title}"

        print(f"[Gemini] 브리핑 생성 완료: {briefing['title']}")
        return briefing
    except Exception as e:
        print(f"[Gemini 오류] 브리핑 생성 실패: {e}")
        return None
