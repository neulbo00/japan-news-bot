"""
Wiki 기사 단위 적재 모듈 (Phase 4 전면 재작성).

적재 경로: C:\\Users\\neulb\\OneDrive\\Documents\\wiki\\raw\\news\\YYYY-MM-DD\\{slug}.md
importance >= 4 기사만 단독 .md 파일로 저장.
importance < 4 기사는 daily note 안에 reference만 남김 (Phase 5에서 처리).
"""
import json
import os
import re
from datetime import datetime
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    JST = ZoneInfo("Asia/Tokyo")
except ImportError:
    import pytz
    JST = pytz.timezone("Asia/Tokyo")

WIKI_NEWS_ROOT = Path(r"C:\Users\neulb\OneDrive\Documents\wiki\raw\news")
IMPORTANCE_THRESHOLD = 4  # 이 값 이상만 단독 .md 파일 생성


def _slugify(title: str) -> str:
    """제목 → 파일명용 slug (한/일 허용, 특수문자 제거)."""
    # 일본어·한국어·영숫자·하이픈만 허용
    slug = re.sub(r"[^\w぀-ヿ㐀-䶿一-鿿가-힯-]", "-", title)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug[:60]  # 최대 60자


def _make_unique_path(directory: Path, slug: str) -> Path:
    """충돌 시 -2, -3 접미사로 유일한 파일명 생성."""
    path = directory / f"{slug}.md"
    if not path.exists():
        return path
    for n in range(2, 100):
        path = directory / f"{slug}-{n}.md"
        if not path.exists():
            return path
    return directory / f"{slug}-x.md"


def _wiki_links(items: list) -> list:
    """entity 목록을 Obsidian 위키링크 형식으로 변환."""
    return [f"[[{item}]]" for item in items if item]


def _format_frontmatter(article: dict, date_str: str, slot: str) -> str:
    ent = article.get("entities", {})
    people = _wiki_links(ent.get("people", []))
    orgs   = _wiki_links(ent.get("organizations", []))
    places = _wiki_links(ent.get("places", []))
    topics = _wiki_links(ent.get("topics", []))
    cat = "korea" if article.get("is_korea") else "japan"
    imp = ent.get("importance", 3)

    lines = [
        "---",
        f"date: {date_str}",
        f"slot: {slot}",
        f"source: {article.get('source', '')}",
        f"url: {article.get('link', '')}",
        f"category: {cat}",
        f"importance: {imp}",
    ]
    if people:
        lines.append(f"people: {json.dumps(people, ensure_ascii=False)}")
    if orgs:
        lines.append(f"organizations: {json.dumps(orgs, ensure_ascii=False)}")
    if places:
        lines.append(f"places: {json.dumps(places, ensure_ascii=False)}")
    if topics:
        lines.append(f"topics: {json.dumps(topics, ensure_ascii=False)}")
    lines.append(f"is_followup: {'true' if article.get('is_followup') else 'false'}")
    lines.append("---")
    return "\n".join(lines)


def _inject_wiki_links(text: str, entities: dict) -> str:
    """본문 텍스트에 entity 위키링크 삽입 (첫 등장만)."""
    inserted = set()
    all_names = (
        entities.get("people", [])
        + entities.get("organizations", [])
        + entities.get("places", [])
    )
    for name in all_names:
        if not name or name in inserted:
            continue
        # 텍스트에 해당 이름이 있으면 첫 번째만 [[name]] 으로 교체
        if name in text:
            text = text.replace(name, f"[[{name}]]", 1)
            inserted.add(name)
    return text


