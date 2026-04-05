"""
Google OAuth2 인증 초기 설정 스크립트
─────────────────────────────────────
사전 준비:
  1. Google Cloud Console (https://console.cloud.google.com) 에서:
     - 프로젝트 생성
     - Blogger API v3 활성화
     - OAuth 2.0 클라이언트 ID 생성 (유형: 웹 애플리케이션)
     - 승인된 리디렉션 URI 에 "http://localhost:8080" 추가
  2. .env 파일에 아래 값 설정:
       GOOGLE_CLIENT_ID=...
       GOOGLE_CLIENT_SECRET=...
  3. 블로그 ID 확인:
     Blogger 관리 페이지 URL → https://www.blogger.com/blog/posts/{블로그ID}

실행 방법:
  python setup_google_auth.py

완료 후:
  출력된 GOOGLE_REFRESH_TOKEN 을 .env 파일에 추가하세요.
"""

import os
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
REDIRECT_URI  = "http://localhost:8080"
SCOPE         = "https://www.googleapis.com/auth/blogger"

_auth_code = None


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _auth_code
        params     = parse_qs(urlparse(self.path).query)
        _auth_code = params.get("code", [None])[0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(
            "<h2 style='font-family:sans-serif;color:green'>✅ 인증 완료! 이 탭을 닫아도 됩니다.</h2>".encode()
        )

    def log_message(self, *args):
        pass  # 불필요한 서버 로그 숨김


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("[오류] .env 파일에 GOOGLE_CLIENT_ID 와 GOOGLE_CLIENT_SECRET 을 먼저 설정하세요.")
        return

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id":     CLIENT_ID,
        "redirect_uri":  REDIRECT_URI,
        "response_type": "code",
        "scope":         SCOPE,
        "access_type":   "offline",
        "prompt":        "consent",
    })

    print("=" * 60)
    print("Google Blogger OAuth2 인증 설정")
    print("=" * 60)
    print("\n브라우저에서 Google 인증 페이지를 열고 있습니다...")
    print(f"\n자동으로 열리지 않으면 아래 URL을 복사하세요:\n{auth_url}\n")
    webbrowser.open(auth_url)

    print("인증 완료를 기다리는 중... (브라우저에서 Google 계정 로그인 후 허용 클릭)")
    server = HTTPServer(("localhost", 8080), _CallbackHandler)
    server.handle_request()

    if not _auth_code:
        print("[오류] 인증 코드를 받지 못했습니다. 다시 시도하세요.")
        return

    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code":          _auth_code,
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri":  REDIRECT_URI,
            "grant_type":    "authorization_code",
        },
        timeout=10,
    )
    resp.raise_for_status()
    refresh_token = resp.json().get("refresh_token", "")

    print("\n" + "=" * 60)
    print("✅ 리프레시 토큰 발급 완료!")
    print("=" * 60)
    print("\n.env 파일에 아래 줄을 추가하세요:\n")
    print(f"GOOGLE_REFRESH_TOKEN={refresh_token}\n")


if __name__ == "__main__":
    main()
