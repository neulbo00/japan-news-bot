"""
JMA(기상청) 도쿄 일기예보 취득 모듈.
API: https://www.jma.go.jp/bosai/forecast/data/forecast/130000.json
  130000 = 도쿄도 (시나가와 포함)

사용:
  from weather_jma import get_today_weather
  weather = get_today_weather()   # dict | None

CLI 테스트:
  python weather_jma.py --test
"""
import argparse
import json
import sys
from datetime import datetime
import requests

try:
    from zoneinfo import ZoneInfo
    JST = ZoneInfo("Asia/Tokyo")
except ImportError:
    import pytz
    JST = pytz.timezone("Asia/Tokyo")

JMA_URL = "https://www.jma.go.jp/bosai/forecast/data/forecast/130000.json"
HEADERS = {"User-Agent": "JapanNewsBot/2.0"}

# 강수확률 시간대 레이블 (JMA 시간대: 00-06 / 06-12 / 12-18 / 18-24)
RAIN_SLOTS = ["morning", "afternoon", "evening", "night"]
RAIN_LABELS = {
    "morning":   "오전",
    "afternoon": "오후",
    "evening":   "저녁",
    "night":     "야간",
}

# 날씨 코드 → 한국어 요약 (주요 코드만)
WEATHER_CODE_MAP = {
    "100": "맑음", "101": "맑음 → 흐림", "102": "맑음, 일부 비",
    "103": "맑음, 때때로 비", "104": "맑음, 눈 또는 비",
    "110": "맑음 → 흐림", "111": "맑음 → 흐림 → 비",
    "112": "맑음 → 비", "113": "맑음 → 비 또는 눈",
    "200": "흐림", "201": "흐림 → 맑음", "202": "흐림, 일부 비",
    "203": "흐림, 때때로 비", "204": "흐림, 눈 또는 비",
    "205": "흐림, 때때로 비 또는 눈", "206": "흐림 후 비",
    "207": "흐림 후 눈 또는 비", "208": "흐림 후 비 또는 눈",
    "209": "안개", "210": "흐림 → 비",
    "211": "흐림 → 비", "212": "흐림 → 비",
    "218": "흐림 → 비 또는 눈", "219": "흐림 → 눈",
    "300": "비", "301": "비 → 맑음", "302": "비, 때때로 눈",
    "303": "비 또는 눈", "304": "때때로 비",
    "400": "눈", "401": "눈 → 비", "402": "눈, 때때로 비",
    "403": "눈 또는 비",
}

WEATHER_EMOJI = {
    "맑음": "☀️", "흐림": "☁️", "비": "☂️", "눈": "❄️",
    "안개": "🌫️",
}


def _weather_summary(code: str, text: str) -> str:
    """날씨 코드 → 한국어 요약. 코드 없으면 원문 텍스트 요약."""
    if code and code in WEATHER_CODE_MAP:
        return WEATHER_CODE_MAP[code]
    if text:
        # 일본어 원문에서 키워드 기반 요약
        if "晴れ" in text and "雨" in text:
            return "맑음, 일부 비"
        if "晴れ" in text:
            return "맑음"
        if "曇り" in text and "雨" in text:
            return "흐림 후 비"
        if "曇り" in text:
            return "흐림"
        if "雨" in text:
            return "비"
        if "雪" in text:
            return "눈"
    return "확인 불가"


def _add_emoji(summary: str) -> str:
    for kw, emoji in WEATHER_EMOJI.items():
        if kw in summary:
            return f"{emoji} {summary}"
    return f"🌤️ {summary}"