def _build_article_md(article: dict, date_str: str, slot: str) -> str:
    """기사 1건 → .md 본문 생성."""
    ent = article.get("entities", {})
    title = article.get("title", "")
    link  = article.get("link", "")
    source = article.get("source", "")

    # 본문: full_text 있으면 1500자, 없으면 description
    body_raw = (article.get("full_text") or article.get("content") or "")[:1500]
    body = _inject_wiki_links(body_raw, ent) if body_raw else ""

    # 제목 (번역 없이 일본어 그대로 — 추후 Gemini 번역 통합 가능)
    fm = _format_frontmatter(article, date_str, slot)

    parts = [
        fm,
        "",
        f"# {title}",
        f"> 출처: [{source}]({link})",
        "",
    ]
    if body:
        parts += [body, ""]
    parts += [
        "---",
        f"[원문 링크]({link})",
    ]
    return "\n".join(parts)


def export_articles_to_wiki(articles: list, date_str: str, slot: str) -> dict:
    """
    기사 리스트에서 importance >= IMPORTANCE_THRESHOLD 기사를 Wiki에 적재.
    반환: {"saved": [path...], "skipped": int, "low_importance": [article...]}
      low_importance: importance < threshold 기사 (daily note reference용)
    """
    directory = WIKI_NEWS_ROOT / date_str
    directory.mkdir(parents=True, exist_ok=True)

    saved = []
    low_importance = []

    for article in articles:
        ent = article.get("entities", {})
        imp = ent.get("importance", 3)

        if imp < IMPORTANCE_THRESHOLD:
            low_importance.append(article)
            continue

        slug = _slugify(article.get("title", "untitled"))
        path = _make_unique_path(directory, slug)
        content = _build_article_md(article, date_str, slot)
        path.write_text(content, encoding="utf-8")
        saved.append(str(path))

    if saved:
        print(f"[Wiki] {len(saved)}건 적재 완료 → {directory}")
    if low_importance:
        print(f"[Wiki] importance < {IMPORTANCE_THRESHOLD}: {len(low_importance)}건 (daily note 참조용)")

    return {"saved": saved, "skipped": 0, "low_importance": low_importance}


def export_briefing_to_wiki(briefing: dict, news_dict: dict):
    """
    main.py에서 호출되는 진입점.
    briefing에 _korea_articles / _general_articles가 있으면 기사 단위 적재.
    없으면 레거시 브리핑 1건 적재로 폴백.
    """
    now = datetime.now(tz=JST)
    date_str = now.strftime("%Y-%m-%d")
    hour = now.hour
    slot = "morning" if 5 <= hour < 12 else "evening"

    korea_arts   = briefing.get("_korea_articles", [])
    general_arts = briefing.get("_general_articles", [])
    all_arts     = korea_arts + general_arts

    if all_arts:
        result = export_articles_to_wiki(all_arts, date_str, slot)
        total_saved = len(result["saved"])
        low = result["low_importance"]
        print(f"[Wiki Export] 완료: 총 {total_saved}건 저장 / {len(low)}건 low-importance")
        # low_importance 기사를 briefing에 첨부 (daily note 작성용)
        briefing["_low_importance_articles"] = low
        return True
    else:
        # 레거시 폴백: 브리핑 텍스트 1건 저장
        _legacy_export(briefing, news_dict, date_str, slot)
        return False


def _legacy_export(briefing: dict, news_dict: dict, date_str: str, slot: str):
    """이전 방식 폴백: 브리핑 1건을 raw/news_bot/에 저장."""
    legacy_dir = Path(r"C:\Users\neulb\OneDrive\Documents\wiki\raw\news_bot")
    legacy_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(tz=JST)
    filename = f"{now.strftime('%Y-%m-%d-%H%M')}-briefing.md"
    target = legacy_dir / filename

    title = briefing.get("title", "No Title")
    lines = [
        "---",
        f"title: {title}",
        f"date: {date_str}",
        f"slot: {slot}",
        "source: japan-news-bot",
        "type: news-briefing",
        "---",
        "",
        f"# {title}",
        "",
        json.dumps(briefing, ensure_ascii=False, indent=2),
    ]
    target.write_text("\n".join(lines), encoding="utf-8")
    print(f"[Wiki Export] 레거시 저장: {target}")
