from news_fetch import fetch_japan_news
from translate import translate_to_korean

def main():
    # 1. 일본 뉴스 수집
    news = fetch_japan_news()
    print(f"[수집된 뉴스 {len(news)}건]")

    # 2. 뉴스 번역
    translated_news = translate_to_korean(news)
    print("[한글 번역 결과]")

    # 3. 출력
    for i, article in enumerate(translated_news, 1):
        print(f"\n📰 {i}. {article['title']}")
        print(article['content'])

if __name__ == "__main__":
    main()
