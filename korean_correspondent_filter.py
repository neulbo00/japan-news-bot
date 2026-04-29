"""
Phase 6 — Step 1: 한국 특파원 기사 필터링

한국 8개 신문사 국제면 RSS에서 도쿄발 기사만 추출.
- 정규식 시그니처 매칭 (도쿄=연합뉴스, 도쿄/김상진 특파원 등)
- 12시간 시간 필터 (news_fetch.py 동일 기준)
- 실행 통계 → logs/korean_correspondent_match.json

[변경 이력]
2026-04-29 v1: Phase 6 초기 구현
"""

import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

try:
    import trafilatura
    _TRAFILATURA_OK = True
except ImportError:
    _TRAFILATURA_OK = False

try:
    from zoneinfo import ZoneInfo
    JST = ZoneInfo("Asia/Tokyo")
except ImportError:
    import pytz
    JST = pytz.timezone("Asia/Tokyo")

SCRIPT_DIR   = Path(__file__).resolve().parent
LOGS_DIR     = SCRIPT_DIR.parent / "logs"
MATCH_LOG    = LOGS_DIR / "korean_correspondent_match.json"
SOURCE_LOG   = LOGS_DIR / "kr_source_extractability.json"

HOURS_WINDOW = 12  # news_fetch.py와 동일

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ── 한국 신문사 RSS 소스 (Tier 1) ─────────────────────────────────────────────
KR_RSS_SOURCES = [
    {"name": "연합뉴스",  "url": "https://www.yonhapnewstv.co.kr/category/news/international/feed/"},
    {"name": "조선일보",  "url": "https://www.chosun.com/arc/outboundfeeds/rss/category/international/"},
    {"name": "중앙일보",  "url": "https://rss.joins.com/joins_world_list.xml"},
    {"name": "동아일보",  "url": "https://rss.donga.com/international.xml"},
    {"name": "한겨레",   "url": "https://www.hani.co.kr/rss/international/"},
    {"name": "경향신문",  "url": "https://www.khan.co.kr/rss/rssdata/world_news.xml"},
    {"name": "세계일보",  "url": "http://www.segye.com/Articles/RSSList/segye_world.xml"},
    {"name": "한국일보",  "url": "https://www.hankookilbo.com/Rss/Category/120"},
]

# ── 도쿄발 기사 시그니처 정규식 ────────────────────────────────────────────────
PATTERNS = [
    # 본문 시작 시그니처: (도쿄=연합뉴스) / (도쿄=조선일보) 김상진 특파원
    r"\(도쿄=[^)]+\)",
    r"\(도쿄=[^)]+\)\s*[가-힣]+\s*특파원",
    # 바이라인: 도쿄/김상진 특파원 / 도쿄=홍길동 기자
    r"도쿄[/=]\s*[가-힣]+\s*특파원",
    r"도쿄\s*=\s*[가-힣]+\s*기자",
    # 보조 키워드
    r"도쿄특파원",
    r"도쿄\s*주재\s*특파원",
    # 타이틀 키워드 (약한 신호 — 다른 매칭 없을 때만)
    r"\[도쿄\]",
    r"〈도쿄〉",
]

_NAME_PAT = re.compile(r"([가-힣]{2,4})\s*(?:특파원|기자)")


def is_tokyo_correspondent(title: str, content: str) -> tuple[bool, str | None]:
    """
    도쿄 특파원 기사 여부 판단.
    Returns: (매칭 여부, 특파원 이름 or None)
    본문 첫 500자 + 제목만 검사 (시그니처는 보통 앞에 있음).
    """
    text = title + "\n" + content[:500]
    for pat in PATTERNS:
        if re.search(pat, text):
            name_m = _NAME_PAT.search(text)
            return True, (name_m.group(1) if name_m else None)
    return False, None


# ── RSS 파싱 헬퍼 ──────────────────────────────────────────────────────────────

def _parse_pubdate(pub_str: str):
    """RSS pubDate → UTC datetime. 실패 시 None."""
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


def _fetch_full_text(url: str) -> str | None:
    """trafilatura로 기사 본문 추출. 실패 시 None."""
    if not _TRAFILATURA_OK:
        return None
    try:
        downloaded = trafilatura.fetch_url(url, config=trafilatura.settings.use_config())
        if downloaded is None:
            return None
        text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
        return text if text and len(text) > 50 else None
    except Exception:
        return None


def _check_source(source: dict) -> bool:
    """RSS URL 200 OK 여부 확인. 실패 시 False 반환 + 로그."""
    try:
        r = requests.get(source["url"], headers=HEADERS, timeout=8)
        ok = r.status_code == 200
        if not ok:
            print(f"  [{source['name']}] HTTP {r.status_code} — 스킵")
        return ok
    except Exception as e:
        print(f"  [{source['name']}] 연결 실패: {e} — 스킵")
        return False


