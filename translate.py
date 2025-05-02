from googletrans import Translator

def translate_to_korean(news_list):
    translator = Translator()
    translated_list = []

    for item in news_list:
        try:
            # 빈 문자열이나 None 방지 처리
            content = item['content'] or ""
            if not content.strip():
                raise ValueError("내용 없음")

            result = translator.translate(content, src='ja', dest='ko')

            translated_item = {
                "title": item['title'],
                "content": result.text
            }

        except Exception as e:
            print("번역 실패:", e)
            translated_item = {
                "title": item['title'],
                "content": "[번역 실패]"
            }

        translated_list.append(translated_item)

    return translated_list
