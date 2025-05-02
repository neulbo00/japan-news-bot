import requests
import xml.etree.ElementTree as ET

def fetch_japan_news():
    url = "https://news.yahoo.co.jp/rss/topics/top-picks.xml"
    response = requests.get(url)
    response.encoding = 'utf-8'

    root = ET.fromstring(response.text)
    items = root.findall(".//item")

    news_list = []
    for item in items[:5]:
        title_elem = item.find("title")
        desc_elem = item.find("description")

        title = title_elem.text.strip() if title_elem is not None else "[제목 없음]"
        description = desc_elem.text.strip() if desc_elem is not None else ""

        news_list.append({
            "title": title,
            "content": description
        })

    return news_list
