"""SQLite data models for Foura Goalkeeper Coach."""

import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "goalkeepers.db")

STAT_FIELDS = (
    "crosses_attempted", "crosses_successful",
    "interventions_total", "interventions_good",
    "duels_total", "duels_won",
    "saves", "goals_conceded",
    "passes_attempted", "passes_completed",
    "commands_total", "commands_good",
    "aerial_total", "aerial_won",
    "sweeper_total", "sweeper_successful",
    "penalties_faced", "penalties_saved",
)

_STAT_COLUMNS = ",\n    ".join(
    f"{name} INTEGER NOT NULL DEFAULT 0" for name in STAT_FIELDS
)

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS clubs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_fr TEXT NOT NULL DEFAULT '',
    name_ar TEXT NOT NULL DEFAULT '',
    logo TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS goalkeepers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    birth_date TEXT,
    nationality TEXT,
    jersey_number INTEGER,
    photo TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goalkeeper_id INTEGER NOT NULL REFERENCES goalkeepers(id) ON DELETE CASCADE,
    match_date TEXT NOT NULL,
    opponent TEXT NOT NULL DEFAULT '',
    competition TEXT NOT NULL DEFAULT '',
    venue TEXT NOT NULL DEFAULT 'home',
    notes TEXT NOT NULL DEFAULT '',
    {_STAT_COLUMNS},
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL UNIQUE REFERENCES matches(id) ON DELETE CASCADE,
    overall_score REAL NOT NULL,
    rating_key TEXT NOT NULL,
    breakdown TEXT NOT NULL,
    created_at TEXT
);
"""


def _now():
    return datetime.now().isoformat(timespec="seconds")


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with closing(connect()) as conn, conn:
        conn.executescript(SCHEMA)
        if conn.execute("SELECT COUNT(*) AS c FROM clubs").fetchone()["c"] == 0:
            default_logo = os.path.join(BASE_DIR, "static", "img", "club_logo.png")
            logo = "img/club_logo.png" if os.path.exists(default_logo) else None
            conn.execute(
                "INSERT INTO clubs (name_fr, name_ar, logo, updated_at) VALUES (?, ?, ?, ?)",
                ("USMB", "الاتحاد الرياضي لمدينة البليدة", logo, _now()),
            )


class Club:
    @staticmethod
    def get():
        with closing(connect()) as conn:
            row = conn.execute("SELECT * FROM clubs ORDER BY id LIMIT 1").fetchone()
        return dict(row) if row else None

    @staticmethod
    def update(name_fr, name_ar, logo=None):
        with closing(connect()) as conn, conn:
            if logo is not None:
                conn.execute(
                    "UPDATE clubs SET name_fr=?, name_ar=?, logo=?, updated_at=?",
                    (name_fr, name_ar, logo, _now()),
                )
            else:
                conn.execute(
                    "UPDATE clubs SET name_fr=?, name_ar=?, updated_at=?",
                    (name_fr, name_ar, _now()),
                )


class Goalkeeper:
    @staticmethod
    def create(first_name, last_name, birth_date=None, nationality=None,
               jersey_number=None, photo=None):
        with closing(connect()) as conn, conn:
            cur = conn.execute(
                """INSERT INTO goalkeepers
                   (first_name, last_name, birth_date, nationality, jersey_number, photo, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (first_name, last_name, birth_date, nationality,
                 jersey_number, photo, _now()),
            )
            return cur.lastrowid

    @staticmethod
    def update(gid, first_name, last_name, birth_date=None, nationality=None,
               jersey_number=None, photo=None):
        with closing(connect()) as conn, conn:
            if photo is not None:
                conn.execute(
                    """UPDATE goalkeepers SET first_name=?, last_name=?, birth_date=?,
                       nationality=?, jersey_number=?, photo=? WHERE id=?""",
                    (first_name, last_name, birth_date, nationality,
                     jersey_number, photo, gid),
                )
            else:
                conn.execute(
                    """UPDATE goalkeepers SET first_name=?, last_name=?, birth_date=?,
                       nationality=?, jersey_number=? WHERE id=?""",
                    (first_name, last_name, birth_date, nationality,
                     jersey_number, gid),
                )

    @staticmethod
    def get(gid):
        with closing(connect()) as conn:
            row = conn.execute(
                """SELECT g.*,
                          COUNT(e.id) AS match_count,
                          AVG(e.overall_score) AS avg_score,
                          MAX(e.overall_score) AS best_score
                   FROM goalkeepers g
                   LEFT JOIN matches m ON m.goalkeeper_id = g.id
                   LEFT JOIN evaluations e ON e.match_id = m.id
                   WHERE g.id = ?
                   GROUP BY g.id""",
                (gid,),
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def all():
        with closing(connect()) as conn:
            rows = conn.execute(
                """SELECT g.*,
                          COUNT(e.id) AS match_count,
                          AVG(e.overall_score) AS avg_score,
                          MAX(e.overall_score) AS best_score
                   FROM goalkeepers g
                   LEFT JOIN matches m ON m.goalkeeper_id = g.id
                   LEFT JOIN evaluations e ON e.match_id = m.id
                   GROUP BY g.id
                   ORDER BY g.last_name COLLATE NOCASE, g.first_name COLLATE NOCASE"""
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def ranking():
        with closing(connect()) as conn:
            rows = conn.execute(
                """SELECT g.*,
                          COUNT(e.id) AS match_count,
                          AVG(e.overall_score) AS avg_score,
                          MAX(e.overall_score) AS best_score
                   FROM goalkeepers g
                   JOIN matches m ON m.goalkeeper_id = g.id
                   JOIN evaluations e ON e.match_id = m.id
                   GROUP BY g.id
                   ORDER BY avg_score DESC"""
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def delete(gid):
        with closing(connect()) as conn, conn:
            conn.execute("DELETE FROM goalkeepers WHERE id=?", (gid,))

    @staticmethod
    def count():
        with closing(connect()) as conn:
            return conn.execute("SELECT COUNT(*) AS c FROM goalkeepers").fetchone()["c"]


class Match:
    _INFO_COLUMNS = ("match_date", "opponent", "competition", "venue", "notes")

    @staticmethod
    def create(goalkeeper_id, info, stats):
        columns = ["goalkeeper_id", *Match._INFO_COLUMNS, *STAT_FIELDS, "created_at"]
        values = [
            goalkeeper_id,
            *(info.get(col, "") for col in Match._INFO_COLUMNS),
            *(int(stats.get(field) or 0) for field in STAT_FIELDS),
            _now(),
        ]
        placeholders = ", ".join("?" for _ in columns)
        with closing(connect()) as conn, conn:
            cur = conn.execute(
                f"INSERT INTO matches ({', '.join(columns)}) VALUES ({placeholders})",
                values,
            )
            return cur.lastrowid

    @staticmethod
    def update(mid, info, stats):
        assignments = ", ".join(f"{col}=?" for col in (*Match._INFO_COLUMNS, *STAT_FIELDS))
        values = [
            *(info.get(col, "") for col in Match._INFO_COLUMNS),
            *(int(stats.get(field) or 0) for field in STAT_FIELDS),
            mid,
        ]
        with closing(connect()) as conn, conn:
            conn.execute(f"UPDATE matches SET {assignments} WHERE id=?", values)

    @staticmethod
    def _select():
        return """SELECT m.*,
                         g.first_name, g.last_name,
                         g.jersey_number,
                         e.overall_score, e.rating_key
                  FROM matches m
                  JOIN goalkeepers g ON g.id = m.goalkeeper_id
                  LEFT JOIN evaluations e ON e.match_id = m.id"""

    @staticmethod
    def get(mid):
        with closing(connect()) as conn:
            row = conn.execute(
                Match._select() + " WHERE m.id = ?", (mid,)
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def all(goalkeeper_id=None):
        query = Match._select()
        params = ()
        if goalkeeper_id:
            query += " WHERE m.goalkeeper_id = ?"
            params = (goalkeeper_id,)
        query += " ORDER BY m.match_date DESC, m.id DESC"
        with closing(connect()) as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def recent(limit=5):
        with closing(connect()) as conn:
            rows = conn.execute(
                Match._select() + " ORDER BY m.match_date DESC, m.id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def delete(mid):
        with closing(connect()) as conn, conn:
            conn.execute("DELETE FROM matches WHERE id=?", (mid,))

    @staticmethod
    def count():
        with closing(connect()) as conn:
            return conn.execute("SELECT COUNT(*) AS c FROM matches").fetchone()["c"]


class Evaluation:
    @staticmethod
    def save(match_id, result):
        with closing(connect()) as conn, conn:
            conn.execute(
                """INSERT INTO evaluations (match_id, overall_score, rating_key, breakdown, created_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(match_id) DO UPDATE SET
                       overall_score=excluded.overall_score,
                       rating_key=excluded.rating_key,
                       breakdown=excluded.breakdown,
                       created_at=excluded.created_at""",
                (match_id, result["overall"], result["rating_key"],
                 json.dumps(result, ensure_ascii=False), _now()),
            )

    @staticmethod
    def get_by_match(match_id):
        with closing(connect()) as conn:
            row = conn.execute(
                "SELECT * FROM evaluations WHERE match_id=?", (match_id,)
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["breakdown"] = json.loads(data["breakdown"])
        return data

    @staticmethod
    def summary():
        with closing(connect()) as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS count, AVG(overall_score) AS average FROM evaluations"
            ).fetchone()
        return {"count": row["count"], "average": row["average"]}
