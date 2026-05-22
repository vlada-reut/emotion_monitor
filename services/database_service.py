from __future__ import annotations

import json
import math
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core.models import SessionState
from services.config_service import BASE_DIR, DatabaseConfig


KNOWN_AGE_GROUPS = {"child", "teen", "young_adult", "adult", "senior", "unknown"}


@dataclass(slots=True)
class StoredUser:
    user_id: int
    display_name: str
    created_at: str
    updated_at: str
    first_seen_at: str
    last_seen_at: str
    dominant_gender: str
    dominant_age_group: str
    total_sessions: int
    total_observations: int
    last_emotion: str
    notes: str = ""
    embedding_samples: int = 0


@dataclass(slots=True)
class StoredUserSession:
    session_id: str
    started_at: str
    finished_at: str
    observations_count: int
    dominant_emotion: str
    dominant_gender: str
    dominant_age_group: str


class UserDatabaseService:
    def __init__(self, config: DatabaseConfig) -> None:
        db_path = Path(config.path)
        if not db_path.is_absolute():
            db_path = (BASE_DIR / db_path).resolve()

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.similarity_threshold = config.similarity_threshold
        self.search_limit = config.search_limit
        self.max_embeddings_per_user = max(1, int(config.max_embeddings_per_user))
        self.min_samples_for_new_user = max(1, int(config.min_samples_for_new_user))
        self._write_lock = threading.Lock()
        self._embedding_cache: dict[int, list[list[float]]] = {}
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _initialize(self) -> None:
        with self._write_lock:
            with self._connect() as connection:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        display_name TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        first_seen_at TEXT NOT NULL,
                        last_seen_at TEXT NOT NULL,
                        dominant_gender TEXT NOT NULL DEFAULT 'unknown',
                        dominant_age_group TEXT NOT NULL DEFAULT 'unknown',
                        total_sessions INTEGER NOT NULL DEFAULT 0,
                        total_observations INTEGER NOT NULL DEFAULT 0,
                        last_emotion TEXT NOT NULL DEFAULT 'unknown',
                        notes TEXT NOT NULL DEFAULT '',
                        embedding_json TEXT,
                        embedding_samples INTEGER NOT NULL DEFAULT 0
                    );

                    CREATE INDEX IF NOT EXISTS idx_users_display_name
                    ON users(display_name);

                    CREATE INDEX IF NOT EXISTS idx_users_last_seen_at
                    ON users(last_seen_at DESC);

                    CREATE TABLE IF NOT EXISTS user_embeddings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        embedding_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_user_embeddings_user_id
                    ON user_embeddings(user_id, created_at DESC, id DESC);

                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        started_at TEXT NOT NULL,
                        finished_at TEXT NOT NULL,
                        summary_path TEXT NOT NULL DEFAULT '',
                        unique_people_count INTEGER NOT NULL DEFAULT 0,
                        observations_count INTEGER NOT NULL DEFAULT 0,
                        frames_processed INTEGER NOT NULL DEFAULT 0,
                        fps REAL NOT NULL DEFAULT 0
                    );

                    CREATE TABLE IF NOT EXISTS session_users (
                        session_id TEXT NOT NULL,
                        user_id INTEGER NOT NULL,
                        session_person_id INTEGER NOT NULL,
                        first_seen_at TEXT NOT NULL,
                        last_seen_at TEXT NOT NULL,
                        observations_count INTEGER NOT NULL DEFAULT 0,
                        dominant_emotion TEXT NOT NULL DEFAULT 'unknown',
                        dominant_gender TEXT NOT NULL DEFAULT 'unknown',
                        dominant_age_group TEXT NOT NULL DEFAULT 'unknown',
                        track_ids_json TEXT NOT NULL DEFAULT '[]',
                        PRIMARY KEY (session_id, user_id, session_person_id),
                        FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_session_users_user_id
                    ON session_users(user_id, last_seen_at DESC);
                    """
                )
                self._migrate_legacy_embeddings(connection)
                self._reload_embedding_cache(connection)

    def resolve_user(
        self,
        embedding: list[float] | None,
        observed_at: str,
        gender: str | None,
        age_group: str | None,
        create_if_missing: bool = True,
    ) -> StoredUser | None:
        normalized_gender = self._normalize_gender(gender)
        normalized_age_group = self._normalize_age_group(age_group)

        with self._write_lock:
            with self._connect() as connection:
                matched_user_id = self._find_best_match(connection, embedding)

                if matched_user_id is None:
                    if not create_if_missing:
                        return None
                    cursor = connection.execute(
                        """
                        INSERT INTO users (
                            display_name,
                            created_at,
                            updated_at,
                            first_seen_at,
                            last_seen_at,
                            dominant_gender,
                            dominant_age_group,
                            embedding_json,
                            embedding_samples
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "",
                            observed_at,
                            observed_at,
                            observed_at,
                            observed_at,
                            normalized_gender or "unknown",
                            normalized_age_group or "unknown",
                            None,
                            0,
                        ),
                    )
                    user_id = int(cursor.lastrowid)
                    connection.execute(
                        "UPDATE users SET display_name = ? WHERE id = ?",
                        (f"Пользователь {user_id}", user_id),
                    )
                else:
                    row = connection.execute(
                        "SELECT * FROM users WHERE id = ?",
                        (matched_user_id,),
                    ).fetchone()
                    if row is None:
                        raise RuntimeError(f"User {matched_user_id} was not found in database")

                    connection.execute(
                        """
                        UPDATE users
                        SET updated_at = ?,
                            last_seen_at = ?,
                            dominant_gender = ?,
                            dominant_age_group = ?,
                            embedding_json = ?,
                            embedding_samples = ?
                        WHERE id = ?
                        """,
                        (
                            observed_at,
                            observed_at,
                            self._prefer_known_value(row["dominant_gender"], normalized_gender),
                            self._prefer_known_value(row["dominant_age_group"], normalized_age_group),
                            row["embedding_json"],
                            int(row["embedding_samples"] or 0),
                            matched_user_id,
                        ),
                    )
                    user_id = matched_user_id

                if embedding:
                    self._store_embedding_sample(
                        connection=connection,
                        user_id=user_id,
                        embedding=embedding,
                        observed_at=observed_at,
                    )
                self._refresh_user_embedding_metadata(
                    connection=connection,
                    user_id=user_id,
                    fallback_embedding=embedding,
                )
                self._reload_embedding_cache(connection)

                stored = connection.execute(
                    "SELECT * FROM users WHERE id = ?",
                    (user_id,),
                ).fetchone()
                if stored is None:
                    raise RuntimeError(f"User {user_id} could not be loaded after resolve")
                return self._row_to_user(stored)

    def save_session(self, session: SessionState, summary_path: str) -> None:
        finished_at = session.history[-1].timestamp if session.history else session.started_at

        with self._write_lock:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO sessions (
                        session_id,
                        started_at,
                        finished_at,
                        summary_path,
                        unique_people_count,
                        observations_count,
                        frames_processed,
                        fps
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        started_at = excluded.started_at,
                        finished_at = excluded.finished_at,
                        summary_path = excluded.summary_path,
                        unique_people_count = excluded.unique_people_count,
                        observations_count = excluded.observations_count,
                        frames_processed = excluded.frames_processed,
                        fps = excluded.fps
                    """,
                    (
                        session.session_id,
                        session.started_at,
                        finished_at,
                        summary_path,
                        len(session.people),
                        len(session.history),
                        session.frames_processed,
                        round(session.fps, 2),
                    ),
                )

                connection.execute(
                    "DELETE FROM session_users WHERE session_id = ?",
                    (session.session_id,),
                )

                for person in session.people.values():
                    if person.user_id is None:
                        continue

                    connection.execute(
                        """
                        INSERT INTO session_users (
                            session_id,
                            user_id,
                            session_person_id,
                            first_seen_at,
                            last_seen_at,
                            observations_count,
                            dominant_emotion,
                            dominant_gender,
                            dominant_age_group,
                            track_ids_json
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            session.session_id,
                            person.user_id,
                            person.person_id,
                            person.first_seen,
                            person.last_seen,
                            person.observations_count,
                            self._normalize_emotion(person.dominant_emotion()),
                            self._normalize_gender(person.dominant_gender()),
                            self._normalize_age_group(person.dominant_age_group()),
                            json.dumps(sorted(person.track_ids), ensure_ascii=False),
                        ),
                    )

                    stored_row = connection.execute(
                        "SELECT * FROM users WHERE id = ?",
                        (person.user_id,),
                    ).fetchone()
                    if stored_row is None:
                        continue

                    self._store_embedding_samples(
                        connection=connection,
                        user_id=person.user_id,
                        embeddings=person.embeddings,
                        observed_at=person.last_seen,
                    )
                    connection.execute(
                        """
                        UPDATE users
                        SET updated_at = ?,
                            last_seen_at = ?,
                            dominant_gender = ?,
                            dominant_age_group = ?,
                            last_emotion = ?,
                            total_sessions = (
                                SELECT COUNT(DISTINCT session_id)
                                FROM session_users
                                WHERE user_id = users.id
                            ),
                            total_observations = (
                                SELECT COALESCE(SUM(observations_count), 0)
                                FROM session_users
                                WHERE user_id = users.id
                            )
                        WHERE id = ?
                        """,
                        (
                            person.last_seen,
                            person.last_seen,
                            self._prefer_known_value(stored_row["dominant_gender"], self._normalize_gender(person.dominant_gender())),
                            self._prefer_known_value(stored_row["dominant_age_group"], self._normalize_age_group(person.dominant_age_group())),
                            self._normalize_emotion(person.dominant_emotion()),
                            person.user_id,
                        ),
                    )
                    self._refresh_user_embedding_metadata(
                        connection=connection,
                        user_id=person.user_id,
                        fallback_embedding=person.embedding,
                    )
                self._reload_embedding_cache(connection)

    def search_users(
        self,
        query: str = "",
        gender: str | None = None,
        age_group: str | None = None,
        limit: int | None = None,
    ) -> list[StoredUser]:
        filters: list[str] = []
        params: list[Any] = []

        text = query.strip()
        if text:
            pattern = f"%{text}%"
            filters.append("(display_name LIKE ? OR CAST(id AS TEXT) LIKE ?)")
            params.extend([pattern, pattern])

        normalized_gender = self._normalize_gender(gender) if gender else ""
        if normalized_gender:
            filters.append("dominant_gender = ?")
            params.append(normalized_gender)

        normalized_age_group = self._normalize_age_group(age_group) if age_group else ""
        if normalized_age_group:
            filters.append("dominant_age_group = ?")
            params.append(normalized_age_group)

        sql = "SELECT * FROM users"
        if filters:
            sql += " WHERE " + " AND ".join(filters)
        sql += " ORDER BY last_seen_at DESC, id DESC LIMIT ?"
        params.append(limit or self.search_limit)

        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._row_to_user(row) for row in rows]

    def get_user(self, user_id: int) -> StoredUser | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        return self._row_to_user(row) if row is not None else None

    def get_user_sessions(self, user_id: int, limit: int = 10) -> list[StoredUserSession]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    su.session_id,
                    s.started_at,
                    s.finished_at,
                    su.observations_count,
                    su.dominant_emotion,
                    su.dominant_gender,
                    su.dominant_age_group
                FROM session_users su
                INNER JOIN sessions s ON s.session_id = su.session_id
                WHERE su.user_id = ?
                ORDER BY s.finished_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()

        return [
            StoredUserSession(
                session_id=row["session_id"],
                started_at=row["started_at"],
                finished_at=row["finished_at"],
                observations_count=int(row["observations_count"] or 0),
                dominant_emotion=self._normalize_emotion(row["dominant_emotion"]),
                dominant_gender=self._normalize_gender(row["dominant_gender"]),
                dominant_age_group=self._normalize_age_group(row["dominant_age_group"]),
            )
            for row in rows
        ]

    def update_display_name(self, user_id: int, display_name: str) -> None:
        cleaned = display_name.strip()
        if not cleaned:
            raise ValueError("Display name cannot be empty")

        with self._write_lock:
            with self._connect() as connection:
                connection.execute(
                    """
                    UPDATE users
                    SET display_name = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (cleaned, datetime.now().isoformat(timespec="seconds"), user_id),
                )

    def delete_user(self, user_id: int) -> bool:
        with self._write_lock:
            with self._connect() as connection:
                deleted = connection.execute(
                    "DELETE FROM users WHERE id = ?",
                    (user_id,),
                ).rowcount
                if deleted:
                    connection.execute(
                        """
                        DELETE FROM sessions
                        WHERE session_id IN (
                            SELECT s.session_id
                            FROM sessions s
                            LEFT JOIN session_users su ON su.session_id = s.session_id
                            WHERE su.session_id IS NULL
                        )
                        """
                    )
                    self._rebalance_sequence(connection, "users")
                    self._reload_embedding_cache(connection)
                return deleted > 0

    @staticmethod
    def _serialize_embedding(embedding: list[float] | None) -> str | None:
        if not embedding:
            return None
        return json.dumps([float(value) for value in embedding], ensure_ascii=False)

    @staticmethod
    def _deserialize_embedding(raw: str | None) -> list[float] | None:
        if not raw:
            return None
        try:
            values = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(values, list):
            return None
        return [float(value) for value in values]

    def _migrate_legacy_embeddings(self, connection: sqlite3.Connection) -> None:
        rows = connection.execute(
            """
            SELECT id, embedding_json, first_seen_at
            FROM users
            WHERE embedding_json IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM user_embeddings ue
                  WHERE ue.user_id = users.id
              )
            """
        ).fetchall()
        for row in rows:
            connection.execute(
                """
                INSERT INTO user_embeddings (user_id, embedding_json, created_at)
                VALUES (?, ?, ?)
                """,
                (int(row["id"]), row["embedding_json"], str(row["first_seen_at"])),
            )

    def _reload_embedding_cache(self, connection: sqlite3.Connection) -> None:
        cache: dict[int, list[list[float]]] = {}
        rows = connection.execute(
            """
            SELECT user_id, embedding_json
            FROM user_embeddings
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()
        for row in rows:
            embedding = self._deserialize_embedding(row["embedding_json"])
            if not embedding:
                continue
            cache.setdefault(int(row["user_id"]), []).append(embedding)

        fallback_rows = connection.execute(
            """
            SELECT id, embedding_json
            FROM users
            WHERE embedding_json IS NOT NULL
            """
        ).fetchall()
        for row in fallback_rows:
            user_id = int(row["id"])
            if user_id in cache:
                continue
            embedding = self._deserialize_embedding(row["embedding_json"])
            if not embedding:
                continue
            cache[user_id] = [embedding]

        self._embedding_cache = cache

    def _store_embedding_samples(
        self,
        connection: sqlite3.Connection,
        user_id: int,
        embeddings: list[list[float]],
        observed_at: str,
    ) -> None:
        for embedding in embeddings:
            self._store_embedding_sample(connection, user_id, embedding, observed_at)

    def _store_embedding_sample(
        self,
        connection: sqlite3.Connection,
        user_id: int,
        embedding: list[float] | None,
        observed_at: str,
    ) -> None:
        probe = self._to_unit_vector(embedding)
        serialized = self._serialize_embedding(embedding)
        if probe is None or serialized is None:
            return

        rows = connection.execute(
            "SELECT id, embedding_json FROM user_embeddings WHERE user_id = ? ORDER BY created_at DESC, id DESC",
            (user_id,),
        ).fetchall()
        for row in rows:
            candidate = self._to_unit_vector(self._deserialize_embedding(row["embedding_json"]))
            if candidate is None:
                continue
            if self._cosine_similarity(probe, candidate) >= 0.995:
                return

        connection.execute(
            """
            INSERT INTO user_embeddings (user_id, embedding_json, created_at)
            VALUES (?, ?, ?)
            """,
            (user_id, serialized, observed_at),
        )

        extra_rows = connection.execute(
            """
            SELECT id
            FROM user_embeddings
            WHERE user_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT -1 OFFSET ?
            """,
            (user_id, self.max_embeddings_per_user),
        ).fetchall()
        if extra_rows:
            placeholders = ", ".join("?" for _ in extra_rows)
            connection.execute(
                f"DELETE FROM user_embeddings WHERE id IN ({placeholders})",
                [int(row["id"]) for row in extra_rows],
            )

    def _refresh_user_embedding_metadata(
        self,
        connection: sqlite3.Connection,
        user_id: int,
        fallback_embedding: list[float] | None = None,
    ) -> None:
        rows = connection.execute(
            """
            SELECT embedding_json
            FROM user_embeddings
            WHERE user_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (user_id,),
        ).fetchall()
        latest_embedding = rows[0]["embedding_json"] if rows else self._serialize_embedding(fallback_embedding)
        connection.execute(
            """
            UPDATE users
            SET embedding_json = ?, embedding_samples = ?
            WHERE id = ?
            """,
            (latest_embedding, len(rows), user_id),
        )

    @staticmethod
    def _rebalance_sequence(connection: sqlite3.Connection, table_name: str) -> None:
        max_row = connection.execute(
            f"SELECT MAX(id) AS max_id FROM {table_name}"
        ).fetchone()
        max_id = int(max_row["max_id"]) if max_row and max_row["max_id"] is not None else 0
        if max_id <= 0:
            connection.execute("DELETE FROM sqlite_sequence WHERE name = ?", (table_name,))
            return
        connection.execute(
            "UPDATE sqlite_sequence SET seq = ? WHERE name = ?",
            (max_id, table_name),
        )
        connection.execute(
            "INSERT INTO sqlite_sequence(name, seq) SELECT ?, ? WHERE NOT EXISTS (SELECT 1 FROM sqlite_sequence WHERE name = ?)",
            (table_name, max_id, table_name),
        )

    def _find_best_match(
        self,
        connection: sqlite3.Connection,
        embedding: list[float] | None,
    ) -> int | None:
        del connection
        probe = self._to_unit_vector(embedding)
        if probe is None:
            return None

        best_user_id: int | None = None
        best_similarity = -1.0

        for user_id, embeddings in self._embedding_cache.items():
            for sample in embeddings:
                candidate = self._to_unit_vector(sample)
                if candidate is None:
                    continue
                similarity = self._cosine_similarity(probe, candidate)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_user_id = int(user_id)

        if best_user_id is None or best_similarity < self.similarity_threshold:
            return None
        return best_user_id

    def _merge_embedding(
        self,
        stored_embedding: str | None,
        stored_samples: int,
        new_embedding: list[float] | None,
    ) -> tuple[str | None, int]:
        if not new_embedding:
            return stored_embedding, stored_samples

        current = self._deserialize_embedding(stored_embedding)
        if not current or stored_samples <= 0:
            return self._serialize_embedding(new_embedding), 1

        if len(current) != len(new_embedding):
            return self._serialize_embedding(new_embedding), 1

        merged = [
            ((float(old_value) * stored_samples) + float(new_value)) / (stored_samples + 1)
            for old_value, new_value in zip(current, new_embedding)
        ]
        return self._serialize_embedding(merged), stored_samples + 1

    @staticmethod
    def _to_unit_vector(values: list[float] | None) -> list[float] | None:
        if not values:
            return None
        norm = math.sqrt(sum(float(value) * float(value) for value in values))
        if norm == 0:
            return None
        return [float(value) / norm for value in values]

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        return float(sum(a * b for a, b in zip(left, right)))

    @staticmethod
    def _normalize_emotion(value: str | None) -> str:
        if not value:
            return "unknown"
        normalized = str(value).strip().lower()
        return normalized or "unknown"

    @staticmethod
    def _normalize_gender(value: str | None) -> str:
        if value is None:
            return ""
        normalized = str(value).strip().lower()
        if normalized in {"male", "man"}:
            return "male"
        if normalized in {"female", "woman"}:
            return "female"
        if normalized in {"unknown", ""}:
            return "unknown" if normalized == "unknown" else ""
        return "unknown"

    @staticmethod
    def _normalize_age_group(value: str | None) -> str:
        if value is None:
            return ""
        normalized = str(value).strip().lower()
        if normalized in KNOWN_AGE_GROUPS:
            return normalized
        if normalized in {"unknown", ""}:
            return "unknown" if normalized == "unknown" else ""
        return "unknown"

    @staticmethod
    def _prefer_known_value(existing: str | None, incoming: str | None) -> str:
        current = str(existing or "").strip().lower()
        candidate = str(incoming or "").strip().lower()
        if candidate and candidate != "unknown":
            return candidate
        if current:
            return current
        return "unknown"

    @staticmethod
    def _row_to_user(row: sqlite3.Row) -> StoredUser:
        return StoredUser(
            user_id=int(row["id"]),
            display_name=str(row["display_name"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            first_seen_at=str(row["first_seen_at"]),
            last_seen_at=str(row["last_seen_at"]),
            dominant_gender=UserDatabaseService._normalize_gender(row["dominant_gender"]) or "unknown",
            dominant_age_group=UserDatabaseService._normalize_age_group(row["dominant_age_group"]) or "unknown",
            total_sessions=int(row["total_sessions"] or 0),
            total_observations=int(row["total_observations"] or 0),
            last_emotion=UserDatabaseService._normalize_emotion(row["last_emotion"]),
            notes=str(row["notes"] or ""),
            embedding_samples=int(row["embedding_samples"] or 0),
        )
