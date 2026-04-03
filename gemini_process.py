import json
import re
import requests
from config import GEMINI_API_KEY

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:generateContent?key=" + (GEMINI_API_KEY or "")
)

PROMPT_TEMPLATE = """
너는 일본 뉴스를 한국 독자에게 전달하는 에디터야.
아래 일본어 뉴스를 한국어로 번역·요약하고, 한국 독자 관심도 기준으로 중요도를 평가해줘.

반드시 아래 JSON 형식으로만 응답해. 다른 텍스트는 절대 포함하지 마.

{{
  "title_ko": "한국어 제목",
  "summary_ko": "3~4줄 요약 (한국어, 핵심 내용 위주)",
  "category": "카테고리 (정치/경제/사회/국제/한국관련/재해/기타 중 하나)",
  "importance_score": 중요도 점수 (1~5 정수),
  "importance_reason": "중요도 판단 이유 한 줄"
}}

중요도 기준 (한국 독자 관심도):
5점 - 한국에 직접 영향 (외교, 경제, 재난 등) / 매우 큰 국제 이슈
4점 - 일본 주요 정치·경제·사회 이슈 / 한국과 간접 연관
3점 - 일반 일본 사회·문화 뉴스
2점 - 지역 뉴스 / 소규모 사건사고
1점 - 연예·스포츠·생활 정보 등 가벼운 내용

--- 원문 ---
제목: {title}
내용: {content}
"""

def _strip_json_fence(text):
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*\n?', '', text)
    text = re.sub(r'\n?```\s*$', '', text)
    return text.strip()

def process_article(article):
    prompt = PROMPT_TEMPLATE.format(
        title=article["title"],
        content=article["content"] or "내용 없음"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3}
    }
    try:
        res = requests.post(GEMINI_URL, json=payload, timeout=20)
        res.raise_for_status()
        raw = res.json()
        text = raw["candidates"][0]["content"]["parts"][0]["text"].strip()
        text = _strip_json_fence(text)
        parsed = json.loads(text)

        article["title_ko"]          = parsed.get("title_ko", article["title"])
        article["summary_ko"]        = parsed.get("summary_ko", "")
        article["category"]          = parsed.get("category", "기타")
        article["importance_score"]  = int(parsed.get("importance_score", 3))
        article["importance_reason"] = parsed.get("importance_reason", "")
        return article

    except Exception as e:
        print(f"[Gemini 실패] {article['title'][:30]}... → {e}")
        article["title_ko"]          = article["title"]
        article["summary_ko"]        = article["content"][:200] if article["content"] else ""
        article["category"]          = "기타"
        article["importance_score"]  = 3
        article["importance_reason"] = ""
        return article

def translate_all(news_list):
    results = []
    for i, article in enumerate(news_list, 1):
        print(f"[번역 중] {i}/{len(news_list)} — {article['title'][:30]}...")
        results.append(process_article(article))

    # 중요도 높은 순 정렬 (동점이면 한국관련 우선)
    results.sort(key=lambda x: (
        -x.get("importance_score", 3),
        0 if x.get("category") == "한국관련" else 1
    ))
    return results
