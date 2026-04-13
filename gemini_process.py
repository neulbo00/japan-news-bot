import json
import os
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

STORY_HISTORY_FILE = os.path.join(os.path.dirname(__file__), "story_history.json")
MAX_HISTORY_ENTRIES = 4  # 최근 4회 = 2일분

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-3.1-flash-lite-preview:generateContent?key=" + (GEMINI_API_KEY or "")
)

BRIEFING_PROMPT = """
당신은 도쿄에서 활동하는 한국인 저널리스트로서 일본 뉴스를 한국어로 정리하는 뉴스 에디터입니다.
여러 일본 매체(Yahoo Japan, NHK, Google News 등)에서 수집한 뉴스입니다.

[방향성]
- 메인 타겟: 재일 한국인 및 한일 관계에 관심 있는 독자
- 부가 타겟: 일본 뉴스의 전반적 흐름 파악
- 한국어로 자연스럽게 작성하되 전문성과 신뢰감이 느껴지도록

[작성 규칙]
1. 한국 관련 뉴스가 있으면 별도 섹션으로 구성, 없으면 생략. "없음" 같은 표현 사용 금지
2. 한국 관련 뉴스가 없으면 korea_section은 빈 배열로 하고 has_korea_news는 false
3. 각 뉴스의 핵심을 파악해 중복·유사 기사는 하나로 통합
4. 리드: 이날 브리핑의 핵심을 한눈에 파악할 수 있게, 간결하게 작성
5. 기사 분량: 한국관련 3~4문장 / 일반뉴스 1~2문장
6. 제목은 내용을 잘 반영해 작성
7. 시제는 브리핑 작성 시점(지금 이 순간)을 기준으로 판단해서 자연스럽게 사용:
   - 방금 발생했거나 현재 진행 중인 사건 → "…하고 있다", "…하는 중이다"
   - 이미 완료된 사실 → "…했다", "…한 것으로 알려졌다"
   - 앞으로 예정된 일 → "…할 예정이다", "…할 방침이다"
   - 같은 문단 안에서 시제를 뒤섞지 말 것

[지명·인명 표기 기준] ※ 반드시 준수
- 일본 지명은 현지 발음(히라가나 읽기) 기준으로 한국어 표기. 한자 음독(한국식) 절대 사용 금지.
  예시(올바른 표기): 東京→도쿄, 大阪→오사카, 京都→교토, 名古屋→나고야,
        横浜→요코하마, 札幌→삿포로, 福岡→후쿠오카, 広島→히로시마,
        神戸→고베, 仙台→센다이, 渋谷→시부야, 新宿→신주쿠
  예시(틀린 표기): 동경(✗), 대판(✗), 경도(✗), 명고옥(✗)
- 일본 인명도 반드시 현지 발음 기준으로 표기 (예: 石破茂→이시바 시게루, 한자 음독 금지)
- 일본 기업·단체명도 공식 한국어명이 있으면 사용, 없으면 발음 기준으로 표기

[이전 브리핑 주요 기사 — 최근 4회(2일분)]
{history}
※ 오늘 뉴스에 이전 기사와 같은 테마가 있으면 "앞서 보도한 X 관련, 오늘은 Y가 확인됐습니다" 형태로 연속성 있게 서술하세요.
※ 관련 없는 이전 기사는 무시하세요.

[수집된 뉴스]
=== 한국·한일 관련 뉴스 (별도 섹션 구성) ===
{korea_news}

=== 일본 일반 뉴스 ===
{general_news}

[답변 형식] 마크다운 없이 JSON으로만 답하고 설명 텍스트는 절대 포함하지 말 것:
{{
  "title": "날짜 없이 핵심 내용만 담은 짧은 부제목 (예: '미·이란 협상 개시 및 주요 사회 소식')",
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


def _load_story_history():
    """story_history.json 로드. 없으면 빈 리스트 반환"""
    if os.path.exists(STORY_HISTORY_FILE):
        try:
            with open(STORY_HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_story_history(briefing, today, slot):
    """이번 브리핑 헤드라인을 story_history.json에 저장 (최근 4회 유지)"""
    history = _load_story_history()

    headlines = []
    for item in (briefing.get("korea_section") or []):
        headlines.append({
            "type": "한국관련",
            "headline": item.get("headline", ""),
            "summary": (item.get("body") or "")[:80],
        })
    for item in (briefing.get("japan_section") or []):
        headlines.append({
            "type": "일본뉴스",
            "headline": item.get("headline", ""),
            "summary": (item.get("body") or "")[:80],
        })

    history.append({"date": today, "slot": slot, "headlines": headlines})
    history = history[-MAX_HISTORY_ENTRIES:]  # 최근 4회만 유지

    with open(STORY_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"[히스토리] story_history.json 저장 완료 ({len(history)}회 보관)")


def _format_history_for_prompt(history):
    """이전 브리핑 히스토리를 프롬프트용 텍스트로 변환"""
    if not history:
        return "없음 (첫 번째 브리핑)"
    lines = []
    for entry in history:
        lines.append(f"■ {entry['date']} {entry['slot']} 브리핑")
        for h in entry.get("headlines", []):
            lines.append(f"  [{h['type']}] {h['headline']} — {h['summary']}")
    return "\n".join(lines)


def _format_news_for_prompt(articles):
    """뉴스 기사를 프롬프트용 텍스트로 변환 (갯수 상한 없음)"""
    if not articles:
        return "없음"
    lines = []
    for i, a in enumerate(articles, 1):
        pub = a.get("pubDate", "")
        content = (a.get("content") or "")[:200]
        lines.append(f"{i}. 【{a['source']}】{a['title']} ({pub})\n   {content}")
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
    korea_text   = _format_news_for_prompt(news_dict.get("korea", []))
    general_text = _format_news_for_prompt(news_dict.get("general", []))

    # JST(일본 표준시) 기준으로 날짜 문자열 생성
    now        = datetime.now(tz=JST)
    year_short = now.year % 100          # 2026 → 26
    today      = f"{year_short}년 {now.month}월 {now.day}일"

    # 이전 브리핑 히스토리 로드
    history      = _load_story_history()
    history_text = _format_history_for_prompt(history)
    print(f"[히스토리] 이전 브리핑 {len(history)}회 로드")

    prompt = BRIEFING_PROMPT.format(
        history=history_text,
        korea_news=korea_text,
        general_news=general_text,
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4},
    }

    try:
        res = requests.post(GEMINI_URL, json=payload, timeout=90)
        res.raise_for_status()
        raw  = res.json()
        text = raw["candidates"][0]["content"]["parts"][0]["text"].strip()
        text = _strip_json_fence(text)
        briefing = json.loads(text)

        # 타이틀을 Python(JST)에서 직접 덮어씀 → Gemini 월(月) 할루시네이션 방지
        # 형식: "26년 4월 11일 일본 저녁 뉴스 브리핑: [Gemini 부제목]"
        gemini_subtitle = briefing.get("title", "주요 뉴스")
        briefing["title"] = f"{today} 일본 {slot} 뉴스 브리핑: {gemini_subtitle}"

        print(f"[Gemini] 브리핑 생성 완료: {briefing['title']}")

        # 이번 브리핑 헤드라인을 히스토리에 저장
        _save_story_history(briefing, today, slot)

        return briefing
    except Exception as e:
        print(f"[Gemini 오류] 브리핑 생성 실패: {e}")
        return None
