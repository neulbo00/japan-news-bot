import os
from dotenv import load_dotenv

load_dotenv()

# Gemini AI
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Google Blogger (OAuth2)
BLOGGER_BLOG_ID      = os.getenv("BLOGGER_BLOG_ID")       # Blogger 관리 URL에서 확인
GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID")      # GCP OAuth2 클라이언트 ID
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")  # GCP OAuth2 클라이언트 시크릿
GOOGLE_REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN")  # setup_google_auth.py 로 발급

# 텔레그램
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

# 스케줄 (24시간제)
SCHEDULE_HOURS = [7, 19]  # 오전 7시, 오후 7시

# 수집 뉴스 건수
MAX_NEWS_PER_SOURCE = 5
