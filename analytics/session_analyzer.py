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


def _select_people_for_session_stats(
    session: SessionState,
    min_observations: int,
) -> list:
    threshold = max(1, int(min_observations))
    return [
        person
        for person in session.people.values()
        if person.observations_count >= threshold
    ]


def build_current_metrics(session: SessionState) -> dict:
    emotions = [observation.emotion for observation in session.active_faces.values()]
    genders = [observation.gender for observation in session.active_faces.values()]
    age_groups = [observation.age_group for observation in session.active_faces.values()]

    dominant_emotion = dominant_label(emotions)

    return {
        "people_count": len(session.active_faces),
        "distribution": calculate_distribution(emotions),
        "unique_emotions": sorted({emotion for emotion in emotions if emotion and emotion != "unknown"}),
        "dominant_emotion": dominant_emotion,
        "group_mood": GROUP_MOOD_MAP.get(dominant_emotion, "неопределенное"),
        "gender_distribution": dict(Counter(genders)),
        "age_group_distribution": dict(Counter(age_groups)),
    }



def build_session_metrics(session: SessionState, min_observations: int = 1) -> dict:
    people = _select_people_for_session_stats(session, min_observations)
    dominant_emotions = [person.dominant_emotion() for person in people]
    dominant_genders = [person.dominant_gender() for person in people]
    dominant_age_groups = [person.dominant_age_group() for person in people]

    dominant_emotion = dominant_label(dominant_emotions)

    return {
        "people_count": len(people),
        "active_people_count": len(session.active_faces),
        "unique_people_count": len(session.people),
        "observations_count": len(session.history),
        "frames_processed": session.frames_processed,
        "min_observations_for_stats": max(1, int(min_observations)),
        "distribution": calculate_distribution(dominant_emotions),
        "unique_emotions": sorted(
            {emotion for emotion in dominant_emotions if emotion and emotion != "unknown"}
        ),
        "dominant_emotion": dominant_emotion,
        "group_mood": GROUP_MOOD_MAP.get(dominant_emotion, "неопределенное"),
        "gender_distribution": dict(Counter(dominant_genders)),
        "age_group_distribution": dict(Counter(dominant_age_groups)),
        "fps": round(session.fps, 2),
    }



def build_full_summary(session: SessionState, min_observations: int = 1) -> dict:
    people_summary = []
    for person in session.people.values():
        people_summary.append(
            {
                "person_id": person.person_id,
                "user_id": person.user_id,
                "display_name": person.display_name,
                "first_seen": person.first_seen,
                "last_seen": person.last_seen,
                "track_ids": sorted(person.track_ids),
                "observations_count": person.observations_count,
                "dominant_emotion": person.dominant_emotion(),
                "dominant_gender": person.dominant_gender(),
                "dominant_age_group": person.dominant_age_group(),
            }
        )

    return {
        "session_id": session.session_id,
        "started_at": session.started_at,
        "current": build_current_metrics(session),
        "session": build_session_metrics(session, min_observations=min_observations),
        "people": people_summary,
        "weather": session.last_weather.to_dict() if session.last_weather else None,
    }
