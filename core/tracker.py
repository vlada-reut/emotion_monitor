from __future__ import annotations

import math
from dataclasses import dataclass

from core.models import TrackDetection


@dataclass(slots=True)
class _TrackState:
    track_id: int
    bbox: tuple[int, int, int, int]
    center: tuple[int, int]
    missed_frames: int = 0


class CentroidTracker:
    def __init__(self, max_distance: int = 70, max_missing: int = 12) -> None:
        self.max_distance = max_distance
        self.max_missing = max_missing
        self._tracks: dict[int, _TrackState] = {}
        self._next_id = 0

    @staticmethod
    def _center(box: tuple[int, int, int, int]) -> tuple[int, int]:
        x1, y1, x2, y2 = box
        return (x1 + x2) // 2, (y1 + y2) // 2

    @staticmethod
    def _distance(a: tuple[int, int], b: tuple[int, int]) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def update(self, detections: list[tuple[int, int, int, int]]) -> list[TrackDetection]:
        if not detections:
            stale_ids = []
            for track_id, track in self._tracks.items():
                track.missed_frames += 1
                if track.missed_frames > self.max_missing:
                    stale_ids.append(track_id)
            for track_id in stale_ids:
                del self._tracks[track_id]
            return []

        detection_centers = [self._center(box) for box in detections]
        unmatched_track_ids = set(self._tracks.keys())
        unmatched_detection_indices = set(range(len(detections)))
        matches: list[tuple[int, int]] = []

        candidate_pairs: list[tuple[float, int, int]] = []
        for track_id, track in self._tracks.items():
            for det_index, det_center in enumerate(detection_centers):
                distance = self._distance(track.center, det_center)
                candidate_pairs.append((distance, track_id, det_index))

        for distance, track_id, det_index in sorted(candidate_pairs, key=lambda item: item[0]):
            if distance > self.max_distance:
                continue
            if track_id not in unmatched_track_ids or det_index not in unmatched_detection_indices:
                continue
            matches.append((track_id, det_index))
            unmatched_track_ids.remove(track_id)
            unmatched_detection_indices.remove(det_index)

        for track_id, det_index in matches:
            bbox = detections[det_index]
            self._tracks[track_id] = _TrackState(
                track_id=track_id,
                bbox=bbox,
                center=detection_centers[det_index],
                missed_frames=0,
            )

        for track_id in list(unmatched_track_ids):
            self._tracks[track_id].missed_frames += 1
            if self._tracks[track_id].missed_frames > self.max_missing:
                del self._tracks[track_id]

        for det_index in unmatched_detection_indices:
            track_id = self._next_id
            self._next_id += 1
            self._tracks[track_id] = _TrackState(
                track_id=track_id,
                bbox=detections[det_index],
                center=detection_centers[det_index],
                missed_frames=0,
            )

        active_tracks = [
            TrackDetection(
                track_id=track.track_id,
                bbox=track.bbox,
                center=track.center,
                missed_frames=track.missed_frames,
            )
            for track in self._tracks.values()
            if track.missed_frames == 0
        ]

        active_tracks.sort(key=lambda item: item.track_id)
        return active_tracks
