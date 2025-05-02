from googletrans import Translator

def translate_to_korean(news_list):
    """
    일본어 뉴스 리스트를 받아, 한글로 번역된 리스트를 반환합니다.
    
    :param news_list: [{"title": "원제목", "content": "일본어 본문"}, ...]
    :return: [{"title": "원제목", "content": "한글 번역"}, ...]
    """
    translator = Translator()
    translated_list = []

    for item in news_list:
        try:
            result = translator.translate(item['content'], src='ja', dest='ko')
            translated_item = {
                "title": item['title'],  # 제목은 번역하지 않음
                "content": result.text   # 본문만 번역
            }
            translated_list.append(translated_item)
        except Exception as e:
            print("번역 실패:", e)
            # 실패한 뉴스는 내용 없이 제목만 전달
            translated_list.append({
                "title": item['title'],
                "content": "[번역 실패]"
            })

    return translated_list
