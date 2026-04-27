import json
import os
import re
import requests
import time
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


ENTITY_PROMPT = """
다음 뉴스 기사 목록에서 각 기사의 entity(개체명)를 추출해 JSON 배열로 반환하라.
기사 순서 그대로, 같은 개수로 반환할 것.

추출 항목:
- people: 등장 인물명 (일본인은 일본어 발음 기준 한국어 표기, 예: 이시바 시게루)
- organizations: 기업·정당·기관·단체명
- places: 지명 (일본 지명은 발음 기준 한국어, 예: 도쿄·오사카)
- numbers: [{{"value": "금액/수치", "context": "맥락"}}] 형태 (중요 수치만)
- topics: 핵심 주제 키워드 2~4개
- importance: 한국인 독자 관심도 1~5 정수
  (5=매우 중요 한일 직접 관련, 4=중요 한일 간접 관련, 3=보통, 2=낮음, 1=노이즈)

규칙:
- entity가 없는 항목은 빈 배열 [] (null/None 사용 금지)
- numbers가 없으면 []
- JSON 배열만 출력, 설명 텍스트 절대 불포함

기사 목록:
{articles_text}

[답변 형식] JSON 배열만:
[
  {{"people": [], "organizations": [], "places": [], "numbers": [], "topics": [], "importance": 3}},
  ...
]
"""

NEGATIVE_CONSTRAINT_TEMPLATE = """
⚠️ 아래 인명·조직명·지명은 절대 누락 금지. 원문 표현 그대로 사용할 것:
인명: {people}
조직: {organizations}
지명: {places}
"""


def _call_gemini(prompt: str, timeout: int = 90) -> str | None:
    """단일 Gemini 호출. 폴백 포함. 성공 시 텍스트 반환, 실패 시 None."""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2},
    }
    RETRY_WAIT = 30
    for model in GEMINI_MODELS:
        url = f"{GEMINI_BASE}/{model}:generateContent?key={GEMINI_API_KEY}"
        for attempt in range(1, 3):
            try:
                res = requests.post(url, json=payload, timeout=timeout)
                res.raise_for_status()
                raw = res.json()
                return raw["candidates"][0]["content"]["parts"][0]["text"].strip()
            except Exception as e:
                err = str(e)
                is_server_err = any(c in err for c in ["503", "timed out", "timeout"])
                is_rate_limit = "429" in err
                if is_server_err and attempt == 1:
                    print(f"[Gemini] {model} 재시도 ({err[:60]})")
                    time.sleep(RETRY_WAIT)
                elif is_server_err or is_rate_limit:
                    print(f"[Gemini] {model} 폴백 ({err[:60]})")
                    time.sleep(60)
                    break
                else:
                    print(f"[Gemini] 오류: {err[:80]}")
                    return None
    return None


def extract_entities(articles: list) -> list:
    """
    기사 리스트에 대해 batch Gemini 호출로 entity 추출.
    각 article에 'entities' 키를 추가한 새 리스트 반환.
    Gemini 실패 시 빈 entity 구조로 채워 반환.
    """
    empty_entity = {
        "people": [], "organizations": [], "places": [],
        "numbers": [], "topics": [], "importance": 3,
    }
    if not articles:
        return articles

    lines = []
    for i, a in enumerate(articles, 1):
        body = (a.get("full_text") or a.get("content") or "")[:500]
        lines.append(f"{i}. 제목: {a['title']}\n   내용: {body}")
    articles_text = "\n\n".join(lines)

    prompt = ENTITY_PROMPT.format(articles_text=articles_text)
    raw = _call_gemini(prompt, timeout=120)

    entity_list = []
    if raw:
        try:
            raw_clean = _strip_json_fence(raw)
            parsed = json.loads(raw_clean)
            if isinstance(parsed, list):
                entity_list = parsed
        except Exception as e:
            print(f"[Entity] JSON 파싱 실패: {e}")

    result = []
    for i, article in enumerate(articles):
        a = dict(article)
        if i < len(entity_list) and isinstance(entity_list[i], dict):
            ent = entity_list[i]
            a["entities"] = {
                "people":        ent.get("people") or [],
                "organizations": ent.get("organizations") or [],
                "places":        ent.get("places") or [],
                "numbers":       ent.get("numbers") or [],
                "topics":        ent.get("topics") or [],
                "importance":    ent.get("importance") or 3,
            }
        else:
            a["entities"] = dict(empty_entity)
        result.append(a)

    people_found = sum(len(a["entities"]["people"]) for a in result)
    print(f"[Entity] {len(result)}건 처리 완료 — 인명 {people_found}개 추출")
    return result


