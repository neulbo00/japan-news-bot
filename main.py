import schedule
import time
from datetime import datetime

from news_fetch import fetch_japan_news
from gemini_process import generate_briefing
from blogger_post import post_briefing
from telegram_notify import notify_done
from config import SCHEDULE_HOURS


def run_pipeline():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n{'='*50}")
    print(f"[시작] {now}")
    print(f"{'='*50}")

    # 1. 뉴스 수집 (한국관련 / 일본뉴스 분류)
    news_dict = fetch_japan_news()
    total = len(news_dict["korea"]) + len(news_dict["general"])
    if total == 0:
        print("[종료] 수집된 신규 뉴스 없음")
        return

    # 2. Gemini — 브리핑 1편 생성
    briefing = generate_briefing(news_dict)
    if not briefing:
        print("[종료] 브리핑 생성 실패")
        return

    # 3. Blogger — 브리핑 1건 게시
    post_url = post_briefing(briefing, news_dict)

    # 4. 텔레그램 알림
    if post_url:
        notify_done([{"title": briefing.get("title", "뉴스 브리핑"), "url": post_url}])
        print(f"[완료] 브리핑 게시 성공")
    else:
        print(f"[완료] 브리핑 게시 실패")


if __name__ == "__main__":
    print("[Japan News Bot 시작]")
    print(f"스케줄: 매일 {SCHEDULE_HOURS}시 실행\n")

    for hour in SCHEDULE_HOURS:
        schedule.every().day.at(f"{hour:02d}:00").do(run_pipeline)

    # 테스트용 1회 즉시 실행 (필요 없으면 주석처리)
    # run_pipeline()

    while True:
        schedule.run_pending()
        time.sleep(60)
