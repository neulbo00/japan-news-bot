from news_fetch import fetch_japan_news
from translate import translate_to_korean
from blog_post import post_to_naver_blog  # ← 이 줄 위치는 맨 위로 옮깁니다

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

    # 4. 블로그 게시 (지금은 출력만)
    post_to_naver_blog(translated_news)   # ← 이 줄이 들여쓰기 되어 있어야 합니다!

if __name__ == "__main__":
    main()
