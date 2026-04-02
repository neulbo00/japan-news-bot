import requests
from config import TISTORY_ACCESS_TOKEN, TISTORY_BLOG_NAME

TISTORY_API = "https://www.tistory.com/apis/post/write"

CATEGORY_MAP = {
    "정치":    "",  # 티스토리 카테고리 ID (설정 후 채워넣기)
    "경제":    "",
    "사회":    "",
    "국제":    "",
    "한국관련": "",
    "기타":    "",
}

def _build_html(article):
    return f"""
<div style="font-family: 'Noto Sans KR', sans-serif; line-height: 1.8;">
  <p style="color:#888; font-size:13px;">
    📰 원문 출처: {article['source']} &nbsp;|&nbsp;
    <a href="{article['link']}" target="_blank">원문 보기</a>
  </p>
  <hr/>
  <p>{article['summary_ko']}</p>
  <hr/>
  <p style="color:#aaa; font-size:12px;">
    🤖 이 글은 일본 뉴스를 AI가 번역·요약한 자동 게시글입니다.
  </p>
</div>
""".strip()

def post_article(article):
    html_content = _build_html(article)
    params = {
        "access_token": TISTORY_ACCESS_TOKEN,
        "output":       "json",
        "blogName":     TISTORY_BLOG_NAME,
        "title":        article["title_ko"],
        "content":      html_content,
        "visibility":   "3",   # 3 = 공개
        "tag":          article["category"],
    }
    category_id = CATEGORY_MAP.get(article["category"], "")
    if category_id:
        params["category"] = category_id

    try:
        res = requests.post(TISTORY_API, data=params, timeout=15)
        res.raise_for_status()
        data = res.json()
        post_url = data.get("tistory", {}).get("url", "")
        print(f"[게시 완료] {article['title_ko'][:30]}... → {post_url}")
        return post_url
    except Exception as e:
        print(f"[게시 실패] {article['title_ko'][:30]}... → {e}")
        return None

def post_all(news_list):
    urls = []
    for article in news_list:
        url = post_article(article)
        if url:
            urls.append({"title": article["title_ko"], "url": url})
    return urls
