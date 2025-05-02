from news_fetch import fetch_japan_news
from translate import translate_to_korean
from blog_post import post_to_naver_blog

news_items = fetch_japan_news()
translated = translate_to_korean(news_items)
post_to_naver_blog(translated)
