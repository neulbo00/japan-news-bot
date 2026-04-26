"""
Daily Note 자동 생성 모듈 (Phase 5).

경로: C:\\Users\\neulb\\OneDrive\\Documents\\wiki\\Daily\\YYYY-MM-DD.md
07시 슬롯: 파일 생성 (날씨 + 아침 뉴스)
19시 슬롯: 같은 파일 업데이트 (저녁 뉴스 추가)
"""
import re
from datetime import datetime
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    JST = ZoneInfo("Asia/Tokyo")
except ImportError:
    import pytz
    JST = pytz.timezone("Asia/Tokyo")

DAILY_DIR = Path(r"C:\Users\neulb\OneDrive\Documents\wiki\Daily")
IMPORTANCE_THRESHOLD = 4

WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]


def _importance_stars(imp: int) -> str:
    return "★" * min(imp, 5)


def _article_line(article: dict, date_str: str) -> str:
    """기사 1건 → daily note 한 줄."""
    ent = article.get("entities", {})
    imp = ent.get("importance", 3)
    title = article.get("title", "")

    if imp >= IMPORTANCE_THRESHOLD:
        from export_to_wiki import _slugify
        slug = _slugify(title)
        # wiki link 형식: [[News/2026-04-27/slug]]
        link = f"[[News/{date_str}/{slug}]]"
        return f"- {link} {_importance_stars(imp)}"
    else:
        return f"- {title}"


def _build_news_section(articles: list, label: str, date_str: str) -> list:
    """기사 리스트 → 섹션 줄 목록."""
    if not articles:
        return []
    lines = [f"### {label}"]
    for a in articles:
        lines.append(_article_line(a, date_str))
    return lines


def _build_morning_note(date_str: str, weekday: str,
                        briefing: dict, weather_block: str) -> str:
    """07시: 데일리 노트 초기 생성."""
    korea_arts   = briefing.get("_korea_articles", [])
    general_arts = briefing.get("_general_articles", [])
    low_arts     = briefing.get("_low_importance_articles", [])

    # low_importance 기사를 korea / general로 분류
    low_korea   = [a for a in low_arts if a.get("is_korea")]
    low_general = [a for a in low_arts if not a.get("is_korea")]
    all_korea   = korea_arts + low_korea
    all_general = general_arts + low_general

    lines = [f"# {date_str} ({weekday})", ""]

    # 날씨 블록
    if weather_block:
        lines += weather_block.split("\n") + [""]

    lines += ["## 📰 오늘의 뉴스", ""]

    # 아침 한국관련
    korea_lines = _build_news_section(all_korea, "한국관련 (아침)", date_str)
    if korea_lines:
        lines += korea_lines + [""]

    # 아침 일본 종합
    gen_lines = _build_news_section(all_general, "일본 종합 (아침)", date_str)
    if gen_lines:
        lines += gen_lines + [""]

    # 저녁 플레이스홀더 (저녁 슬롯에서 채움)
    lines += [
        "### 한국관련 (저녁)",
        "<!-- 저녁 브리핑 후 자동 추가 -->",
        "",
        "### 일본 종합 (저녁)",
        "<!-- 저녁 브리핑 후 자동 추가 -->",
        "",
    ]

    # 향후 확장 자리
    lines += [
        "## 🔮 일진",
        "<!-- 사주 일진 모듈에서 후속 추가 -->",
        "",
        "## 📅 오늘 일정",
        "<!-- Google Calendar 모듈에서 후속 추가 -->",
        "",
        "## 📊 포트폴리오",
        "<!-- Stock-Portfolio 모듈에서 후속 추가 -->",
    ]

    return "\n".join(lines)


def _update_evening_note(content: str, date_str: str, briefing: dict) -> str:
    """19시: 기존 데일리 노트에 저녁 섹션 업데이트."""
    korea_arts   = briefing.get("_korea_articles", [])
    general_arts = briefing.get("_general_articles", [])
    low_arts     = briefing.get("_low_importance_articles", [])

    low_korea   = [a for a in low_arts if a.get("is_korea")]
    low_general = [a for a in low_arts if not a.get("is_korea")]
    all_korea   = korea_arts + low_korea
    all_general = general_arts + low_general

    def _section_text(articles, label):
        lines = _build_news_section(articles, label, date_str)
        return "\n".join(lines) if lines else f"### {label}\n- (기사 없음)"

    korea_block   = _section_text(all_korea, "한국관련 (저녁)")
    general_block = _section_text(all_general, "일본 종합 (저녁)")

    # 플레이스홀더 교체
    content = re.sub(
        r"### 한국관련 \(저녁\)\n<!-- 저녁 브리핑 후 자동 추가 -->",
        korea_block,
        content,
    )
    content = re.sub(
        r"### 일본 종합 \(저녁\)\n<!-- 저녁 브리핑 후 자동 추가 -->",
        general_block,
        content,
    )
    return content


def write_daily_note(briefing: dict, slot: str = "morning") -> Path | None:
    """
    데일리 노트 생성 또는 업데이트.
    slot: "morning" | "evening"
    반환: 저장된 파일 경로 또는 None
    """
    DAILY_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now(tz=JST)
    date_str = now.strftime("%Y-%m-%d")
    weekday  = WEEKDAY_KO[now.weekday()]
    note_path = DAILY_DIR / f"{date_str}.md"

    weather_block = briefing.get("_weather_block", "")

    try:
        if slot == "morning" or not note_path.exists():
            content = _build_morning_note(date_str, weekday, briefing, weather_block)
            note_path.write_text(content, encoding="utf-8")
            print(f"[DailyNote] 생성: {note_path}")
        else:
            # 저녁: 기존 파일 업데이트
            existing = note_path.read_text(encoding="utf-8")
            updated  = _update_evening_note(existing, date_str, briefing)
            note_path.write_text(updated, encoding="utf-8")
            print(f"[DailyNote] 업데이트 (저녁): {note_path}")

        return note_path
    except Exception as e:
        print(f"[DailyNote] 오류: {e}")
        return None
