import requests

# 발급받은 API 키를 여기에 입력
API_KEY = "3255f9616b8d4400bbf2d01d4818af9a"

def fetch_japan_news():
    url = "https://newsapi.org/v2/everything"
    params = {
        "apiKey": API_KEY,
        "q": "Japan OR 일본",   # 일본 관련 뉴스로 범위 넓히기
        "sortBy": "publishedAt",
        "language": "en",       # 일단 영어 뉴스라도 받아보는 방식
        "pageSize": 5
    }

    response = requests.get(url, params=params)
    data = response.json()

    print("[DEBUG] 응답 내용:", data)
    
    news_list = []
    for article in data.get("articles", []):
        news_list.append({
            "title": article["title"],
            "content": article["description"] or article["content"] or ""
        })

    return news_list
