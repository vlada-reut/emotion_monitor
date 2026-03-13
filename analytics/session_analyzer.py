from __future__ import annotations

from collections import Counter

from analytics.stats import calculate_distribution, dominant_label
from core.models import SessionState


GROUP_MOOD_MAP = {
    "happy": "позитивное",
    "neutral": "спокойное",
    "sad": "подавленное",
    "surprise": "возбужденное",
    "angry": "напряженное",
    "fear": "тревожное",
    "disgust": "негативное",
    "unknown": "неопределенное",
}


def build_current_metrics(session: SessionState) -> dict:
    emotions = [observation.emotion for observation in session.active_faces.values()]
    genders = [observation.gender for observation in session.active_faces.values()]
    age_groups = [observation.age_group for observation in session.active_faces.values()]

    dominant_emotion = dominant_label(emotions)

    return {
        "people_count": len(session.active_faces),
        "distribution": calculate_distribution(emotions),
        "dominant_emotion": dominant_emotion,
        "group_mood": GROUP_MOOD_MAP.get(dominant_emotion, "неопределенное"),
        "gender_distribution": dict(Counter(genders)),
        "age_group_distribution": dict(Counter(age_groups)),
    }



def build_session_metrics(session: SessionState) -> dict:
    emotions = [observation.emotion for observation in session.history]
    genders = [observation.gender for observation in session.history]
    age_groups = [observation.age_group for observation in session.history]

    dominant_emotion = dominant_label(emotions)

    return {
        "people_count": len(session.active_faces),
        "unique_people_count": len(session.unique_face_ids),
        "observations_count": len(session.history),
        "frames_processed": session.frames_processed,
        "distribution": calculate_distribution(emotions),
        "dominant_emotion": dominant_emotion,
        "group_mood": GROUP_MOOD_MAP.get(dominant_emotion, "неопределенное"),
        "gender_distribution": dict(Counter(genders)),
        "age_group_distribution": dict(Counter(age_groups)),
        "fps": round(session.fps, 2),
    }



def build_full_summary(session: SessionState) -> dict:
    return {
        "session_id": session.session_id,
        "started_at": session.started_at,
        "current": build_current_metrics(session),
        "session": build_session_metrics(session),
        "weather": session.last_weather.to_dict() if session.last_weather else None,
    }
