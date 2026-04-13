from datetime import datetime
try:
    from zoneinfo import ZoneInfo
    JST = ZoneInfo("Asia/Tokyo")
except ImportError:
    import pytz
    JST = pytz.timezone("Asia/Tokyo")

from news_fetch import fetch_japan_news
from gemini_process import generate_briefing
from blogger_post import post_briefing
from telegram_notify import notify_done, send_message


def run_pipeline():
    now_jst = datetime.now(tz=JST)
    now_str = now_jst.strftime("%Y-%m-%d %H:%M")
    print(f"\n{'='*50}")
    print(f"[시작] {now_str}")
    print(f"{'='*50}")

    # 아침(05:00~11:59) / 저녁(그 외) 판단
    slot = "아침" if 5 <= now_jst.hour < 12 else "저녁"

    # 1. 뉴스 수집 (한국관련 / 일본뉴스 분류)
    news_dict = fetch_japan_news()
    total = len(news_dict["korea"]) + len(news_dict["general"])
    if total == 0:
        print("[종료] 수집된 신규 뉴스 없음")
        return

    # 2. Gemini로 브리핑 1편 생성
    briefing = generate_briefing(news_dict, slot=slot)
    if not briefing:
        print("[종료] 브리핑 생성 실패")
        send_message("📰 *Japan News Bot*\n⚠️ 브리핑 생성에 실패했습니다. (Gemini API 오류 또는 JSON 파싱 실패)\n서버 로그를 확인해주세요.")
        return

    # 3. Blogger에 브리핑 1편 게시
    post_url = post_briefing(briefing, news_dict)

    # 4. 위키 Raw 폴더로 전송 (추가)
    from export_to_wiki import export_briefing_to_wiki
    export_briefing_to_wiki(briefing, news_dict)

    # 5. 텔레그램 알림
    if post_url:
        notify_done([{"title": briefing.get("title", "뉴스 브리핑"), "url": post_url}])
        print(f"[완료] 브리핑 게시 성공")
    else:
        print(f"[완료] 브리핑 게시 실패")


if __name__ == "__main__":
    run_pipeline()
