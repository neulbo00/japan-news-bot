import requests

# 발급받은 API 키를 여기에 입력
API_KEY = "3255f9616b8d4400bbf2d01d4818af9a"

def fetch_japan_news():
    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "apiKey": API_KEY,
        "country": "jp",        # 일본 국가 코드 사용
        "language": "ja",       # 일본어
        "pageSize": 5           # 기사 최대 수
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
