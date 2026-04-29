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

    # 2. Gemini로 브리핑 1편 생성 (entity 추출 + 누락 검증 포함)
    briefing = generate_briefing(news_dict, slot=slot, telegram_notify_fn=send_message)
    if not briefing:
        print("[종료] 브리핑 생성 실패")
        send_message("📰 *Japan News Bot*\n⚠️ 브리핑 생성에 실패했습니다. (Gemini API 오류 또는 JSON 파싱 실패)\n서버 로그를 확인해주세요.")
        return

    # 3. Blogger에 브리핑 1편 게시
    post_url = post_briefing(briefing, news_dict)

    # 4. Wiki 기사 단위 적재 (Phase 4)
    from export_to_wiki import export_briefing_to_wiki
    export_briefing_to_wiki(briefing, news_dict)

    # 5. Daily Note 생성/업데이트 (Phase 5)
    from daily_note_writer import write_daily_note
    note_slot = "morning" if slot == "아침" else "evening"

    # Phase 6: 한국 도쿄특파원 기사 수집 → 분류 → Wiki 적재 → Daily Note 통합
    try:
        from korean_correspondent_filter import fetch_korean_correspondent_news
        from correspondent_classifier import classify_correspondent_articles
        from export_to_wiki import export_korean_correspondent_to_wiki

        kr_raw = fetch_korean_correspondent_news()
        if kr_raw:
            cls_result = classify_correspondent_articles(kr_raw)
            value_articles = cls_result["value"]

            if value_articles:
                # entity 추출 (Phase 2 로직 재사용)
                from gemini_process import extract_entities
                value_articles = extract_entities(value_articles)

                # Wiki 적재
                from datetime import datetime
                try:
                    from zoneinfo import ZoneInfo
                    _JST = ZoneInfo("Asia/Tokyo")
                except ImportError:
                    import pytz
                    _JST = pytz.timezone("Asia/Tokyo")
                date_str_p6 = datetime.now(tz=_JST).strftime("%Y-%m-%d")
                export_korean_correspondent_to_wiki(value_articles, date_str_p6, note_slot)

                # Daily Note에 전달
                briefing["_kr_correspondent_articles"] = value_articles
                print(f"[Phase 6] Wiki 적재 완료: {len(value_articles)}건")
            else:
                print("[Phase 6] 적재 대상 기사 없음 (모두 redundant/uncertain)")
        else:
            print("[Phase 6] 도쿄 특파원 기사 수집 결과 없음")
    except Exception as e:
        print(f"[Phase 6] 오류 (파이프라인 계속): {e}")

    write_daily_note(briefing, slot=note_slot)

    # 7. 텔레그램 알림 (브리핑 게시 결과만 — Phase 6 기사는 Wiki only)
    if post_url:
        notify_done([{"title": briefing.get("title", "뉴스 브리핑"), "url": post_url}])
        print(f"[완료] 브리핑 게시 성공")
    else:
        print(f"[완료] 브리핑 게시 실패")


if __name__ == "__main__":
    run_pipeline()
