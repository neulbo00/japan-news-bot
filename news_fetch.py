import hashlib
import json
import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

try:
    from zoneinfo import ZoneInfo
    JST = ZoneInfo("Asia/Tokyo")
except ImportError:
    import pytz
    JST = pytz.timezone("Asia/Tokyo")

POSTED_IDS_FILE = os.path.join(os.path.dirname(__file__), "posted_ids.json")
MAX_HISTORY = 500
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; JapanNewsBot/1.0)"}

# 수집 시간 범위: 브리핑 실행 시각 기준 과거 12시간
HOURS_WINDOW = 12

# ──────────────────────────────────────────────────────────────────────────────
# 한국관련 키워드 (일본어) — "일본에서 보는 한국" 관점 강화
# 일본 매체에서 한국·한일 관련 기사를 잡기 위한 키워드
# ──────────────────────────────────────────────────────────────────────────────
KOREA_KEYWORDS = [
    # 국가·지역
    "\u97d3\u56fd", "\u97d3\u56fd\u4eba", "\u97d3\u56fd\u653f\u5e9c", "\u97d3\u56fd\u4eba\u6c11", "\u97d3\u56fd\u8ecd", "\u97d3\u56fd\u793e\u4f1a",
    "\u65e5\u97d3", "\u97d3\u65e5", "\u65e5\u97d3\u95a2\u4fc2", "\u97d3\u65e5\u95a2\u4fc2",
    "\u671d\u9bae", "\u671d\u9bae\u534a\u5cf6", "\u671d\u9bae\u6c11\u65cf",
    "\u30bd\u30a6\u30eb", "\u30d7\u30b5\u30f3", "\u5149\u5dde", "\u5927\u90b1", "\u4ec1\u5ddd",

    # 외교·정치 (일본어 매체 한국 관련 키워드)
    "\u5f81\u7528\u5de5\u554f\u984c", "\u5f90\u7528\u5de5\u554f\u984c", "\u97d3\u56fd\u5927\u7d71\u9818", "\u97d3\u56fd\u9996\u76f8", "\u97d3\u56fd\u653f\u5c40",
    "\u97d3\u56fd\u5916\u76f8", "\u97d3\u56fd\u5916\u4ea4", "\u97d3\u56fd\u5916\u52d9",
    "\u6155\u5bb9\u8239", "\u6155\u5bb9\u8239\u554f\u984c", "\u6df1\u5e95\u6f41\u6a29", "\u6df1\u5e95\u6f41\u6a29\u8a02\u7d04",
    "\u9020\u8239", "\u8fba\u8239", "\u65e5\u97d3\u5bfe\u8a71", "\u97d3\u5bfe\u8a71",
    "\u8f38\u51fa\u8996\u5bdf", "\u8f38\u51fa\u8996\u5bdf\u59d4\u54e1\u4f1a", "\u8f38\u51fa\u8996\u5bdf\u59d4", "\u697d\u5929",

    # 안보·군사
    "THAAD", "\u5317\u671d\u9bae\u30df\u30b5\u30a4\u30eb", "\u5317\u671d\u9bae", "\u9811\u671d\u9bae",
    "\u97d3\u56fd\u8ecd", "\u97d3\u56fd\u8ecd\u968a", "\u97d3\u56fd\u7a7a\u8ecd",
    "\u5317\u671d\u9bae\u30df\u30b5\u30a4\u30eb", "\u5317\u671d\u9bae\u6838",

    # 경제·기업
    "\u30b5\u30e0\u30b9\u30f3", "\u73fe\u4ee3\u81ea\u52d5\u8eca", "\u30d2\u30e5\u30f3\u30c0\u30a4", "LG", "SK\u30cf\u30a4\u30cb\u30c3\u30af\u30b9",
    "\u30ed\u30c3\u30c6", "\u30ab\u30ab\u30aa", "\u30cd\u30a4\u30d0\u30fc", "\u30cf\u30a4\u30d6",
    "\u97d3\u56fd\u7d4c\u6e08", "\u97d3\u56fd\u682a", "\u30a6\u30a9\u30f3\u5316", "\u30a6\u30a9\u30f3\u9ad8",
    "\u97d3\u56fd\u8f38\u51fa", "\u97d3\u56fd\u8f38\u5165",

    # 문화·엔터
    "K-POP", "K\u30dd\u30c3\u30d7", "\u97d3\u6d41", "K\u30c9\u30e9\u30de", "\u97d3\u56fd\u30c9\u30e9\u30de",
    "BTS", "\u30d6\u30e9\u30c3\u30af\u30d4\u30f3\u30af", "BLACKPINK", "NewJeans", "\u30cb\u30e5\u30fc\u30b8\u30fc\u30f3\u30ba",
    "\u97d3\u56fd\u6620\u753b", "\u97d3\u56fd\u6f14\u6b4c", "\u97d3\u56fd\u30b3\u30b9\u30e1",
    "\u5728\u65e5\u30b3\u30ea\u30a2\u30f3", "\u5728\u65e5\u97d3\u56fd\u4eba",
]

