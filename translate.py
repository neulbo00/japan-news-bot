# ⚠️ 이 파일은 Papago API 테스트용 임시 파일입니다.
# 현재 파이프라인에서는 사용되지 않습니다. (gemini_process.py 사용 중)
# API 키는 반드시 .env 파일에 저장하세요.

import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY_ID = os.getenv("NAVER_API_KEY_ID", "")
API_KEY    = os.getenv("NAVER_API_KEY", "")

headers = {
    "X-NCP-APIGW-API-KEY-ID": API_KEY_ID,
    "X-NCP-APIGW-API-KEY":    API_KEY,
    "Content-Type": "application/x-www-form-urlencoded"
}

data = {
    "source": "ja",
    "target": "ko",
    "text": "おはようございます"
}

response = requests.post(
    "https://naveropenapi.apigw.ntruss.com/nmt/v1/translation",
    headers=headers,
    data=data
)

print("응답 코드:", response.status_code)
print("응답 내용:", response.text)
