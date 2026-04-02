import schedule
import time
from datetime import datetime

from news_fetch import fetch_japan_news
from gemini_process import translate_all
from tistory_post import post_all
from telegram_notify import notify_done
from config import SCHEDULE_HOURS

def run_pipeline():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n{'='*50}")
    print(f"[시작] {now}")
    print(f"{'='*50}")

    # 1. 뉴스 수집
    news = fetch_japan_news()
    if not news:
        print("[종료] 수집된 뉴스 없음")
        return

    # 2. Gemini 번역+요약
    translated = translate_all(news)

    # 3. 티스토리 게시
    posted = post_all(translated)

    # 4. 텔레그램 알림
    notify_done(posted)

    print(f"[완료] {len(posted)}/{len(news)}건 게시")

if __name__ == "__main__":
    print("[Japan News Bot 시작]")
    print(f"스케줄: 매일 {SCHEDULE_HOURS}시 실행\n")

    for hour in SCHEDULE_HOURS:
        schedule.every().day.at(f"{hour:02d}:00").do(run_pipeline)

    # 시작 시 1회 즉시 실행 (테스트용 — 필요 없으면 주석처리)
    # run_pipeline()

    while True:
        schedule.run_pending()
        time.sleep(60)
