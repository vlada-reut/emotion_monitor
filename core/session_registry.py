from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np

from core.models import FaceObservation, SessionPerson, SessionState


@dataclass(slots=True)
class ReIdConfig:
    similarity_threshold: float = 0.72


class SessionRegistry:
    def __init__(self, session: SessionState, similarity_threshold: float = 0.72) -> None:
        self.session = session
        self.config = ReIdConfig(similarity_threshold=similarity_threshold)
        self._next_person_id = 0

    def begin_frame(self, active_track_ids: Iterable[int]) -> None:
        active_track_ids = set(active_track_ids)
        stale_track_ids = [
            track_id for track_id in self.session.active_track_to_person.keys() if track_id not in active_track_ids
        ]
        for track_id in stale_track_ids:
            del self.session.active_track_to_person[track_id]
            self.session.last_results.pop(track_id, None)
            self.session.last_analysis_frame.pop(track_id, None)

    def resolve_person_id(self, track_id: int, embedding: list[float] | None = None) -> int:
        existing = self.session.active_track_to_person.get(track_id)
        if existing is not None:
            return existing

        matched_person_id = self._match_inactive_person(embedding)
        if matched_person_id is None:
            matched_person_id = self._create_person_id()

        self.session.active_track_to_person[track_id] = matched_person_id
        return matched_person_id

    def register_observation(
        self,
        track_id: int,
        observation: FaceObservation,
        embedding: list[float] | None = None,
    ) -> None:
        person = self.session.people.get(observation.person_id)
        if person is None:
            person = SessionPerson(
                person_id=observation.person_id,
                user_id=observation.user_id,
                display_name=None,
                first_seen=observation.timestamp,
                last_seen=observation.timestamp,
            )
            self.session.people[observation.person_id] = person

        person.register_observation(observation=observation, track_id=track_id, embedding=embedding)
        self.session.history.append(observation)
        self.session.active_faces[observation.person_id] = observation

    def set_active_faces(self, observations_by_person_id: dict[int, FaceObservation]) -> None:
        self.session.active_faces = observations_by_person_id

    def _create_person_id(self) -> int:
        person_id = self._next_person_id
        self._next_person_id += 1
        return person_id

    def _match_inactive_person(self, embedding: list[float] | None) -> int | None:
        if not embedding:
            return None

        current_active_person_ids = set(self.session.active_track_to_person.values())
        best_person_id: int | None = None
        best_similarity = -1.0

        probe = self._to_unit_vector(embedding)
        if probe is None:
            return None

        for person_id, person in self.session.people.items():
            if person_id in current_active_person_ids:
                continue
            if not person.embedding:
                continue

            candidate = self._to_unit_vector(person.embedding)
            if candidate is None:
                continue

            similarity = float(np.dot(probe, candidate))
            if similarity > best_similarity:
                best_similarity = similarity
                best_person_id = person_id

        if best_person_id is None:
            return None
        if best_similarity < self.config.similarity_threshold:
            return None
        return best_person_id

    @staticmethod
    def _to_unit_vector(values: list[float] | None) -> np.ndarray | None:
        if not values:
            return None
        vector = np.asarray(values, dtype=np.float32)
        norm = np.linalg.norm(vector)
        if norm == 0:
            return None
        return vector / norm
