import requests

API_KEY_ID = "f6oizljb7n"
API_KEY = "cRAC9CTqXmLsERKeT9bwpcbn1fc75OcoACkAh4G3"

headers = {
    "X-NCP-APIGW-API-KEY-ID": API_KEY_ID,
    "X-NCP-APIGW-API-KEY": API_KEY,
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
