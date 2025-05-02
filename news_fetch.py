import requests

# 발급받은 API 키를 여기에 입력
API_KEY = 3255f9616b8d4400bbf2d01d4818af9a

def fetch_japan_news():
    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "apiKey": API_KEY,
        "q": "Japan",            # "Japan"이 포함된 뉴스
        "language": "ja",        # 일본어 뉴스
        "pageSize": 5            # 최대 5개 기사 (필요 시 조정 가능)
    }

    response = requests.get(url, params=params)
    data = response.json()

    news_list = []
    for article in data.get("articles", []):
        news_list.append({
            "title": article["title"],
            "content": article["description"] or article["content"] or ""
        })

    return news_list
