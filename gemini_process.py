import json
import re
import requests
from config import GEMINI_API_KEY

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-1.5-flash:generateContent?key=" + (GEMINI_API_KEY or "")
        )

        PROMPT_TEMPLATE = """
        다음 일본어 뉴스를 한국어로 번역하고 요약해줘.
        반드시 아래 JSON 형식으로만 응답해. 다른 텍스트는 절대 포함하지 마.

        {{
            "title_ko": "한국어 제목",
                "summary_ko": "3~4줄 요약 (한국어)",
                    "category": "카테고리 (정치/경제/사회/국제/한국관련/기타 중 하나)"
                    }}

                    --- 원문 ---
                    제목: {title}
                    내용: {content}
                    """

                    def _strip_json_fence(text):
                        """Gemini가 ```json ... ``` 형태로 감싸서 반환할 때 안전하게 제거"""
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
                                                                                                                            
                                                                                                                                    # JSON 펜스 제거
                                                                                                                                            text = _strip_json_fence(text)
                                                                                                                                            
                                                                                                                                                    parsed = json.loads(text)
                                                                                                                                                            article["title_ko"]   = parsed.get("title_ko", article["title"])
                                                                                                                                                                    article["summary_ko"] = parsed.get("summary_ko", "")
                                                                                                                                                                            article["category"]   = parsed.get("category", "기타")
                                                                                                                                                                                    return article
                                                                                                                                                                                    
                                                                                                                                                                                        except Exception as e:
                                                                                                                                                                                                print(f"[Gemini 실패] {article['title'][:30]}... -> {e}")
                                                                                                                                                                                                        article["title_ko"]   = article["title"]
                                                                                                                                                                                                                article["summary_ko"] = article["content"][:200] if article["content"] else ""
                                                                                                                                                                                                                        article["category"]   = "기타"
                                                                                                                                                                                                                                return article
                                                                                                                                                                                                                                
                                                                                                                                                                                                                                def translate_all(news_list):
                                                                                                                                                                                                                                    results = []
                                                                                                                                                                                                                                        for i, article in enumerate(news_list, 1):
                                                                                                                                                                                                                                                print(f"[번역 중] {i}/{len(news_list)} - {article['title'][:30]}...")
                                                                                                                                                                                                                                                        results.append(process_article(article))
                                                                                                                                                                                                                                                            return results
