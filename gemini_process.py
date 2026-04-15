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

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
# 모델 우선순위: 앞에서부터 순서대로 시도, 503/429 시 다음 모델로 폴백
GEMINI_MODELS = [
    "gemini-3.1-flash-lite-preview",  # 1순위: 무료 RPD 500
    "gemini-2.5-flash",               # 폴백: 503/timeout 시 자동 전환
]

# Gemini에 전달하는 기사 수 상한 (payload 과부하 방지)
# 저녁 브리핑은 하루치 기사가 쌓여 50~130건에 달해 90초 timeout 유발
MAX_KOREA_FOR_GEMINI   = 20  # 한국관련 최대 20건
MAX_GENERAL_FOR_GEMINI = 40  # 일반뉴스 최대 40건

BRIEFING_PROMPT = """
당신은 도쿄에서 활동하는 한국인 저널리스트로서 일본 뉴스를 한국어로 정리하는 뉴스 에디터입니다.
여러 일본 매체(Yahoo Japan, NHK, Google News 등)에서 수집한 뉴스입니다.

[독자]
- 메인: 재일 한국인, 한일 관계에 관심 있는 독자
- 한국어로 자연스럽게, 전문성과 신뢰감이 느껴지도록 작성

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[한일관련 섹션 선정 기준] ※ 이 기준을 엄격히 적용할 것
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 포함 (진짜 한일관련)
  - 한일 외교·정치: 정상회담, 외교장관 회담, 일본 정부의 한국 관련 공식 성명/조치
  - 한일 경제: 일본 기업·시장에서의 한국 기업/상품 동향, 한일 무역 분쟁·협력
  - 한일 안보: 독도, 위안부, 강제징용, 레이더 조사, GSOMIA, 북한 관련 한일 공조
  - 한국인의 일본 내 사건·사고 (재일교포 포함)
  - 일본 사회에서 K-콘텐츠·한국 문화가 구체적 사회현상으로 나타나는 경우
    (예: 한국어 학습 붐, 특정 K-드라마/영화 일본 흥행 1위, 한국 음식 일본 내 유행)

❌ 제외 (한국 언급만 있을 뿐 한일관련 아님)
  - 한국 내부 정치·사회·경제 사건 (일본에 직접 영향 없는 것)
  - 삼성·LG·현대 등 한국 기업의 글로벌 동향 (일본 시장과 무관한 것)
  - K-pop 그룹 공연·앨범·수상 소식 (일본 내 구체적 현상이 아닌 단순 언급)
  - 스포츠 기사에서 한국 선수·팀이 단순 언급된 것
  - "일본 매체가 보도했다"는 사실만으로 한일관련으로 분류하지 말 것

→ 위 기준에 맞는 한일관련 기사가 없으면 has_korea_news: false, korea_section: []
→ 억지로 한일관련 기사를 만들지 말 것

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[작성 규칙]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. 직접 인용(" ") 사용 금지 — 저널리스트 서술체로 자연스럽게 쓸 것
2. 구체 정보 필수: 인명(발음 기준 한국어), 수치, 날짜, 기업명 등을 명시
3. 하나의 기사 = 하나의 명확한 주제. 다른 주제를 억지로 묶지 말 것
4. 중복·유사 기사는 하나로 통합
5. 리드: 이날 핵심을 1~2문장으로, 간결하게
6. 기사 분량: 한국관련 3~4문장 / 일반뉴스 1~2문장
7. 시제는 브리핑 시점 기준으로 자연스럽게:
   - 진행 중 → "~하고 있다", "~중이다"
   - 완료 → "~했다", "~한 것으로 나타났다"
   - 예정 → "~할 예정이다", "~할 방침이다"
   - 같은 문단에서 시제 혼용 금지

[지명·인명 표기] ※ 반드시 준수
- 일본 지명: 현지 발음(히라가나) 기준 한국어 표기. 한자 음독 절대 금지
  (東京→도쿄, 大阪→오사카, 京都→교토, 名古屋→나고야, 横浜→요코하마)
  (틀린 표기: 동경✗, 대판✗, 경도✗)
- 일본 인명: 현지 발음 기준 (石破茂→이시바 시게루)
- 일본 기업·단체: 공식 한국어명 있으면 사용, 없으면 발음 기준

[이전 브리핑 — 최근 4회(2일분)]
{history}
※ 같은 테마 뉴스가 있으면 "앞서 보도한 X 관련, 오늘은 Y가 확인됐다" 형태로 연속성 있게 서술
※ 무관한 이전 기사는 무시

[수집된 뉴스]
=== 한국·한일 관련 후보 기사 (위 선정 기준으로 걸러서 사용) ===
{korea_news}

=== 일본 일반 뉴스 ===
{general_news}

[답변 형식] 마크다운 없이 JSON만, 설명 텍스트 절대 불포함:
{{
  "title": "날짜 없이 핵심 내용만 담은 짧은 부제목 (예: '미·이란 협상 재개 및 주요 사회 소식')",
  "lead": "이번 브리핑 핵심을 1~2문장으로 요약",
  "has_korea_news": true 또는 false,
  "korea_section": [
    {{"headline": "기사제목 (구체적 인명·사건명 포함)", "body": "3~4문장. 직접인용 금지. 구체적 수치·인명·날짜 포함"}}
  ],
  "japan_section": [
    {{"headline": "기사제목", "body": "1~2문장. 직접인용 금지"}}
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
    """뉴스 기사를 프롬프트용 텍스트로 변환"""
    if not articles:
        return "없음"
    lines = []
    for i, a in enumerate(articles, 1):
        pub = a.get("pubDate", "")
        content = (a.get("content") or "")[:200]
        tag = " [연속보도]" if a.get("is_followup") else ""
        lines.append(f"{i}. 【{a['source']}】{a['title']}{tag} ({pub})\n   {content}")
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
    # Gemini 전달 전: 연속보도(follow-up)를 후순위로 정렬 → 상한 초과 시 우선 trim
    korea_all   = sorted(news_dict.get("korea",   []), key=lambda x: x.get("is_followup", False))
    general_all = sorted(news_dict.get("general", []), key=lambda x: x.get("is_followup", False))
    korea_trim   = korea_all[:MAX_KOREA_FOR_GEMINI]
    general_trim = general_all[:MAX_GENERAL_FOR_GEMINI]
    if len(korea_all) > MAX_KOREA_FOR_GEMINI or len(general_all) > MAX_GENERAL_FOR_GEMINI:
        print(f"[Gemini] 입력 제한 적용: 한국관련 {len(korea_trim)}/{len(korea_all)}건, "
              f"일본뉴스 {len(general_trim)}/{len(general_all)}건")
    korea_text   = _format_news_for_prompt(korea_trim)
    general_text = _format_news_for_prompt(general_trim)

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

    import time

    RETRY_WAIT = 30  # 동일 모델 재시도 대기 (초)

    for model in GEMINI_MODELS:
        url = f"{GEMINI_BASE}/{model}:generateContent?key={GEMINI_API_KEY}"
        for attempt in range(1, 3):  # 모델당 최대 2회 시도
            try:
                res = requests.post(url, json=payload, timeout=90)
                res.raise_for_status()
                raw  = res.json()
                text = raw["candidates"][0]["content"]["parts"][0]["text"].strip()
                text = _strip_json_fence(text)
                briefing = json.loads(text)

                # 타이틀을 Python(JST)에서 직접 덮어씀 → Gemini 월(月) 할루시네이션 방지
                gemini_subtitle = briefing.get("title", "주요 뉴스")
                briefing["title"] = f"{today} 일본 {slot} 뉴스 브리핑: {gemini_subtitle}"

                if model != GEMINI_MODELS[0]:
                    print(f"[Gemini] 폴백 모델 사용: {model}")
                print(f"[Gemini] 브리핑 생성 완료: {briefing['title']}")

                # 이번 브리핑 헤드라인을 히스토리에 저장
                _save_story_history(briefing, today, slot)

                return briefing

            except Exception as e:
                err = str(e)
                is_server_err = any(code in err for code in ["503", "timed out", "timeout"])
                is_rate_limit = "429" in err

                if is_server_err and attempt == 1:
                    # 동일 모델 1회 재시도
                    print(f"[Gemini 재시도] {model} — {RETRY_WAIT}초 후 재시도 ({e})")
                    time.sleep(RETRY_WAIT)
                elif is_server_err or is_rate_limit:
                    # 다음 모델로 폴백 (60초 대기 후)
                    print(f"[Gemini 폴백] {model} 실패({e}), 60초 후 다음 모델 시도")
                    time.sleep(60)
                    break
                else:
                    print(f"[Gemini 오류] 브리핑 생성 실패: {e}")
                    return None

    print("[Gemini 오류] 모든 모델 실패")
    return None
