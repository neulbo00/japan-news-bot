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

STORY_HISTORY_FILE   = os.path.join(os.path.dirname(__file__), "story_history.json")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

# 제목 유사도 기반 중복 제거 임계값
TITLE_SIM_THRESHOLD   = 0.45  # within-run: 동일 사건 클러스터링
FOLLOWUP_SIM_THRESHOLD = 0.50  # cross-run: 이전 브리핑 연속 보도 판정

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
    {"name": "\uc544\uc0ac\ud788\uc2e0\ubb38",   "url": "https://www.asahi.com/rss/asahi/newsheadlines.rdf",                                       "korea_feed": False},
    {"name": "\uc9c0\uc9c0\ud1b5\uc2e0",        "url": "https://www.jiji.com/rss/ranking.rdf",                                                      "korea_feed": False},
]


def _is_korea_related(text):
    return any(kw in text for kw in KOREA_KEYWORDS)


# ── 중복 필터링 헬퍼 ──────────────────────────────────────────────────────────

# RSS 소스 우선순위 (낮을수록 고우선)
SOURCE_PRIORITY = {
    "NHK 국내뉴스": 0, "NHK 국제뉴스": 0,
    "Yahoo 교도통신": 1, "지지통신": 1,
    "마이니치신문": 2, "아사히신문": 2,
    "Yahoo Japan": 3, "Google 일본뉴스": 3, "Google 한국관련": 3,
}


def _title_bigrams(title):
    """제목을 문자 단위 bigram 집합으로 변환 (일본어/한국어 모두 대응)"""
    return set(title[i:i+2] for i in range(len(title) - 1))


def _title_similarity(a, b):
    """두 제목의 Jaccard bigram 유사도 (0.0~1.0)"""
    ba, bb = _title_bigrams(a), _title_bigrams(b)
    if not ba or not bb:
        return 0.0
    return len(ba & bb) / len(ba | bb)


def _dedup_by_title(articles):
    """
    within-run: 유사 제목 기사를 클러스터링해 대표 1건만 유지.
    같은 클러스터 내에서 SOURCE_PRIORITY 높은 소스를 대표로 선택.
    """
    kept = []
    for article in articles:
        merged = False
        for i, rep in enumerate(kept):
            if _title_similarity(article["title"], rep["title"]) >= TITLE_SIM_THRESHOLD:
                if SOURCE_PRIORITY.get(article["source"], 9) < SOURCE_PRIORITY.get(rep["source"], 9):
                    kept[i] = article
                merged = True
                break
        if not merged:
            kept.append(article)
    return kept


def _load_story_history():
    """story_history.json 로드 (cross-run 중복 판정용)"""
    if os.path.exists(STORY_HISTORY_FILE):
        try:
            with open(STORY_HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _mark_followups(articles):
    """
    cross-run: 최근 브리핑 헤드라인과 유사한 기사에 is_followup=True 마킹.
    Gemini 전송 시 후순위로 처리되며, 프롬프트에 [연속보도] 태그로 표시됨.
    """
    history = _load_story_history()
    past = [h["headline"] for e in history for h in e.get("headlines", [])]
    for article in articles:
        article["is_followup"] = bool(past) and any(
            _title_similarity(article["title"], hl) >= FOLLOWUP_SIM_THRESHOLD
            for hl in past
        )
    return articles


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
    """RSS / RDF 피드 파싱. cutoff_utc 이후 발행된 기사만 반환"""
    # RDF 네임스페이스 (아사히신문 등)
    NS_RSS  = "http://purl.org/rss/1.0/"
    NS_DC   = "http://purl.org/dc/elements/1.1/"
    try:
        res = requests.get(source["url"], headers=HEADERS, timeout=10)
        # bytes로 파싱해야 XML 선언부 인코딩을 ET가 올바르게 처리
        root = ET.fromstring(res.content)

        # RSS 2.0: .//item  /  RDF 1.0: .//{ns}item
        items = root.findall(".//item")
        if not items:
            items = root.findall(f".//{{{NS_RSS}}}item")

        result = []
        skipped_old = 0
        for item in items:
            # 제목: RSS → title / RDF → {ns}title
            title = (
                item.findtext("title")
                or item.findtext(f"{{{NS_RSS}}}title")
                or ""
            ).strip()
            # 설명: RSS → description / RDF → {ns}description
            desc = (
                item.findtext("description")
                or item.findtext(f"{{{NS_RSS}}}description")
                or ""
            ).strip()
            # 링크: RSS → link / RDF → {ns}link
            link = (
                item.findtext("link")
                or item.findtext(f"{{{NS_RSS}}}link")
                or ""
            ).strip()
            # 날짜: RSS → pubDate / RDF → dc:date
            pub = (
                item.findtext("pubDate")
                or item.findtext(f"{{{NS_DC}}}date")
                or ""
            ).strip()

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
        "korea":   [한국관련 기사 리스트 (시간 필터 + 유사 중복 제거 + 연속보도 마킹)],
        "general": [일반 일본 기사 리스트 (시간 필터 + 유사 중복 제거 + 연속보도 마킹)],
      }
    각 기사에 is_followup(bool) 필드 포함.
    """
    now_utc    = datetime.now(timezone.utc)
    cutoff_utc = now_utc - timedelta(hours=HOURS_WINDOW)
    print(f"[시간 필터] 최근 {HOURS_WINDOW}시간 이내 기사만 수집 ({cutoff_utc.astimezone(JST).strftime('%m/%d %H:%M')} JST 이후)")

    seen_ids     = set()
    korea_news   = []
    general_news = []

    for source in RSS_SOURCES:
        for article in _parse_rss(source, cutoff_utc):
            if article["id"] in seen_ids:
                continue
            seen_ids.add(article["id"])
            if article["is_korea"]:
                korea_news.append(article)
            else:
                general_news.append(article)

    raw_k, raw_g = len(korea_news), len(general_news)

    # ① within-run: 제목 유사도 기반 중복 제거
    korea_news   = _dedup_by_title(korea_news)
    general_news = _dedup_by_title(general_news)
    dedup_k = raw_k - len(korea_news)
    dedup_g = raw_g - len(general_news)
    if dedup_k or dedup_g:
        print(f"[유사 중복 제거] 한국관련 -{dedup_k}건 / 일본뉴스 -{dedup_g}건")

    # ② cross-run: 이전 브리핑 연속 보도 마킹
    korea_news   = _mark_followups(korea_news)
    general_news = _mark_followups(general_news)
    fu_k = sum(1 for a in korea_news if a["is_followup"])
    fu_g = sum(1 for a in general_news if a["is_followup"])
    if fu_k or fu_g:
        print(f"[연속보도 마킹] 한국관련 {fu_k}건 / 일본뉴스 {fu_g}건 → Gemini 후순위 처리")

    print(f"[수집 완료] 한국관련 {len(korea_news)}건 / 일본뉴스 {len(general_news)}건")
    return {"korea": korea_news, "general": general_news}
