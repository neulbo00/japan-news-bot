import requests
import xml.etree.ElementTree as ET

def fetch_japan_news():
    url = "https://news.yahoo.co.jp/rss/topics/top-picks.xml"
    response = requests.get(url)
    response.encoding = 'utf-8'  # 일본어 대응

    # XML 파싱
    root = ET.fromstring(response.text)
    items = root.findall(".//item")

    news_list = []
    for item in items[:5]:  # 최대 5개 기사만 수집
        title = item.find("title").text
        description = item.find("description").text
        news_list.append({
            "title": title.strip(),
            "content": description.strip()
        })

    return news_list
