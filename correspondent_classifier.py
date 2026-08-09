"""
Phase 6 — Step 2: 도쿄 특파원 기사 Gemini 분류

도쿄발 기사를 4종으로 분류:
  value_korean_perspective  — 한국 시각·한일관계 해석  → Wiki 적재
  value_field_report        — 직접 취재(인터뷰·르포)  → Wiki 적재
  redundant_japan_media_quote — 일본 매체 받아쓰기      → 스킵
  redundant_press_release     — 정부·기업 보도자료       → 스킵

Phase 2(gemini_process.py)의 extract_entities 패턴 재사용.
기사 1~5건씩 배치 호출 → Gemini API 비용 최소화.

[변경 이력]
2026-04-29 v1: Phase 6 초기 구현
"""

import json
import os
import re
import time
import requests

from config import GEMINI_API_KEY

GEMINI_BASE   = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
]

CONFIDENCE_THRESHOLD = 0.70   # 이 이상만 채택
BATCH_SIZE           = 5      # 한 번에 분류할 기사 수

# ── 분류 프롬프트 ──────────────────────────────────────────────────────────────
CLASSIFIER_PROMPT = """다음 한국 신문 도쿄특파원 기사들을 각각 4가지 카테고리 중 하나로 분류해.

[분류 기준]
- value_korean_perspective: 한국에 미치는 영향, 한일관계, 한국인 시각의 해석이 주된 내용
- value_field_report: 직접 취재 흔적이 있음 (인터뷰, 현장 르포, 현지 사회 관찰, 재일동포 증언)
- redundant_japan_media_quote: "현지 언론에 따르면", "닛케이가 보도", "아사히신문이 전했다" 등 일본 매체 받아쓰기가 주
- redundant_press_release: 일본 정부·기업의 발표·보도자료를 옮긴 것 (한국 시각 없음)

[규칙]
- 같은 기사가 여러 카테고리에 걸치면 주된 성격 하나만 선택
- confidence: 0.0~1.0 (분류 확신도)
- reason: 분류 이유를 15자 이내로

기사 순서 그대로, 같은 개수로 반환할 것.

[기사 목록]
{articles_text}

[답변 형식] JSON 배열만, 설명 없이:
[
  {{"category": "value_korean_perspective", "confidence": 0.85, "reason": "한일경제협력 한국 입장 해석"}},
  ...
]
"""


def _strip_fence(text: str) -> str:
    """```json ... ``` 펜스 제거."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _call_gemini(prompt: str, timeout: int = 90) -> str | None:
    """단일 Gemini 호출. 모델 폴백 포함."""
    if not GEMINI_API_KEY:
        print("[Classifier] Gemini API 키 없음")
        return None
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
                return res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            except Exception as e:
                err = str(e)
                is_retry = any(c in err for c in ["503", "timed out", "timeout"])
                is_ratelimit = "429" in err
                if is_retry and attempt == 1:
                    print(f"  [Classifier] {model} 재시도 ({err[:60]})")
                    time.sleep(RETRY_WAIT)
                elif is_retry or is_ratelimit:
                    print(f"  [Classifier] {model} 폴백 ({err[:60]})")
                    time.sleep(60)
                    break
                else:
                    print(f"  [Classifier] 오류: {err[:80]}")
                    return None
    return None


def _classify_batch(articles: list[dict]) -> list[dict]:
    """
    기사 배치를 Gemini로 분류. 각 article에 'classification' 키 추가.
    {'category': str, 'confidence': float, 'reason': str}
    """
    empty_cls = {"category": "uncertain", "confidence": 0.0, "reason": "분류 실패"}

    lines = []
    for i, a in enumerate(articles, 1):
        body = (a.get("full_text") or a.get("content") or "")[:400]
        lines.append(f"{i}. 제목: {a['title']}\n   내용: {body}")
    articles_text = "\n\n".join(lines)

    prompt = CLASSIFIER_PROMPT.format(articles_text=articles_text)
    raw = _call_gemini(prompt)

    cls_list = []
    if raw:
        try:
            parsed = json.loads(_strip_fence(raw))
            if isinstance(parsed, list):
                cls_list = parsed
        except Exception as e:
            print(f"  [Classifier] JSON 파싱 실패: {e}")

    result = []
    for i, article in enumerate(articles):
        a = dict(article)
        if i < len(cls_list) and isinstance(cls_list[i], dict):
            c = cls_list[i]
            a["classification"] = {
                "category":   c.get("category", "uncertain"),
                "confidence": float(c.get("confidence", 0.0)),
                "reason":     c.get("reason", ""),
            }
        else:
            a["classification"] = dict(empty_cls)
        result.append(a)
    return result


# ── 메인 진입점 ────────────────────────────────────────────────────────────────

def classify_correspondent_articles(articles: list[dict]) -> dict:
    """
    도쿄 특파원 기사 리스트를 Gemini로 분류.

    Returns:
      {
        "value":     [Wiki 적재 대상 (value_* + confidence >= threshold)],
        "redundant": [스킵 대상],
        "uncertain": [신뢰도 낮음 → uncertain 폴더 보관],
      }
    """
    if not articles:
        return {"value": [], "redundant": [], "uncertain": []}

    print(f"[Classifier] {len(articles)}건 분류 시작 (배치 크기={BATCH_SIZE})")

    classified = []
    for i in range(0, len(articles), BATCH_SIZE):
        batch = articles[i: i + BATCH_SIZE]
        classified.extend(_classify_batch(batch))

    value     = []
    redundant = []
    uncertain = []

    for a in classified:
        cls  = a.get("classification", {})
        cat  = cls.get("category", "uncertain")
        conf = cls.get("confidence", 0.0)

        if cat.startswith("value_") and conf >= CONFIDENCE_THRESHOLD:
            value.append(a)
        elif cat.startswith("redundant_"):
            redundant.append(a)
        else:
            uncertain.append(a)

    # importance 보정: 한국 시각 기사는 기본값 +1
    for a in value:
        ent = a.get("entities", {})
        if isinstance(ent.get("importance"), int):
            ent["importance"] = min(5, ent["importance"] + 1)
        else:
            a.setdefault("entities", {})["importance"] = 4  # 기본 4

    print(
        f"[Classifier] 완료 — 적재 대상: {len(value)}건 "
        f"/ 중복·보도자료: {len(redundant)}건 "
        f"/ uncertain: {len(uncertain)}건"
    )
    return {"value": value, "redundant": redundant, "uncertain": uncertain}
