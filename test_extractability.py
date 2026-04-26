"""
9개 RSS 소스 각 1건씩 본문 추출 가능 여부 테스트.
결과: logs/source_extractability.json

사용: python test_extractability.py
"""
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path
import requests

try:
    import trafilatura
    _TRAF_OK = True
except ImportError:
    _TRAF_OK = False

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

RSS_SOURCES = [
    {"name": "Yahoo Japan",    "url": "https://news.yahoo.co.jp/rss/topics/top-picks.xml"},
    {"name": "NHK 국내뉴스",   "url": "https://www3.nhk.or.jp/rss/news/cat0.xml"},
    {"name": "NHK 국제뉴스",   "url": "https://www3.nhk.or.jp/rss/news/cat6.xml"},
    {"name": "Google 일본뉴스", "url": "https://news.google.com/rss?hl=ja&gl=JP&ceid=JP:ja"},
    {"name": "Google 한국관련", "url": "https://news.google.com/rss/search?q=%E9%9F%93%E5%9B%BD+%E6%97%A5%E6%9C%AC&hl=ja&gl=JP&ceid=JP:ja"},
    {"name": "Yahoo 교도통신",  "url": "https://news.yahoo.co.jp/rss/media/kyodonews/all.xml"},
    {"name": "마이니치신문",    "url": "http://mainichi.jp/rss/etc/flash.rss"},
    {"name": "아사히신문",      "url": "https://www.asahi.com/rss/asahi/newsheadlines.rdf"},
    {"name": "지지통신",        "url": "https://www.jiji.com/rss/ranking.rdf"},
]


def get_first_link(rss_url: str) -> str | None:
    NS_RSS = "http://purl.org/rss/1.0/"
    try:
        res = requests.get(rss_url, headers=HEADERS, timeout=10)
        root = ET.fromstring(res.content)
        items = root.findall(".//item") or root.findall(f".//{{{NS_RSS}}}item")
        if not items:
            return None
        item = items[0]
        link = (
            item.findtext("link")
            or item.findtext(f"{{{NS_RSS}}}link")
            or ""
        ).strip()
        return link or None
    except Exception as e:
        print(f"  RSS 파싱 실패: {e}")
        return None


def try_extract(url: str) -> dict:
    if not _TRAF_OK:
        return {"success": False, "reason": "trafilatura_not_installed"}
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded is None:
            return {"success": False, "reason": "fetch_failed"}
        text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
        if text and len(text) > 50:
            return {"success": True, "char_count": len(text)}
        return {"success": False, "reason": "no_content_extracted"}
    except Exception as e:
        return {"success": False, "reason": str(e)[:100]}


def main():
    results = {}
    for src in RSS_SOURCES:
        print(f"\n[{src['name']}] RSS 수집 중...")
        link = get_first_link(src["url"])
        if not link:
            results[src["name"]] = {"success": False, "reason": "rss_no_link"}
            print(f"  → 링크 없음")
            continue

        print(f"  링크: {link[:80]}")
        result = try_extract(link)
        results[src["name"]] = result
        if result["success"]:
            print(f"  → ✅ 본문 추출 성공 ({result['char_count']}자)")
        else:
            print(f"  → ❌ 실패: {result['reason']}")

    logs_dir = Path(__file__).parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    out_path = logs_dir / "source_extractability.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    success_count = sum(1 for v in results.values() if v.get("success"))
    print(f"\n{'='*50}")
    print(f"결과: {success_count}/{len(RSS_SOURCES)}개 소스 본문 추출 성공")
    print(f"저장: {out_path}")

    if success_count >= 5:
        print("✅ Phase 1 완료 기준 달성 (5개 이상 성공)")
    else:
        print(f"⚠️  성공 {success_count}개 — 기준 미달 (5개 이상 필요)")


if __name__ == "__main__":
    main()
