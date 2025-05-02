import requests

# 발급받은 정보로 교체
CLIENT_ID = "f6oizljb7n"
CLIENT_SECRET = "cRAC9CTqXmLsERKeT9bwpcbn1fc75OcoACkAh4G3"

def translate_to_korean(news_list):
    translated_list = []

    for item in news_list:
        text = item['content'] or item['title'] or ""
        if not text.strip():
            translated_list.append({
                "title": item['title'],
                "content": "[번역 실패: 내용 없음]"
            })
            continue

        headers = {
            "X-NCP-APIGW-API-KEY-ID": CLIENT_ID,
            "X-NCP-APIGW-API-KEY": CLIENT_SECRET
        }

        data = {
            "source": "ja",
            "target": "ko",
            "text": text
        }

        try:
            response = requests.post(
                "https://naveropenapi.apigw.ntruss.com/nmt/v1/translation",
                headers=headers,
                data=data
            )
            result = response.json()

            if 'message' in result and 'result' in result['message']:
                translated_text = result['message']['result']['translatedText']
            else:
                raise ValueError(f"API 응답 오류: {result}")

            translated_list.append({
                "title": item['title'],
                "content": translated_text
            })

        except Exception as e:
            print("번역 실패:", e)
            translated_list.append({
                "title": item['title'],
                "content": "[번역 실패]"
            })

    return translated_list
