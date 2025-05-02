from googletrans import Translator

def translate_to_korean(news_list):
    translator = Translator()
    translated_list = []

    for item in news_list:
        try:
            title = item['title'] or ""
            content = item['content'] or ""

            # 제목과 내용 중에서 번역 가능한 부분 선택
            if content.strip():
                target_text = content
            elif title.strip():
                target_text = title
            else:
                raise ValueError("내용 없음")

            result = translator.translate(target_text, src='ja', dest='ko')

            translated_item = {
                "title": title,
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
