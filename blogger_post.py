import time
import requests
from config import (
    BLOGGER_BLOG_ID,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REFRESH_TOKEN,
)

BLOGGER_API = "https://blogger.googleapis.com/v3/blogs"
TOKEN_URL   = "https://oauth2.googleapis.com/token"


def _get_access_token():
    """저장된 refresh_token으로 access_token을 발급받습니다."""
    if not all([GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN]):
        raise RuntimeError("[Blogger] .env에 GOOGLE_CLIENT_ID / SECRET / REFRESH_TOKEN 이 필요합니다.")
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type":    "refresh_token",
            "client_id":     GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "refresh_token": GOOGLE_REFRESH_TOKEN,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _build_html(article):
    """기사 딕셔너리에서 Blogger용 HTML 본문 생성"""
    stars = "⭐" * article.get("importance_score", 3)
    reason = article.get("importance_reason", "")
    return f"""<div style="font-family: 'Noto Sans KR', sans-serif; line-height: 1.8; max-width: 720px; margin: auto;">
  <p style="color:#888; font-size:13px;">
    📰 원문 출처: <b>{article['source']}</b> &nbsp;|&nbsp;
    <a href="{article['link']}" target="_blank" rel="noopener">원문 보기</a>
    &nbsp;|&nbsp; 중요도: {stars}
  </p>
  {f'<p style="color:#666; font-size:12px; font-style:italic;">💡 {reason}</p>' if reason else ''}
  <hr style="border:none; border-top:1px solid #eee;"/>
  <p style="font-size:16px;">{article['summary_ko']}</p>
  <hr style="border:none; border-top:1px solid #eee;"/>
  <p style="color:#aaa; font-size:12px;">🤖 이 글은 일본 뉴스를 Google Gemini AI가 번역·요약한 자동 게시글입니다.</p>
</div>""".strip()


def post_article(article, access_token):
    """Blogger API v3로 글 1건 게시"""
    if not BLOGGER_BLOG_ID:
        print("[Blogger] BLOGGER_BLOG_ID 미설정 — 게시 스킵")
        return None
    url = f"{BLOGGER_API}/{BLOGGER_BLOG_ID}/posts/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type":  "application/json",
    }
    body = {
        "title":   article["title_ko"],
        "content": _build_html(article),
        "labels":  [article.get("category", "일본뉴스"), "자동게시"],
    }
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=15)
        resp.raise_for_status()
        post_url = resp.json().get("url", "")
        print(f"[게시 완료] {article['title_ko'][:30]}... → {post_url}")
        return post_url
    except Exception as e:
        print(f"[게시 실패] {article['title_ko'][:30]}... → {e}")
        return None


def post_all(news_list):
    """뉴스 리스트 전체를 Blogger에 게시"""
    try:
        access_token = _get_access_token()
    except Exception as e:
        print(f"[Blogger] 토큰 발급 실패: {e}")
        return []

    urls = []
    for article in news_list:
        post_url = post_article(article, access_token)
        if post_url:
            urls.append({"title": article["title_ko"], "url": post_url})
        time.sleep(2)  # Blogger API rate limit 방지
    return urls