def get_today_weather() -> dict | None:
    """
    도쿄 오늘/내일 날씨 반환.
    {
      "summary": "흐림 → 오후 비",
      "temp_max": 18,
      "temp_min": 12,
      "rain_chances": {"morning": 30, "afternoon": 70, "evening": 60, "night": 40},
      "tomorrow_summary": "맑음",
      "tomorrow_temp_max": 21,
    }
    실패 시 None
    """
    try:
        res = requests.get(JMA_URL, headers=HEADERS, timeout=10)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        print(f"[JMA] API 오류: {e}")
        return None

    try:
        # data[0]: 도쿄都 광역 예보, data[1]: 세부 예보
        # timeSeries[0]: 天気 (날씨 코드/텍스트)
        # timeSeries[1]: 降水確率 (강수확률)
        # timeSeries[2]: 気温 (기온)
        ts = data[0]["timeSeries"]

        # ── 날씨 코드 ───────────────────────────────────────────────────────
        weather_series = ts[0]
        weather_times  = weather_series["timeDefines"]  # ISO datetime strings
        areas          = weather_series["areas"]
        # 도쿄지방(Tokyo) area 선택 (첫 번째 area 사용)
        area_w = areas[0]
        codes  = area_w.get("weatherCodes", [])
        texts  = area_w.get("weathers", [])

        today_code    = codes[0] if codes else ""
        today_text    = texts[0] if texts else ""
        tomorrow_code = codes[1] if len(codes) > 1 else ""
        tomorrow_text = texts[1] if len(texts) > 1 else ""

        today_summary    = _weather_summary(today_code, today_text)
        tomorrow_summary = _weather_summary(tomorrow_code, tomorrow_text)

        # ── 강수확률 ─────────────────────────────────────────────────────────
        rain_chances: dict[str, int] = {}
        if len(ts) > 1:
            rain_series = ts[1]
            rain_areas  = rain_series["areas"]
            area_r = rain_areas[0]
            pops = area_r.get("pops", [])  # 최대 8개 (오늘 4 + 내일 4)
            slots_today = pops[:4]  # 오늘 00-06 / 06-12 / 12-18 / 18-24
            for i, slot_name in enumerate(RAIN_SLOTS):
                if i < len(slots_today):
                    try:
                        rain_chances[slot_name] = int(slots_today[i])
                    except (ValueError, TypeError):
                        rain_chances[slot_name] = -1  # 불명

        # ── 기온 (data[1] 세부 예보에서 취득) ───────────────────────────────
        temp_max = temp_min = tomorrow_temp_max = None
        try:
            ts1 = data[1]["timeSeries"]
            # ts1[1]: tempsMin / tempsMax (오늘, 내일, 모레 순)
            area_t = ts1[1]["areas"][0]
            mins = area_t.get("tempsMin", [])
            maxs = area_t.get("tempsMax", [])
            # index 0 = 오늘 (새벽엔 빈 값일 수 있음), index 1 = 내일
            def _safe_int(lst, idx):
                if idx < len(lst) and lst[idx] not in ("", None):
                    try:
                        return int(lst[idx])
                    except (ValueError, TypeError):
                        pass
                return None
            temp_min      = _safe_int(mins, 0)
            temp_max      = _safe_int(maxs, 0)
            # 오늘 값이 비어있으면 단기예보 timeSeries[2] 시도
            if temp_max is None and len(ts) > 2:
                area_t0 = ts[2]["areas"][0]
                temp_min = _safe_int(area_t0.get("tempsMin", []), 0)
                temp_max = _safe_int(area_t0.get("tempsMax", []), 0)
            tomorrow_temp_max = _safe_int(maxs, 1)
        except Exception:
            pass

        return {
            "summary":          today_summary,
            "temp_max":         temp_max,
            "temp_min":         temp_min,
            "rain_chances":     rain_chances,
            "tomorrow_summary": tomorrow_summary,
            "tomorrow_temp_max": tomorrow_temp_max,
        }

    except Exception as e:
        print(f"[JMA] 파싱 오류: {e}")
        return None


def format_weather_block(weather: dict, slot: str = "아침") -> str:
    """날씨 dict → 브리핑용 마크다운 블록."""
    if not weather:
        return ""

    summary = _add_emoji(weather.get("summary", ""))
    t_max   = weather.get("temp_max")
    t_min   = weather.get("temp_min")
    rain    = weather.get("rain_chances", {})

    temp_str = ""
    if t_min is not None and t_max is not None:
        temp_str = f" / 최저 {t_min}℃ / 최고 {t_max}℃"
    elif t_max is not None:
        temp_str = f" / 최고 {t_max}℃"

    rain_parts = []
    for slot_key in RAIN_SLOTS:
        val = rain.get(slot_key, -1)
        if val >= 0:
            rain_parts.append(f"{RAIN_LABELS[slot_key]} {val}%")
    rain_str = " / ".join(rain_parts) if rain_parts else ""

    lines = [
        "## ☀️ 오늘의 도쿄",
        f"{summary}{temp_str}",
    ]
    if rain_str:
        lines.append(f"강수확률: {rain_str}")

    if slot == "저녁":
        tmr = weather.get("tomorrow_summary")
        tmr_max = weather.get("tomorrow_temp_max")
        if tmr:
            tmr_str = _add_emoji(tmr)
            if tmr_max is not None:
                tmr_str += f" (예상 최고 {tmr_max}℃)"
            lines.append(f"내일: {tmr_str}")

    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()

    if args.test:
        print("[JMA] 날씨 데이터 취득 테스트...")
        weather = get_today_weather()
        if weather:
            print("✅ 성공:")
            print(json.dumps(weather, ensure_ascii=False, indent=2))
            print("\n--- 아침 블록 ---")
            print(format_weather_block(weather, "아침"))
            print("\n--- 저녁 블록 ---")
            print(format_weather_block(weather, "저녁"))
        else:
            print("❌ 실패: None 반환")
            sys.exit(1)
