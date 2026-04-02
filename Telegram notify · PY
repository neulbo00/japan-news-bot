import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def send_message(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[텔레그램] 토큰/채팅ID 미설정 — 알림 스킵")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       text,
        "parse_mode": "Markdown",
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        res.raise_for_status()
        print("[텔레그램] 알림 전송 완료")
    except Exception as e:
        print(f"[텔레그램] 알림 실패: {e}")

def notify_done(posted_list):
    if not posted_list:
        send_message("📰 *Japan News Bot*\n오늘 게시할 뉴스가 없었습니다.")
        return
    lines = [f"📰 *Japan News Bot* — {len(posted_list)}건 게시 완료\n"]
    for item in posted_list[:5]:  # 최대 5건만 표시
        lines.append(f"• [{item['title'][:30]}...]({item['url']})")
    if len(posted_list) > 5:
        lines.append(f"_외 {len(posted_list) - 5}건..._")
    send_message("\n".join(lines))
