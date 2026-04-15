import time
import requests
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
    JST = ZoneInfo("Asia/Tokyo")
except ImportError:
    import pytz
    JST = pytz.timezone("Asia/Tokyo")

from config import (
    BLOGGER_BLOG_ID,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REFRESH_TOKEN,
)

BLOGGER_API = "https://blogger.googleapis.com/v3/blogs"
TOKEN_URL   = "https://oauth2.googleapis.com/token"


def _get_access_token():
    if not all([GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN]):
        raise RuntimeError(".env에 Google OAuth2 자격증명이 필요합니다.")
    resp = requests.post(TOKEN_URL, data={
        "grant_type":    "refresh_token",
        "client_id":     GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": GOOGLE_REFRESH_TOKEN,
    }, timeout=10)
    resp.raise_for_status()
    return resp.json()["access_token"]


def _build_briefing_html(briefing):
    """브리핑 딕셔너리를 Blogger용 HTML로 변환"""
    now = datetime.now(tz=JST).strftime("%Y년 %m월 %d일 %H:%M")
    sections = []

    # 리드
    lead = briefing.get("lead", "")
    if lead:
        sections.append(f'<p style="font-size:17px; font-weight:bold; color:#333; line-height:1.8;">{lead}</p>')
        sections.append('<hr style="border:none; border-top:2px solid #4285f4; margin:20px 0;"/>')

    # 한국·일본 관련 뉴스 섹션
    korea_items = briefing.get("korea_section") or []
    if korea_items:
        sections.append('<h3 style="color:#c0392b; font-size:18px; margin-top:24px;">📌 한일 관련 주요 뉴스</h3>')
        for item in korea_items:
            sections.append(f'''<div style="margin:12px 0; padding:12px 16px; background:#fff5f5; border-left:4px solid #c0392b; border-radius:4px;">
  <p style="font-weight:bold; margin:0 0 6px 0; font-size:15px;">{item.get("headline","")}</p>
  <p style="margin:0; line-height:1.8; color:#444;">{item.get("body","")}</p>
</div>''')

    # 일본 주요 뉴스 섹션
    japan_items = briefing.get("japan_section") or []
    if japan_items:
        sections.append('<h3 style="color:#2c3e50; font-size:18px; margin-top:24px;">📰 오늘의 일본 주요 뉴스</h3>')
        for item in japan_items:
            sections.append(f'''<div style="margin:10px 0; padding:10px 16px; background:#f8f9fa; border-left:4px solid #4285f4; border-radius:4px;">
  <p style="font-weight:bold; margin:0 0 4px 0; font-size:14px;">{item.get("headline","")}</p>
  <p style="margin:0; line-height:1.8; color:#555;">{item.get("body","")}</p>
</div>''')

    # 푸터
    sections.append(f'''<hr style="border:none; border-top:1px solid #eee; margin:28px 0 12px 0;"/>
<p style="color:#aaa; font-size:12px; line-height:1.6;">
  🤖 이 브리핑은 일본 뉴스를 <b>Google Gemini AI</b>가 수집·번역·요약해 자동 작성한 콘텐츠입니다.<br>
  ⏱ 작성 시각: {now} (JST)
</p>''')

    return f'<div style="font-family:\'Noto Sans KR\', sans-serif; line-height:1.8; max-width:740px; margin:auto; padding:8px;">\n' + \
           "\n".join(sections) + "\n</div>"


def post_briefing(briefing, news_dict):
    """
    Gemini가 생성한 브리핑을 Blogger에 1건 게시.
    news_dict: 원본 뉴스 dict (posted_ids 기록용)
    반환: 게시된 URL 또는 None
    """
    if not BLOGGER_BLOG_ID:
        print("[Blogger] BLOGGER_BLOG_ID 미설정")
        return None

    try:
        access_token = _get_access_token()
    except Exception as e:
        print(f"[Blogger] 토큰 발급 실패: {e}")
        return None

    title   = briefing.get("title", datetime.now(tz=JST).strftime("%m월 %d일 일본 뉴스 브리핑"))
    labels  = briefing.get("labels", ["브리핑", "일본뉴스"])
    content = _build_briefing_html(briefing)

    url = f"{BLOGGER_API}/{BLOGGER_BLOG_ID}/posts/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type":  "application/json",
    }
    body = {"title": title, "content": content, "labels": labels}

    try:
        resp = requests.post(url, headers=headers, json=body, timeout=15)
        resp.raise_for_status()
        post_url = resp.json().get("url", "")
        print(f"[게시 완료] {title} → {post_url}")
        return post_url
    except Exception as e:
        print(f"[게시 실패] {e}")
        return None
