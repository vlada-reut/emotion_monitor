from __future__ import annotations

from analytics.stats import age_group_to_russian, emotion_to_russian, gender_to_russian


UNAVAILABLE_WEATHER_TEXT = (
    "Погодные данные пока недоступны. Связь между погодой и настроением аудитории "
    "будет рассчитана после обновления прогноза."
)


def build_text_summary(metrics: dict, weather: dict | None = None, mode: str = "current") -> str:
    people_count = metrics.get("people_count", 0)
    dominant_emotion = emotion_to_russian(metrics.get("dominant_emotion", "unknown"))
    group_mood = metrics.get("group_mood", "неопределенное")
    people_label = "Людей в кадре" if mode == "current" else "Учтено в статистике"

    lines = [
        f"Режим анализа: {'текущий кадр' if mode == 'current' else 'вся сессия'}.",
        f"{people_label}: {people_count}.",
        f"Преобладающая эмоция: {dominant_emotion}.",
        f"Общее настроение группы: {group_mood}.",
    ]

    if unique_people_count := metrics.get("unique_people_count"):
        lines.append(f"Уникальных лиц за сессию: {unique_people_count}.")

    if observations_count := metrics.get("observations_count"):
        lines.append(f"Всего наблюдений: {observations_count}.")

    gender_distribution = metrics.get("gender_distribution", {})
    if gender_distribution:
        gender_text = ", ".join(
            f"{gender_to_russian(key)} — {value}"
            for key, value in gender_distribution.items()
            if value
        )
        if gender_text:
            lines.append(f"Гендерное распределение: {gender_text}.")

    age_distribution = metrics.get("age_group_distribution", {})
    if age_distribution:
        age_text = ", ".join(
            f"{age_group_to_russian(key)} — {value}"
            for key, value in age_distribution.items()
            if value
        )
        if age_text:
            lines.append(f"Возрастные группы: {age_text}.")

    if weather:
        weather_text = str(weather.get("weather_text", "")).strip().lower()
        if weather_text == "погода в данный момент недоступна":
            lines.append(UNAVAILABLE_WEATHER_TEXT)
        else:
            parts = []
            if weather.get("location_name"):
                parts.append(str(weather["location_name"]))
            if weather.get("temperature_c") is not None:
                parts.append(f"{weather['temperature_c']}°C")
            if weather.get("weather_text"):
                parts.append(str(weather["weather_text"]))
            if parts:
                lines.append(f"Погодные условия: {', '.join(parts)}.")

    return "\n".join(lines)
