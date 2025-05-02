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
            "X-Naver-Client-Id": CLIENT_ID,
            "X-Naver-Client-Secret": CLIENT_SECRET
        }

        data = {
            "source": "ja",
            "target": "ko",
            "text": text
        }

        try:
            response = requests.post("https://openapi.naver.com/v1/papago/n2mt",
                                     headers=headers, data=data)
            result = response.json()
            translated_text = result['message']['result']['translatedText']

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
