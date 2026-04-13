import os
from pathlib import Path
from datetime import datetime

# 위키 업로드 경로 설정 (사용자 경로 기반)
WIKI_RAW_PATH = Path(r"C:\Users\neulb\OneDrive\Documents\wiki\raw\news_bot")

def export_briefing_to_wiki(briefing_data: dict, news_dict: dict):
    """
    briefing_data: {"title": "...", "sections": "..."} 혹은 단일 텍스트
    news_dict: 원본 뉴스 데이터 (출처 확인용)
    """
    try:
        WIKI_RAW_PATH.mkdir(parents=True, exist_ok=True)
        
        title = briefing_data.get("title", "No Title")
        # 파일명 생성: 2026-04-12-morning.md 형식
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d-%H%M")
        filename = f"{timestamp}-briefing.md"
        
        target_file = WIKI_RAW_PATH / filename
        
        # 마크다운 내용 구성
        content = []
        content.append(f"---")
        content.append(f"title: {title}")
        content.append(f"date: {now.strftime('%Y-%m-%d')}")
        content.append(f"source: japan-news-bot")
        content.append(f"type: news-briefing")
        content.append(f"---")
        content.append(f"\n# {title}\n")
        
        # 브리핑 본문 (HTML인 경우 간단히 텍스트 변환되거나 이미 텍스트인 경우 처리)
        # news-bot의 gemini_process 결과물 구조에 맞춰 조정 필요
        body = briefing_data.get("briefing_text", "") or str(briefing_data)
        content.append(body)
        
        content.append("\n\n## 🔗 원본 데이터 참조\n")
        for cat in ["korea", "general"]:
            if cat in news_dict:
                for item in news_dict[cat]:
                    content.append(f"- [{item['title']}]({item['link']})")

        target_file.write_text("\n".join(content), encoding="utf-8")
        print(f"  📂 [Wiki Export] 완료: {target_file}")
        return True
    except Exception as e:
        print(f"  ⚠️ [Wiki Export] 실패: {e}")
        return False
