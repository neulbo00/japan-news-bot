import hashlib
import requests
import xml.etree.ElementTree as ET
from config import MAX_NEWS_PER_SOURCE

RSS_SOURCES = [
    {"name": "Yahoo Japan", "url": "https://news.yahoo.co.jp/rss/topics/top-picks.xml"},
    {"name": "NHK",         "url": "https://www3.nhk.or.jp/rss/news/cat0.xml"},
    {"name": "교도통신",     "url": "https://feeds.kyodonews.net/rss/news.xml"},
]

def _parse_rss(source):
    try:
        res = requests.get(source["url"], timeout=10)
        res.encoding = "utf-8"
        root = ET.fromstring(res.text)
        items = root.findall(".//item")[:MAX_NEWS_PER_SOURCE]
        result = []
        for item in items:
            title = (item.findtext("title") or "").strip()
            desc  = (item.findtext("description") or "").strip()
            link  = (item.findtext("link") or "").strip()
            if not title or not link:
                continue
            result.append({
                "source":  source["name"],
                "title":   title,
                "content": desc,
                "link":    link,
                "id":      hashlib.md5(link.encode()).hexdigest(),
            })
        return result
    except Exception as e:
        print(f"[수집 실패] {source['name']}: {e}")
        return []

def fetch_japan_news():
    all_news = []
    seen_ids = set()
    for source in RSS_SOURCES:
        for article in _parse_rss(source):
            if article["id"] not in seen_ids:
                seen_ids.add(article["id"])
                all_news.append(article)
    print(f"[수집 완료] 총 {len(all_news)}건 (중복 제거 후)")
    # 정렬은 Gemini 번역 후 importance_score 기준으로 처리
    return all_news
