import os
from pathlib import Path
from dotenv import load_dotenv

# .env 우선순위: .secrets (OneDrive 외부) → 프로젝트 로컬
_SECRETS_ENV = Path.home() / ".secrets" / "japan-news-bot.env"
_LOCAL_ENV   = Path(__file__).resolve().parent / ".env"

if _SECRETS_ENV.exists():
    load_dotenv(_SECRETS_ENV)
else:
    load_dotenv(_LOCAL_ENV)

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
