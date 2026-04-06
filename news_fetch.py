import hashlib
import json
import os
import requests
import xml.etree.ElementTree as ET
from config import MAX_NEWS_PER_SOURCE

POSTED_IDS_FILE = os.path.join(os.path.dirname(__file__), "posted_ids.json")
MAX_HISTORY = 500  # 너무 커지지 않도록 최근 500건만 유지


def _load_posted_ids():
    if os.path.exists(POSTED_IDS_FILE):
        try:
            with open(POSTED_IDS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def save_posted_id(article_id):
    """게시 성공한 기사 ID를 이력 파일에 추가"""
    ids = list(_load_posted_ids())
    if article_id not in ids:
        ids.append(article_id)
    # 최대 500건 유지 (오래된 것부터 제거)
    ids = ids[-MAX_HISTORY:]
    with open(POSTED_IDS_FILE, "w", encoding="utf-8") as f:
        json.dump(ids, f, ensure_ascii=False)

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
    posted_ids = _load_posted_ids()
    all_news = []
    seen_ids = set()
    skipped = 0
    for source in RSS_SOURCES:
        for article in _parse_rss(source):
            if article["id"] in seen_ids:
                continue  # 같은 실행 내 중복
            if article["id"] in posted_ids:
                skipped += 1
                continue  # 이전 실행에서 이미 게시된 기사
            seen_ids.add(article["id"])
            all_news.append(article)
    if skipped:
        print(f"[중복 스킵] 이미 게시된 기사 {skipped}건 제외")
    print(f"[수집 완료] 총 {len(all_news)}건 (신규)")
    # 정렬은 Gemini 번역 후 importance_score 기준으로 처리
    return all_news
