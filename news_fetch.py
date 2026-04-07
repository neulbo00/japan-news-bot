import hashlib
import json
import os
import requests
import xml.etree.ElementTree as ET
from config import MAX_NEWS_PER_SOURCE

POSTED_IDS_FILE = os.path.join(os.path.dirname(__file__), "posted_ids.json")
MAX_HISTORY = 500
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; JapanNewsBot/1.0)"}

# ──────────────────────────────────────────────────────────────────────────────
# 한국 관련 키워드 (일본어) — "일본에서 보는 한국" 관점
# 일본 미디어가 한국을 다루는 맥락: 외교·안보·경제·문화·사회 전반
# ──────────────────────────────────────────────────────────────────────────────
KOREA_KEYWORDS = [
    # 국가·지역
    "韓国", "韓国側", "韓国政府", "韓国人", "韓国語", "韓国系",
    "日韓", "韓日", "日韓関係", "韓日関係",
    "朝鮮", "朝鮮半島", "北朝鮮",
    "ソウル", "釜山", "仁川", "済州", "光州",

    # 외교·정치 (일본이 주목하는 한국 정치)
    "尹錫悦", "李在明", "韓国大統領", "韓国外相", "韓国首相",
    "韓国外務", "韓国政界", "韓国野党",
    "徴用工", "元徴用工", "慰安婦", "従軍慰安婦",
    "竹島", "独島", "日本海", "東海",
    "輸出規制", "ホワイト国", "GSOMIA",

    # 안보·군사
    "THAAD", "在韓米軍", "韓米", "米韓",
    "韓国軍", "韓国海軍", "韓国空軍",
    "北朝鮮ミサイル", "北朝鮮核",

    # 경제·기업
    "サムスン", "現代自動車", "ヒュンダイ", "LG", "SKハイニックス",
    "ロッテ", "カカオ", "ネイバー", "ハイブ",
    "韓国経済", "韓国株", "ウォン安", "ウォン高",
    "韓国輸出", "韓国貿易",

    # 문화·엔터
    "K-POP", "Kポップ", "韓流", "Kドラマ", "韓国ドラマ",
    "BTS", "ブラックピンク", "BLACKPINK", "NewJeans", "ニュージーンズ",
    "韓国映画", "韓国料理", "韓国コスメ",
    "在日コリアン", "在日韓国",
]

# RSS 소스 목록
RSS_SOURCES = [
    {
        "name": "Yahoo Japan",
        "url": "https://news.yahoo.co.jp/rss/topics/top-picks.xml",
        "korea_feed": False,
    },
    {
        "name": "NHK 국내뉴스",
        "url": "https://www3.nhk.or.jp/rss/news/cat0.xml",
        "korea_feed": False,
    },
    {
        "name": "NHK 국제뉴스",
        "url": "https://www3.nhk.or.jp/rss/news/cat6.xml",
        "korea_feed": False,
    },
    {
        "name": "Google 일본뉴스",
        "url": "https://news.google.com/rss?hl=ja&gl=JP&ceid=JP:ja",
        "korea_feed": False,
    },
    {
        "name": "Google 한국관련",
        "url": "https://news.google.com/rss/search?q=%E9%9F%93%E5%9B%BD+%E6%97%A5%E6%9C%AC&hl=ja&gl=JP&ceid=JP:ja",
        "korea_feed": True,
    },
]

# 브리핑 1건당 최대 전달 건수
MAX_KOREA_ITEMS   = 10
MAX_GENERAL_ITEMS = 10


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
    ids = ids[-MAX_HISTORY:]
    with open(POSTED_IDS_FILE, "w", encoding="utf-8") as f:
        json.dump(ids, f, ensure_ascii=False)


def _is_korea_related(text):
    """제목/내용에 한국 관련 키워드 포함 여부 확인"""
    return any(kw in text for kw in KOREA_KEYWORDS)


def _parse_rss(source):
    try:
        res = requests.get(source["url"], headers=HEADERS, timeout=10)
        res.encoding = "utf-8"
        root = ET.fromstring(res.text)
        items = root.findall(".//item")[:MAX_NEWS_PER_SOURCE]
        result = []
        for item in items:
            title   = (item.findtext("title") or "").strip()
            desc    = (item.findtext("description") or "").strip()
            link    = (item.findtext("link") or "").strip()
            pub     = (item.findtext("pubDate") or "").strip()
            if not title or not link:
                continue
            result.append({
                "source":  source["name"],
                "title":   title,
                "content": desc,
                "link":    link,
                "pubDate": pub,
                "id":      hashlib.md5(link.encode()).hexdigest(),
                # 소스가 한국 피드이거나, 제목/내용에 한국 키워드 포함 시 True
                "is_korea": source["korea_feed"] or _is_korea_related(title + desc),
            })
        return result
    except Exception as e:
        print(f"[수집 실패] {source['name']}: {e}")
        return []


def fetch_japan_news():
    """
    반환값:
      {
        "korea": [한국관련 기사 리스트 (최대 MAX_KOREA_ITEMS건)],
        "general": [일반 일본 기사 리스트 (최대 MAX_GENERAL_ITEMS건)],
      }
    """
    posted_ids = _load_posted_ids()
    seen_ids   = set()
    korea_news   = []
    general_news = []
    skipped = 0

    for source in RSS_SOURCES:
        for article in _parse_rss(source):
            if article["id"] in seen_ids:
                continue
            if article["id"] in posted_ids:
                skipped += 1
                continue
            seen_ids.add(article["id"])
            if article["is_korea"]:
                korea_news.append(article)
            else:
                general_news.append(article)

    if skipped:
        print(f"[중복 스킵] 이미 브리핑된 기사 {skipped}건 제외")

    # 상한 적용
    korea_news   = korea_news[:MAX_KOREA_ITEMS]
    general_news = general_news[:MAX_GENERAL_ITEMS]

    print(f"[수집 완료] 한국관련 {len(korea_news)}건 / 일본뉴스 {len(general_news)}건")
    return {"korea": korea_news, "general": general_news}
