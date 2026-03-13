from __future__ import annotations

from collections import Counter
from typing import Iterable


EMOTION_ORDER = [
    "happy",
    "neutral",
    "sad",
    "surprise",
    "angry",
    "fear",
    "disgust",
    "unknown",
]

EMOTION_LABELS_RU = {
    "happy": "радость",
    "neutral": "нейтральное",
    "sad": "грусть",
    "surprise": "удивление",
    "angry": "злость",
    "fear": "страх",
    "disgust": "отвращение",
    "unknown": "неизвестно",
}

GENDER_LABELS_RU = {
    "Man": "мужской",
    "Woman": "женский",
    "male": "мужской",
    "female": "женский",
    "unknown": "неизвестно",
}

AGE_GROUP_LABELS_RU = {
    "child": "ребенок",
    "teen": "подросток",
    "young_adult": "молодой взрослый",
    "adult": "взрослый",
    "senior": "пожилой",
    "unknown": "неизвестно",
}


def normalize_emotion(value: str | None) -> str:
    if not value:
        return "unknown"
    return value.strip().lower()


def calculate_distribution(data: Iterable[str]) -> dict[str, float]:
    items = [normalize_emotion(item) for item in data if item is not None]
    if not items:
        return {}

    counter = Counter(items)
    total = sum(counter.values())

    ordered_keys = [key for key in EMOTION_ORDER if key in counter]
    remaining_keys = [key for key in counter.keys() if key not in ordered_keys]

    result: dict[str, float] = {}
    for key in ordered_keys + sorted(remaining_keys):
        result[key] = round(counter[key] / total * 100, 2)

    return result


def dominant_label(data: Iterable[str], default: str = "unknown") -> str:
    items = [item for item in data if item is not None]
    if not items:
        return default
    return Counter(items).most_common(1)[0][0]


def emotion_to_russian(emotion: str) -> str:
    return EMOTION_LABELS_RU.get(normalize_emotion(emotion), emotion)


def gender_to_russian(gender: str) -> str:
    return GENDER_LABELS_RU.get(gender, gender)


def age_group_to_russian(age_group: str) -> str:
    return AGE_GROUP_LABELS_RU.get(age_group, age_group)