def _check_entity_missing(text: str, entities: dict) -> list:
    """브리핑 텍스트에서 누락된 entity 목록 반환 (people + organizations)."""
    missing = []
    for name in entities.get("people", []):
        if name and name not in text:
            missing.append(name)
    for org in entities.get("organizations", []):
        if org and org not in text:
            missing.append(org)
    return missing


def _build_negative_constraint(all_articles: list) -> str:
    """모든 기사의 entity를 모아 negative constraint 텍스트 생성."""
    people = []
    orgs = []
    places = []
    for a in all_articles:
        ent = a.get("entities", {})
        people.extend(ent.get("people", []))
        orgs.extend(ent.get("organizations", []))
        places.extend(ent.get("places", []))
    # 중복 제거
    people  = list(dict.fromkeys(p for p in people if p))
    orgs    = list(dict.fromkeys(o for o in orgs if o))
    places  = list(dict.fromkeys(p for p in places if p))
    if not (people or orgs or places):
        return ""
    return NEGATIVE_CONSTRAINT_TEMPLATE.format(
        people=", ".join(people) if people else "없음",
        organizations=", ".join(orgs) if orgs else "없음",
        places=", ".join(places) if places else "없음",
    )


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


def generate_briefing(news_dict, slot="아침", telegram_notify_fn=None):
    """
    수집된 뉴스 딕셔너리를 받아 Gemini로 브리핑 1편 생성.
    반환: {title, lead, has_korea_news, korea_section, japan_section, labels}
    실패 시 None

    telegram_notify_fn: entity 누락 경고용 send_message 함수 (선택)
    """
    # Gemini 전달 전: 연속보도(follow-up)를 후순위로 정렬 → 상한 초과 시 우선 trim
    korea_all   = sorted(news_dict.get("korea",   []), key=lambda x: x.get("is_followup", False))
    general_all = sorted(news_dict.get("general", []), key=lambda x: x.get("is_followup", False))
    korea_trim   = korea_all[:MAX_KOREA_FOR_GEMINI]
    general_trim = general_all[:MAX_GENERAL_FOR_GEMINI]
    if len(korea_all) > MAX_KOREA_FOR_GEMINI or len(general_all) > MAX_GENERAL_FOR_GEMINI:
        print(f"[Gemini] 입력 제한 적용: 한국관련 {len(korea_trim)}/{len(korea_all)}건, "
              f"일본뉴스 {len(general_trim)}/{len(general_all)}건")

    # ── Phase 2: entity 추출 (batch) ──────────────────────────────────────────
    all_trim = korea_trim + general_trim
    print(f"[Entity] {len(all_trim)}건 entity 추출 시작...")
    all_trim = extract_entities(all_trim)
    korea_trim   = all_trim[:len(korea_trim)]
    general_trim = all_trim[len(korea_trim):]

    # negative constraint 생성 (한국관련 기사 entity만 사용)
    neg_constraint = _build_negative_constraint(korea_trim)

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

    def _build_prompt(extra_constraint: str = "") -> str:
        base = BRIEFING_PROMPT.format(
            history=history_text,
            korea_news=korea_text,
            general_news=general_text,
        )
        if neg_constraint or extra_constraint:
            constraint_block = neg_constraint + extra_constraint
            # [답변 형식] 앞에 constraint 삽입
            return base.replace(
                "[답변 형식]",
                constraint_block + "\n[답변 형식]",
            )
        return base

    def _try_generate(prompt: str) -> dict | None:
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.4},
        }
        RETRY_WAIT = 30
        for model in GEMINI_MODELS:
            url = f"{GEMINI_BASE}/{model}:generateContent?key={GEMINI_API_KEY}"
            for attempt in range(1, 3):
                try:
                    res = requests.post(url, json=payload, timeout=90)
                    res.raise_for_status()
                    raw  = res.json()
                    text = raw["candidates"][0]["content"]["parts"][0]["text"].strip()
                    text = _strip_json_fence(text)
                    briefing = json.loads(text)
                    if model != GEMINI_MODELS[0]:
                        print(f"[Gemini] 폴백 모델 사용: {model}")
                    return briefing
                except Exception as e:
                    err = str(e)
                    is_server_err = any(c in err for c in ["503", "timed out", "timeout"])
                    is_rate_limit = "429" in err
                    if is_server_err and attempt == 1:
                        print(f"[Gemini 재시도] {model} — {RETRY_WAIT}초 후 ({e})")
                        time.sleep(RETRY_WAIT)
                    elif is_server_err or is_rate_limit:
                        print(f"[Gemini 폴백] {model} 실패, 60초 후 다음 모델")
                        time.sleep(60)
                        break
                    else:
                        print(f"[Gemini 오류] {e}")
                        return None
        print("[Gemini 오류] 모든 모델 실패")
        return None

    # ── 1차 생성 ──────────────────────────────────────────────────────────────
    briefing = _try_generate(_build_prompt())
    if briefing is None:
        return None

    # ── entity 누락 검증 (string match, 추가 Gemini 호출 없음) ───────────────
    briefing_text = json.dumps(briefing, ensure_ascii=False)
    all_entities = {}
    for a in korea_trim:
        for k in ("people", "organizations"):
            all_entities.setdefault(k, []).extend(a.get("entities", {}).get(k, []))
    missing = _check_entity_missing(briefing_text, all_entities)

    if missing:
        print(f"[Entity 검증] entity 누락 감지: {missing} — 재생성 시도")

        # ── 2차 생성: 누락 entity를 강조한 추가 제약 ──────────────────────
        extra = f"\n🚨 특히 다음 항목은 반드시 본문에 포함: {', '.join(missing)}\n"
        briefing2 = _try_generate(_build_prompt(extra_constraint=extra))
        if briefing2:
            briefing = briefing2
            # 재검증
            briefing_text2 = json.dumps(briefing2, ensure_ascii=False)
            still_missing = _check_entity_missing(briefing_text2, all_entities)
            if still_missing:
                print(f"[Entity 검증] 재생성 후에도 누락: {still_missing} — 현재 버전으로 게시합니다.")
            elif not still_missing:
                print("[Entity 검증] 재생성 후 누락 해소")

    # ── JMA 날씨 블록 추가 ───────────────────────────────────────────────────
    try:
        from weather_jma import get_today_weather, format_weather_block
        weather = get_today_weather()
        briefing["_weather"] = weather
        briefing["_weather_block"] = format_weather_block(weather, slot) if weather else ""
        if weather:
            print("[JMA] 날씨 블록 생성 완료")
        else:
            print("[JMA] 날씨 데이터 없음 — 블록 생략")
    except Exception as e:
        print(f"[JMA] 날씨 통합 오류: {e}")
        briefing["_weather"] = None
        briefing["_weather_block"] = ""

    # ── 타이틀 덮어쓰기 (Gemini 날짜 할루시네이션 방지) ─────────────────────
    gemini_subtitle = briefing.get("title", "주요 뉴스")
    briefing["title"] = f"{today} 일본 {slot} 뉴스 브리핑: {gemini_subtitle}"
    print(f"[Gemini] 브리핑 생성 완료: {briefing['title']}")

    # entity 메타데이터를 briefing에 저장 (Wiki 적재용)
    briefing["_korea_articles"] = korea_trim
    briefing["_general_articles"] = general_trim

    # 이번 브리핑 헤드라인을 히스토리에 저장
    _save_story_history(briefing, today, slot)

    return briefing