def _parse_kr_rss(source: dict, cutoff_utc: datetime) -> list[dict]:
    """한국 신문사 RSS 파싱 → 도쿄 특파원 기사 필터링."""
    NS_RSS = "http://purl.org/rss/1.0/"
    NS_DC  = "http://purl.org/dc/elements/1.1/"
    try:
        res = requests.get(source["url"], headers=HEADERS, timeout=10)
        root = ET.fromstring(res.content)

        items = root.findall(".//item")
        if not items:
            items = root.findall(f".//{{{NS_RSS}}}item")

        result     = []
        skipped    = 0
        not_tokyo  = 0

        for item in items:
            title = (
                item.findtext("title") or item.findtext(f"{{{NS_RSS}}}title") or ""
            ).strip()
            desc = (
                item.findtext("description") or item.findtext(f"{{{NS_RSS}}}description") or ""
            ).strip()
            link = (
                item.findtext("link") or item.findtext(f"{{{NS_RSS}}}link") or ""
            ).strip()
            pub  = (
                item.findtext("pubDate") or item.findtext(f"{{{NS_DC}}}date") or ""
            ).strip()

            if not title or not link:
                continue

            # 시간 필터
            pub_dt = _parse_pubdate(pub)
            if pub_dt is not None and pub_dt < cutoff_utc:
                skipped += 1
                continue

            # 도쿄 특파원 시그니처 — 제목 + description 먼저 빠르게 확인
            matched, correspondent = is_tokyo_correspondent(title, desc)

            if not matched:
                # trafilatura 본문으로 재시도
                full_text = _fetch_full_text(link)
                if full_text:
                    matched, correspondent = is_tokyo_correspondent(title, full_text)
                else:
                    full_text = None

                if not matched:
                    not_tokyo += 1
                    continue
            else:
                full_text = _fetch_full_text(link)

            result.append({
                "source":                source["name"],
                "title":                 title,
                "content":               desc,
                "full_text":             full_text,
                "link":                  link,
                "pubDate":               pub,
                "pub_dt":                pub_dt,
                "id":                    hashlib.md5(link.encode()).hexdigest(),
                "is_korea":              True,
                "is_followup":           False,
                "is_korean_correspondent": True,
                "correspondent":         correspondent,
            })

        print(
            f"  [{source['name']}] {len(result)}건 도쿄발 매칭 "
            f"/ {not_tokyo}건 비도쿄 / {skipped}건 시간초과"
        )
        return result

    except Exception as e:
        print(f"  [{source['name']}] 파싱 오류: {e}")
        return []


# ── 매칭 통계 로그 ─────────────────────────────────────────────────────────────

def _save_match_log(date_str: str, articles: list, source_stats: dict):
    """logs/korean_correspondent_match.json 업데이트."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        existing = {}
        if MATCH_LOG.exists():
            existing = json.loads(MATCH_LOG.read_text(encoding="utf-8"))

        by_corr: dict[str, int] = {}
        by_src:  dict[str, int] = {}
        for a in articles:
            c = a.get("correspondent") or "미상"
            by_corr[c] = by_corr.get(c, 0) + 1
            s = a["source"]
            by_src[s]  = by_src.get(s, 0) + 1

        existing[date_str] = {
            "total_matched":      len(articles),
            "by_source":          by_src,
            "by_correspondent":   by_corr,
            "source_http_status": source_stats,
        }

        # 최근 30일만 보관
        keys = sorted(existing.keys())
        if len(keys) > 30:
            for k in keys[:-30]:
                del existing[k]

        MATCH_LOG.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[MatchLog] 저장 실패: {e}")


# ── 메인 진입점 ────────────────────────────────────────────────────────────────

def fetch_korean_correspondent_news() -> list[dict]:
    """
    한국 8개 신문사 국제면 RSS → 도쿄 특파원 기사 필터링.
    반환: 매칭된 기사 리스트 (is_korean_correspondent=True 포함).
    """
    now_utc    = datetime.now(timezone.utc)
    cutoff_utc = now_utc - timedelta(hours=HOURS_WINDOW)
    date_str   = now_utc.astimezone(JST).strftime("%Y-%m-%d")

    print(f"\n[Phase 6] 한국 특파원 기사 수집 시작 (최근 {HOURS_WINDOW}h)")

    seen_ids     = set()
    all_articles = []
    source_stats = {}

    for source in KR_RSS_SOURCES:
        ok = _check_source(source)
        source_stats[source["name"]] = "ok" if ok else "fail"
        if not ok:
            continue

        for article in _parse_kr_rss(source, cutoff_utc):
            if article["id"] in seen_ids:
                continue
            seen_ids.add(article["id"])
            all_articles.append(article)

    print(
        f"[Phase 6] 수집 완료: 도쿄 특파원 기사 {len(all_articles)}건 "
        f"({sum(1 for s in source_stats.values() if s == 'ok')}/{len(KR_RSS_SOURCES)} 소스 정상)"
    )

    # 통계 기록
    _save_match_log(date_str, all_articles, source_stats)

    return all_articles