# RSS 소스 목록
RSS_SOURCES = [
    {"name": "Yahoo Japan",    "url": "https://news.yahoo.co.jp/rss/topics/top-picks.xml",                                        "korea_feed": False},
    {"name": "NHK \uad6d\ub0b4\ub274\uc2a4",   "url": "https://www3.nhk.or.jp/rss/news/cat0.xml",                                               "korea_feed": False},
    {"name": "NHK \uad6d\uc81c\ub274\uc2a4",   "url": "https://www3.nhk.or.jp/rss/news/cat6.xml",                                               "korea_feed": False},
    {"name": "Google \uc77c\ubcf8\ub274\uc2a4", "url": "https://news.google.com/rss?hl=ja&gl=JP&ceid=JP:ja",                                      "korea_feed": False},
    {"name": "Google \ud55c\uad6d\uad00\ub828", "url": "https://news.google.com/rss/search?q=%E9%9F%93%E5%9B%BD+%E6%97%A5%E6%9C%AC&hl=ja&gl=JP&ceid=JP:ja", "korea_feed": True},
    {"name": "Yahoo \uad50\ub3c4\ud1b5\uc2e0",  "url": "https://news.yahoo.co.jp/rss/media/kyodonews/all.xml",                                    "korea_feed": False},
    {"name": "\ub9c8\uc774\ub2c8\uce58\uc2e0\ubb38",  "url": "http://mainichi.jp/rss/etc/flash.rss",                                                      "korea_feed": False},
    {"name": "\uc544\uc0ac\ud788\uc2e0\ubb38",   "url": "http://rss.asahi.com/f/asahi_newsheadlines",                                             "korea_feed": False},
]


def _load_posted_ids():
    if os.path.exists(POSTED_IDS_FILE):
        try:
            with open(POSTED_IDS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def save_posted_id(article_id):
    ids = list(_load_posted_ids())
    if article_id not in ids:
        ids.append(article_id)
    ids = ids[-MAX_HISTORY:]
    with open(POSTED_IDS_FILE, "w", encoding="utf-8") as f:
        json.dump(ids, f, ensure_ascii=False)


def _is_korea_related(text):
    return any(kw in text for kw in KOREA_KEYWORDS)


def _parse_pubdate(pub_str):
    """RSS pubDate 문자열 → UTC datetime. 파싱 실패 시 None 반환"""
    if not pub_str:
        return None
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(pub_str.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def _parse_rss(source, cutoff_utc):
    """RSS 피드 파싱. cutoff_utc 이후 발행된 기사만 반환"""
    try:
        res = requests.get(source["url"], headers=HEADERS, timeout=10)
        res.encoding = "utf-8"
        root = ET.fromstring(res.text)
        items = root.findall(".//item")
        result = []
        skipped_old = 0
        for item in items:
            title   = (item.findtext("title") or "").strip()
            desc    = (item.findtext("description") or "").strip()
            link    = (item.findtext("link") or "").strip()
            pub     = (item.findtext("pubDate") or "").strip()
            if not title or not link:
                continue

            # 시간 필터: pubDate가 있으면 cutoff 이후 기사만
            pub_dt = _parse_pubdate(pub)
            if pub_dt is not None and pub_dt < cutoff_utc:
                skipped_old += 1
                continue

            result.append({
                "source":   source["name"],
                "title":    title,
                "content":  desc,
                "link":     link,
                "pubDate":  pub,
                "pub_dt":   pub_dt,
                "id":       hashlib.md5(link.encode()).hexdigest(),
                "is_korea": source["korea_feed"] or _is_korea_related(title + desc),
            })
        if skipped_old:
            print(f"  [{source['name']}] \uc2dc\uac04 \ud544\ud130: {skipped_old}\uac74 \uc81c\uc678 (\ucef7\uc624\ud504 {HOURS_WINDOW}\uc2dc\uac04)")
        return result
    except Exception as e:
        print(f"[\uc218\uc9d1\uc624\ub958] {source['name']}: {e}")
        return []


def fetch_japan_news():
    """
    반환:
      {
        "korea":   [한국관련 기사 리스트 (시간 필터 + 중복제거)],
        "general": [일반 일본 기사 리스트 (시간 필터 + 중복제거)],
      }
    """
    now_utc    = datetime.now(timezone.utc)
    cutoff_utc = now_utc - timedelta(hours=HOURS_WINDOW)
    print(f"[\uc2dc\uac04 \ud544\ud130] \ucd5c\uadfc {HOURS_WINDOW}\uc2dc\uac04 \uc774\ub0b4 \uae30\uc0ac\ub9cc \uc218\uc9d1 ({cutoff_utc.astimezone(JST).strftime('%m/%d %H:%M')} JST \uc774\ud6c4)")

    posted_ids = _load_posted_ids()
    seen_ids   = set()
    korea_news   = []
    general_news = []
    skipped_dup  = 0

    for source in RSS_SOURCES:
        for article in _parse_rss(source, cutoff_utc):
            if article["id"] in seen_ids:
                continue
            if article["id"] in posted_ids:
                skipped_dup += 1
                continue
            seen_ids.add(article["id"])
            if article["is_korea"]:
                korea_news.append(article)
            else:
                general_news.append(article)

    if skipped_dup:
        print(f"[\uc911\ubcf5 \uc81c\uc678] \uc774\ubbf8 \uac8c\uc2dc\ub41c \uae30\uc0ac {skipped_dup}\uac74 \uc2a4\ud0b5")

    print(f"[\uc218\uc9d1 \uc644\ub8cc] \ud55c\uad6d\uad00\ub828 {len(korea_news)}\uac74 / \uc77c\ubcf8\ub274\uc2a4 {len(general_news)}\uac74")
    return {"korea": korea_news, "general": general_news}
