#!/usr/bin/env python3
"""SQLite persistence for Career Application Suite."""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable


BASELINE_WEIGHTS = {
    "role_match": 0.22,
    "skill_match": 0.20,
    "evidence_strength": 0.16,
    "domain_match": 0.12,
    "impact_match": 0.10,
    "job_freshness": 0.08,
    "source_quality": 0.06,
    "location_fit": 0.06,
}

SOURCE_PRIORITY = {
    "manual": 50,
    "company_site": 40,
    "boss": 30,
    "feishu": 20,
    "qqdocs": 20,
}

STAGE_SIGNALS = {
    "PREPARING": (0.0, False),
    "APPLIED": (0.0, False),
    "VIEWED": (0.5, True),
    "CONTACTED": (1.0, True),
    "WRITTEN_TEST": (2.0, True),
    "INTERVIEW_1": (3.0, True),
    "INTERVIEW_2": (3.5, True),
    "FINAL_INTERVIEW": (4.0, True),
    "OFFER": (5.0, True),
    "REJECTED_SCREEN": (-1.0, True),
    "REJECTED_AFTER_INTERVIEW": (0.0, False),
    "NO_RESPONSE": (-0.5, True),
    "WITHDRAWN": (0.0, False),
    "JOB_CLOSED": (0.0, False),
}

NO_RESPONSE_WAIT_DAYS = 21


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[\s·•_/\\|—–-]+", "", text)
    text = re.sub(r"[（）()【】\[\]《》<>，,。.！!？?:：;；'\"“”‘’]", "", text)
    return text


def canonical_key(item: dict[str, Any]) -> str:
    kind = item["kind"]
    company = normalize_text(item.get("company"))
    if kind == "CAMPAIGN":
        discriminator = normalize_text(
            item.get("recruitment_type")
            or item.get("title")
            or item.get("application_start")
        )
    else:
        discriminator = "|".join(
            [
                normalize_text(item.get("title")),
                normalize_text(item.get("location")),
            ]
        )
    return f"{kind}|{company}|{discriminator}"


def normalize_opportunity(source: str, raw: dict[str, Any]) -> dict[str, Any]:
    aliases = {
        "company": ["company", "companyName", "公司", "企业"],
        "title": ["title", "jobName", "position", "岗位", "职位", "公告名称"],
        "location": ["location", "city", "workLocation", "工作地点", "地点"],
        "recruitment_type": [
            "recruitment_type",
            "recruitmentType",
            "招聘类型",
            "招聘批次",
        ],
        "application_start": [
            "application_start",
            "startDate",
            "开始时间",
            "网申开始",
        ],
        "application_deadline": [
            "application_deadline",
            "deadline",
            "截止时间",
            "网申截止",
        ],
        "url": ["url", "jobUrl", "applyUrl", "link", "投递链接", "网申地址"],
        "external_id": ["external_id", "securityId", "id", "jobId"],
        "kind": ["kind", "type", "record_type"],
        "description": ["description", "jobDescription", "jd", "岗位描述"],
    }

    def pick(name: str) -> Any:
        for key in aliases[name]:
            if key in raw and raw[key] not in (None, ""):
                return raw[key]
        return None

    raw_kind = str(pick("kind") or "").upper()
    kind = "CAMPAIGN" if raw_kind in {"CAMPAIGN", "COMPANY", "BATCH"} else "JOB"
    if source in {"feishu", "qqdocs"} and raw_kind not in {"JOB", "POSITION"}:
        kind = "CAMPAIGN"
    item = {
        "kind": kind,
        "company": str(pick("company") or "").strip(),
        "title": str(pick("title") or "").strip(),
        "location": str(pick("location") or "").strip(),
        "recruitment_type": str(pick("recruitment_type") or "").strip(),
        "application_start": str(pick("application_start") or "").strip(),
        "application_deadline": str(pick("application_deadline") or "").strip(),
        "url": str(pick("url") or "").strip(),
        "description": str(pick("description") or "").strip(),
        "features": raw.get("features") or {},
        "hard_eligible": raw.get("hard_eligible"),
    }
    if not item["company"]:
        raise ValueError("Opportunity is missing company")
    if kind == "JOB" and not item["title"]:
        raise ValueError("JOB opportunity is missing title")
    if kind == "CAMPAIGN" and not item["title"]:
        item["title"] = item["recruitment_type"] or "招聘批次"
    external_id = pick("external_id") or item["url"]
    item["external_id"] = str(external_id or stable_hash(json.dumps(raw, sort_keys=True))[:20])
    item["canonical_key"] = canonical_key(item)
    return item


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS base_revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_revision_id INTEGER REFERENCES base_revisions(id),
    summary TEXT NOT NULL,
    content_markdown TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    record_kind TEXT NOT NULL,
    source_url TEXT,
    raw_json TEXT NOT NULL,
    checksum TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    UNIQUE(source, external_id, checksum)
);

CREATE TABLE IF NOT EXISTS opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL CHECK(kind IN ('JOB', 'CAMPAIGN')),
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    location TEXT,
    recruitment_type TEXT,
    application_start TEXT,
    application_deadline TEXT,
    url TEXT,
    description TEXT,
    canonical_key TEXT NOT NULL UNIQUE,
    primary_source TEXT NOT NULL,
    source_priority INTEGER NOT NULL,
    features_json TEXT NOT NULL DEFAULT '{}',
    hard_eligible INTEGER,
    possible_duplicate_of INTEGER REFERENCES opportunities(id),
    status TEXT NOT NULL DEFAULT 'OPEN',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS opportunity_sources (
    opportunity_id INTEGER NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    source_record_id INTEGER NOT NULL REFERENCES source_records(id) ON DELETE CASCADE,
    PRIMARY KEY(opportunity_id, source_record_id)
);

CREATE TABLE IF NOT EXISTS opportunity_relations (
    parent_id INTEGER NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    child_id INTEGER NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL,
    PRIMARY KEY(parent_id, child_id, relation_type)
);

CREATE TABLE IF NOT EXISTS job_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER NOT NULL REFERENCES opportunities(id),
    base_revision_id INTEGER NOT NULL REFERENCES base_revisions(id),
    overlay_markdown TEXT NOT NULL DEFAULT '',
    match_plan_markdown TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'ANALYZING',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS resume_artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_session_id INTEGER NOT NULL REFERENCES job_sessions(id),
    format TEXT NOT NULL,
    path TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER NOT NULL REFERENCES opportunities(id),
    job_session_id INTEGER REFERENCES job_sessions(id),
    resume_artifact_id INTEGER REFERENCES resume_artifacts(id),
    status TEXT NOT NULL,
    applied_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS application_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    signal REAL NOT NULL,
    counts_for_learning INTEGER NOT NULL,
    note TEXT,
    occurred_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scoring_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version INTEGER NOT NULL UNIQUE,
    weights_json TEXT NOT NULL,
    parent_id INTEGER REFERENCES scoring_profiles(id),
    reason TEXT NOT NULL,
    sample_count INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS weight_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scoring_profile_id INTEGER NOT NULL REFERENCES scoring_profiles(id) ON DELETE CASCADE,
    feature TEXT NOT NULL,
    old_weight REAL NOT NULL,
    new_weight REAL NOT NULL,
    delta REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS notion_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notion_sync_state (
    entity_type TEXT NOT NULL,
    local_id INTEGER NOT NULL,
    notion_page_id TEXT,
    notion_page_url TEXT,
    content_hash TEXT,
    last_synced_at TEXT,
    sync_status TEXT NOT NULL DEFAULT 'PENDING',
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    PRIMARY KEY(entity_type, local_id)
);

CREATE TABLE IF NOT EXISTS notion_sync_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    local_id INTEGER NOT NULL,
    action TEXT NOT NULL DEFAULT 'UPSERT',
    payload_json TEXT,
    content_hash TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(entity_type, local_id)
);

CREATE INDEX IF NOT EXISTS idx_notion_sync_queue_status
ON notion_sync_queue(status, updated_at);
"""


class CareerStore:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            row = conn.execute("SELECT id FROM scoring_profiles LIMIT 1").fetchone()
            if row is None:
                cursor = conn.execute(
                    """
                    INSERT INTO scoring_profiles
                    (version, weights_json, reason, sample_count, active, created_at)
                    VALUES (1, ?, ?, 0, 1, ?)
                    """,
                    (json.dumps(BASELINE_WEIGHTS, sort_keys=True), "baseline", utc_now()),
                )
                self._queue_sync_conn(
                    conn, "scoring_profile", int(cursor.lastrowid)
                )

    @staticmethod
    def _queue_sync_conn(
        conn: sqlite3.Connection, entity_type: str, local_id: int
    ) -> None:
        if entity_type not in {
            "opportunity",
            "application",
            "application_event",
            "scoring_profile",
        }:
            raise ValueError(f"Unsupported Notion entity type: {entity_type}")
        now = utc_now()
        conn.execute(
            """
            INSERT INTO notion_sync_queue
            (entity_type, local_id, action, status, created_at, updated_at)
            VALUES (?, ?, 'UPSERT', 'PENDING', ?, ?)
            ON CONFLICT(entity_type, local_id) DO UPDATE SET
                action = 'UPSERT',
                payload_json = NULL,
                content_hash = NULL,
                status = 'PENDING',
                last_error = NULL,
                updated_at = excluded.updated_at
            """,
            (entity_type, local_id, now, now),
        )
        conn.execute(
            """
            INSERT INTO notion_sync_state
            (entity_type, local_id, sync_status)
            VALUES (?, ?, 'PENDING')
            ON CONFLICT(entity_type, local_id) DO UPDATE SET
                sync_status = 'PENDING',
                last_error = NULL
            """,
            (entity_type, local_id),
        )

    @classmethod
    def _queue_all_scored_entities_conn(cls, conn: sqlite3.Connection) -> None:
        for row in conn.execute("SELECT id FROM opportunities").fetchall():
            cls._queue_sync_conn(conn, "opportunity", int(row["id"]))
        for row in conn.execute("SELECT id FROM applications").fetchall():
            cls._queue_sync_conn(conn, "application", int(row["id"]))

    def add_base_revision(self, content: str, summary: str) -> int:
        self.initialize()
        with self.connect() as conn:
            parent = conn.execute(
                "SELECT id FROM base_revisions ORDER BY id DESC LIMIT 1"
            ).fetchone()
            cursor = conn.execute(
                """
                INSERT INTO base_revisions
                (parent_revision_id, summary, content_markdown, content_hash, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    parent["id"] if parent else None,
                    summary,
                    content,
                    stable_hash(content),
                    utc_now(),
                ),
            )
            return int(cursor.lastrowid)

    def base_revision(self, revision_id: int | None = None) -> sqlite3.Row | None:
        self.initialize()
        with self.connect() as conn:
            if revision_id is None:
                return conn.execute(
                    "SELECT * FROM base_revisions ORDER BY id DESC LIMIT 1"
                ).fetchone()
            return conn.execute(
                "SELECT * FROM base_revisions WHERE id = ?", (revision_id,)
            ).fetchone()

    def base_history(self) -> list[sqlite3.Row]:
        self.initialize()
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT id, parent_revision_id, summary, content_hash, created_at
                FROM base_revisions ORDER BY id DESC
                """
            ).fetchall()

    def import_opportunities(
        self, source: str, records: Iterable[dict[str, Any]]
    ) -> dict[str, int]:
        self.initialize()
        source = source.lower()
        stats = {"imported": 0, "merged": 0, "possible_duplicates": 0}
        with self.connect() as conn:
            for raw in records:
                item = normalize_opportunity(source, raw)
                raw_json = json.dumps(raw, ensure_ascii=False, sort_keys=True)
                checksum = stable_hash(raw_json)
                try:
                    source_cursor = conn.execute(
                        """
                        INSERT INTO source_records
                        (source, external_id, record_kind, source_url, raw_json, checksum, fetched_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            source,
                            item["external_id"],
                            item["kind"],
                            item["url"],
                            raw_json,
                            checksum,
                            utc_now(),
                        ),
                    )
                    source_record_id = int(source_cursor.lastrowid)
                except sqlite3.IntegrityError:
                    existing_source = conn.execute(
                        """
                        SELECT id FROM source_records
                        WHERE source = ? AND external_id = ? AND checksum = ?
                        """,
                        (source, item["external_id"], checksum),
                    ).fetchone()
                    source_record_id = int(existing_source["id"])

                existing = conn.execute(
                    "SELECT * FROM opportunities WHERE canonical_key = ?",
                    (item["canonical_key"],),
                ).fetchone()
                priority = SOURCE_PRIORITY.get(source, 10)
                if existing:
                    opportunity_id = int(existing["id"])
                    updates: dict[str, Any] = {"updated_at": utc_now()}
                    if priority >= int(existing["source_priority"]):
                        for field in (
                            "company",
                            "title",
                            "location",
                            "recruitment_type",
                            "application_start",
                            "application_deadline",
                            "url",
                            "description",
                        ):
                            if item.get(field):
                                updates[field] = item[field]
                        updates["primary_source"] = source
                        updates["source_priority"] = priority
                    if item.get("features"):
                        current_features = json.loads(existing["features_json"] or "{}")
                        current_features.update(item["features"])
                        updates["features_json"] = json.dumps(
                            current_features, ensure_ascii=False, sort_keys=True
                        )
                    if item.get("hard_eligible") is not None:
                        updates["hard_eligible"] = int(bool(item["hard_eligible"]))
                    assignments = ", ".join(f"{key} = ?" for key in updates)
                    conn.execute(
                        f"UPDATE opportunities SET {assignments} WHERE id = ?",
                        (*updates.values(), opportunity_id),
                    )
                    stats["merged"] += 1
                else:
                    possible_duplicate_of = self._find_possible_duplicate(conn, item)
                    cursor = conn.execute(
                        """
                        INSERT INTO opportunities (
                            kind, company, title, location, recruitment_type,
                            application_start, application_deadline, url, description,
                            canonical_key, primary_source, source_priority, features_json,
                            hard_eligible, possible_duplicate_of, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            item["kind"],
                            item["company"],
                            item["title"],
                            item["location"],
                            item["recruitment_type"],
                            item["application_start"],
                            item["application_deadline"],
                            item["url"],
                            item["description"],
                            item["canonical_key"],
                            source,
                            priority,
                            json.dumps(item["features"], ensure_ascii=False, sort_keys=True),
                            None
                            if item["hard_eligible"] is None
                            else int(bool(item["hard_eligible"])),
                            possible_duplicate_of,
                            utc_now(),
                            utc_now(),
                        ),
                    )
                    opportunity_id = int(cursor.lastrowid)
                    stats["imported"] += 1
                    if possible_duplicate_of:
                        stats["possible_duplicates"] += 1

                conn.execute(
                    """
                    INSERT OR IGNORE INTO opportunity_sources
                    (opportunity_id, source_record_id) VALUES (?, ?)
                    """,
                    (opportunity_id, source_record_id),
                )
                self._queue_sync_conn(conn, "opportunity", opportunity_id)
        return stats

    @staticmethod
    def _find_possible_duplicate(
        conn: sqlite3.Connection, item: dict[str, Any]
    ) -> int | None:
        rows = conn.execute(
            "SELECT id, company, title, location FROM opportunities WHERE kind = ?",
            (item["kind"],),
        ).fetchall()
        for row in rows:
            if normalize_text(row["company"]) != normalize_text(item["company"]):
                continue
            title_similarity = SequenceMatcher(
                None, normalize_text(row["title"]), normalize_text(item["title"])
            ).ratio()
            location_similarity = SequenceMatcher(
                None,
                normalize_text(row["location"]),
                normalize_text(item["location"]),
            ).ratio()
            if title_similarity >= 0.86 and location_similarity >= 0.65:
                return int(row["id"])
        return None

    def list_opportunities(self, kind: str | None = None) -> list[dict[str, Any]]:
        self.initialize()
        query = """
            SELECT o.*,
                   GROUP_CONCAT(DISTINCT sr.source) AS sources
            FROM opportunities o
            LEFT JOIN opportunity_sources os ON os.opportunity_id = o.id
            LEFT JOIN source_records sr ON sr.id = os.source_record_id
        """
        params: tuple[Any, ...] = ()
        if kind:
            query += " WHERE o.kind = ?"
            params = (kind.upper(),)
        query += " GROUP BY o.id ORDER BY o.updated_at DESC, o.id DESC"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            active = self._active_profile_conn(conn)
            weights = json.loads(active["weights_json"])
            return [self._row_with_score(row, weights) for row in rows]

    def update_opportunity_features(
        self,
        opportunity_id: int,
        features: dict[str, Any],
        hard_eligible: bool | None = None,
    ) -> None:
        self.initialize()
        invalid = sorted(set(features) - set(BASELINE_WEIGHTS))
        if invalid:
            raise ValueError(f"Unknown scoring features: {', '.join(invalid)}")
        normalized = {}
        for name, value in features.items():
            numeric = float(value)
            if not 0.0 <= numeric <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
            normalized[name] = numeric
        with self.connect() as conn:
            row = conn.execute(
                "SELECT features_json FROM opportunities WHERE id = ?",
                (opportunity_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Unknown opportunity: {opportunity_id}")
            current = json.loads(row["features_json"] or "{}")
            current.update(normalized)
            cursor = conn.execute(
                """
                UPDATE opportunities
                SET features_json = ?, hard_eligible = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    json.dumps(current, sort_keys=True),
                    None if hard_eligible is None else int(hard_eligible),
                    utc_now(),
                    opportunity_id,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"Unknown opportunity: {opportunity_id}")
            self._queue_sync_conn(conn, "opportunity", opportunity_id)

    def relate_opportunities(
        self, campaign_id: int, job_id: int, relation_type: str = "CONTAINS"
    ) -> None:
        self.initialize()
        with self.connect() as conn:
            parent = conn.execute(
                "SELECT kind FROM opportunities WHERE id = ?", (campaign_id,)
            ).fetchone()
            child = conn.execute(
                "SELECT kind FROM opportunities WHERE id = ?", (job_id,)
            ).fetchone()
            if parent is None or child is None:
                raise ValueError("Unknown campaign or job opportunity")
            if parent["kind"] != "CAMPAIGN" or child["kind"] != "JOB":
                raise ValueError("Parent must be CAMPAIGN and child must be JOB")
            conn.execute(
                """
                INSERT OR IGNORE INTO opportunity_relations
                (parent_id, child_id, relation_type) VALUES (?, ?, ?)
                """,
                (campaign_id, job_id, relation_type),
            )
            self._queue_sync_conn(conn, "opportunity", job_id)

    @staticmethod
    def _row_with_score(
        row: sqlite3.Row, weights: dict[str, float]
    ) -> dict[str, Any]:
        result = dict(row)
        features = json.loads(result.pop("features_json") or "{}")
        result["features"] = features
        result["score"] = round(
            100
            * sum(
                weights.get(name, 0.0)
                * max(0.0, min(1.0, float(features.get(name, 0.5))))
                for name in weights
            ),
            1,
        )
        return result

    def create_session(self, opportunity_id: int) -> int:
        self.initialize()
        base = self.base_revision()
        if base is None:
            raise ValueError("No Base Career Vault revision exists")
        with self.connect() as conn:
            if conn.execute(
                "SELECT id FROM opportunities WHERE id = ?", (opportunity_id,)
            ).fetchone() is None:
                raise ValueError(f"Unknown opportunity: {opportunity_id}")
            cursor = conn.execute(
                """
                INSERT INTO job_sessions
                (opportunity_id, base_revision_id, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (opportunity_id, int(base["id"]), utc_now(), utc_now()),
            )
            return int(cursor.lastrowid)

    def update_session_file(self, session_id: int, field: str, content: str) -> None:
        if field not in {"overlay_markdown", "match_plan_markdown"}:
            raise ValueError("Unsupported session field")
        self.initialize()
        with self.connect() as conn:
            cursor = conn.execute(
                f"UPDATE job_sessions SET {field} = ?, updated_at = ? WHERE id = ?",
                (content, utc_now(), session_id),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"Unknown session: {session_id}")

    def add_resume(self, session_id: int, fmt: str, path: str | Path) -> int:
        resume_path = Path(path).expanduser().resolve()
        content = resume_path.read_bytes()
        self.initialize()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO resume_artifacts
                (job_session_id, format, path, content_hash, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    fmt.lower(),
                    str(resume_path),
                    hashlib.sha256(content).hexdigest(),
                    utc_now(),
                ),
            )
            return int(cursor.lastrowid)

    def create_application(
        self,
        opportunity_id: int,
        session_id: int | None,
        resume_artifact_id: int | None,
    ) -> int:
        self.initialize()
        now = utc_now()
        with self.connect() as conn:
            if conn.execute(
                "SELECT id FROM opportunities WHERE id = ?", (opportunity_id,)
            ).fetchone() is None:
                raise ValueError(f"Unknown opportunity: {opportunity_id}")
            if session_id is not None:
                session = conn.execute(
                    "SELECT opportunity_id FROM job_sessions WHERE id = ?",
                    (session_id,),
                ).fetchone()
                if session is None:
                    raise ValueError(f"Unknown session: {session_id}")
                if int(session["opportunity_id"]) != opportunity_id:
                    raise ValueError("Session belongs to a different opportunity")
            if resume_artifact_id is not None:
                resume = conn.execute(
                    """
                    SELECT ra.job_session_id, js.opportunity_id
                    FROM resume_artifacts ra
                    JOIN job_sessions js ON js.id = ra.job_session_id
                    WHERE ra.id = ?
                    """,
                    (resume_artifact_id,),
                ).fetchone()
                if resume is None:
                    raise ValueError(f"Unknown resume artifact: {resume_artifact_id}")
                if int(resume["opportunity_id"]) != opportunity_id:
                    raise ValueError("Resume belongs to a different opportunity")
                if session_id is not None and int(resume["job_session_id"]) != session_id:
                    raise ValueError("Resume belongs to a different Job Session")
            cursor = conn.execute(
                """
                INSERT INTO applications
                (opportunity_id, job_session_id, resume_artifact_id, status, applied_at, updated_at)
                VALUES (?, ?, ?, 'APPLIED', ?, ?)
                """,
                (opportunity_id, session_id, resume_artifact_id, now, now),
            )
            application_id = int(cursor.lastrowid)
            event_cursor = conn.execute(
                """
                INSERT INTO application_events
                (application_id, stage, signal, counts_for_learning, note, occurred_at)
                VALUES (?, 'APPLIED', 0, 0, ?, ?)
                """,
                (application_id, "Application recorded", now),
            )
            self._queue_sync_conn(conn, "application", application_id)
            self._queue_sync_conn(
                conn, "application_event", int(event_cursor.lastrowid)
            )
            return application_id

    def record_event(
        self,
        application_id: int,
        stage: str,
        note: str = "",
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        self.initialize()
        stage = stage.upper()
        if stage not in STAGE_SIGNALS:
            raise ValueError(
                f"Unsupported stage {stage}. Allowed: {', '.join(STAGE_SIGNALS)}"
            )
        signal, counts = STAGE_SIGNALS[stage]
        event_time = occurred_at or utc_now()
        with self.connect() as conn:
            application = conn.execute(
                "SELECT applied_at FROM applications WHERE id = ?",
                (application_id,),
            ).fetchone()
            if application is None:
                raise ValueError(f"Unknown application: {application_id}")
            if stage == "NO_RESPONSE":
                applied_at = datetime.fromisoformat(application["applied_at"])
                observed_at = datetime.fromisoformat(event_time)
                if (observed_at - applied_at).days < NO_RESPONSE_WAIT_DAYS:
                    raise ValueError(
                        f"NO_RESPONSE requires at least {NO_RESPONSE_WAIT_DAYS} days"
                    )
            cursor = conn.execute(
                """
                INSERT INTO application_events
                (application_id, stage, signal, counts_for_learning, note, occurred_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    application_id,
                    stage,
                    signal,
                    int(counts),
                    note,
                    event_time,
                ),
            )
            if cursor.lastrowid is None:
                raise ValueError(f"Unknown application: {application_id}")
            event_id = int(cursor.lastrowid)
            updated = conn.execute(
                "UPDATE applications SET status = ?, updated_at = ? WHERE id = ?",
                (stage, utc_now(), application_id),
            )
            if updated.rowcount != 1:
                raise ValueError(f"Unknown application: {application_id}")
            self._queue_sync_conn(conn, "application_event", event_id)
            self._queue_sync_conn(conn, "application", application_id)
        learning = self.recompute_weights(reason=f"application {application_id}: {stage}")
        return {"event_stage": stage, "signal": signal, "learning": learning}

    def applications(self) -> list[dict[str, Any]]:
        self.initialize()
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT a.*, o.company, o.title, o.location, o.kind,
                       ra.path AS resume_path, js.base_revision_id
                FROM applications a
                JOIN opportunities o ON o.id = a.opportunity_id
                LEFT JOIN job_sessions js ON js.id = a.job_session_id
                LEFT JOIN resume_artifacts ra ON ra.id = a.resume_artifact_id
                ORDER BY a.updated_at DESC, a.id DESC
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def application_events(self, application_id: int) -> list[dict[str, Any]]:
        self.initialize()
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM application_events
                WHERE application_id = ?
                ORDER BY occurred_at, id
                """,
                (application_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def _active_profile_conn(self, conn: sqlite3.Connection) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM scoring_profiles WHERE active = 1 ORDER BY version DESC LIMIT 1"
        ).fetchone()
        if row is None:
            raise RuntimeError("No active scoring profile")
        return row

    def active_profile(self) -> dict[str, Any]:
        self.initialize()
        with self.connect() as conn:
            row = self._active_profile_conn(conn)
            result = dict(row)
            result["weights"] = json.loads(result.pop("weights_json"))
            result["changes"] = [
                dict(change)
                for change in conn.execute(
                    "SELECT * FROM weight_changes WHERE scoring_profile_id = ?",
                    (row["id"],),
                ).fetchall()
            ]
            return result

    def profile_history(self) -> list[dict[str, Any]]:
        self.initialize()
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM scoring_profiles ORDER BY version DESC"
            ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["weights"] = json.loads(item.pop("weights_json"))
                result.append(item)
            return result

    def activate_profile(self, version: int) -> None:
        self.initialize()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT id FROM scoring_profiles WHERE version = ?", (version,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Unknown scoring profile version: {version}")
            conn.execute("UPDATE scoring_profiles SET active = 0")
            conn.execute(
                "UPDATE scoring_profiles SET active = 1 WHERE version = ?", (version,)
            )
            for profile in conn.execute("SELECT id FROM scoring_profiles").fetchall():
                self._queue_sync_conn(
                    conn, "scoring_profile", int(profile["id"])
                )
            self._queue_all_scored_entities_conn(conn)

    def recompute_weights(
        self, reason: str, minimum_samples: int = 3
    ) -> dict[str, Any]:
        self.initialize()
        with self.connect() as conn:
            samples = conn.execute(
                """
                WITH ranked AS (
                    SELECT id AS event_id, application_id,
                           ROW_NUMBER() OVER (
                               PARTITION BY application_id
                               ORDER BY occurred_at DESC, id DESC
                           ) AS rank
                    FROM application_events
                    WHERE counts_for_learning = 1
                )
                SELECT ae.signal, o.features_json
                FROM ranked
                JOIN application_events ae ON ae.id = ranked.event_id
                JOIN applications a ON a.id = ae.application_id
                JOIN opportunities o ON o.id = a.opportunity_id
                WHERE ranked.rank = 1
                  AND (o.hard_eligible IS NULL OR o.hard_eligible = 1)
                """
            ).fetchall()
            if len(samples) < minimum_samples:
                return {
                    "updated": False,
                    "sample_count": len(samples),
                    "minimum_samples": minimum_samples,
                    "reason": "insufficient_samples",
                }

            active = self._active_profile_conn(conn)
            old_weights = json.loads(active["weights_json"])
            prior_strength = 4.0
            qualities: dict[str, float] = {}
            all_targets: list[float] = []
            parsed_samples: list[tuple[float, dict[str, Any]]] = []
            for sample in samples:
                target = max(0.0, min(1.0, (float(sample["signal"]) + 1.0) / 6.0))
                all_targets.append(target)
                parsed_samples.append(
                    (target, json.loads(sample["features_json"] or "{}"))
                )
            overall = (
                prior_strength * 0.5 + sum(all_targets)
            ) / (prior_strength + len(all_targets))

            for feature in old_weights:
                weighted_target = prior_strength * 0.5
                exposure = prior_strength
                for target, features in parsed_samples:
                    value = max(
                        0.0, min(1.0, float(features.get(feature, 0.5)))
                    )
                    weighted_target += value * target
                    exposure += value
                qualities[feature] = weighted_target / exposure

            raw = {
                feature: old_weights[feature]
                * math.exp(1.2 * (qualities[feature] - overall))
                for feature in old_weights
            }
            raw_total = sum(raw.values())
            normalized = {feature: value / raw_total for feature, value in raw.items()}

            max_relative_change = 0.10
            bounded = {}
            for feature, old in old_weights.items():
                low = old * (1.0 - max_relative_change)
                high = old * (1.0 + max_relative_change)
                bounded[feature] = min(high, max(low, normalized[feature]))
            bounded_total = sum(bounded.values())
            new_weights = {
                feature: value / bounded_total for feature, value in bounded.items()
            }

            if all(abs(new_weights[k] - old_weights[k]) < 1e-9 for k in old_weights):
                return {
                    "updated": False,
                    "sample_count": len(samples),
                    "reason": "no_change",
                }

            next_version = int(
                conn.execute(
                    "SELECT COALESCE(MAX(version), 0) + 1 AS version FROM scoring_profiles"
                ).fetchone()["version"]
            )
            conn.execute("UPDATE scoring_profiles SET active = 0")
            cursor = conn.execute(
                """
                INSERT INTO scoring_profiles
                (version, weights_json, parent_id, reason, sample_count, active, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    next_version,
                    json.dumps(new_weights, sort_keys=True),
                    int(active["id"]),
                    reason,
                    len(samples),
                    utc_now(),
                ),
            )
            profile_id = int(cursor.lastrowid)
            for feature, old in old_weights.items():
                new = new_weights[feature]
                conn.execute(
                    """
                    INSERT INTO weight_changes
                    (scoring_profile_id, feature, old_weight, new_weight, delta)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (profile_id, feature, old, new, new - old),
                )
            self._queue_sync_conn(conn, "scoring_profile", int(active["id"]))
            self._queue_sync_conn(conn, "scoring_profile", profile_id)
            self._queue_all_scored_entities_conn(conn)
            return {
                "updated": True,
                "version": next_version,
                "sample_count": len(samples),
                "weights": new_weights,
            }

    def configure_notion(self, config: dict[str, Any]) -> dict[str, Any]:
        self.initialize()
        data_sources = config.get("data_sources")
        if not isinstance(data_sources, dict):
            raise ValueError("Notion config requires data_sources")
        required = {
            "opportunity",
            "application",
            "application_event",
            "scoring_profile",
        }
        missing = sorted(required - set(data_sources))
        if missing:
            raise ValueError(
                f"Notion config missing data sources: {', '.join(missing)}"
            )
        values = {
            "page_url": str(config.get("page_url") or ""),
            "page_id": str(config.get("page_id") or ""),
            **{
                f"data_source.{name}": str(data_sources[name]).removeprefix(
                    "collection://"
                )
                for name in required
            },
        }
        now = utc_now()
        with self.connect() as conn:
            for key, value in values.items():
                conn.execute(
                    """
                    INSERT INTO notion_config(key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = excluded.updated_at
                    """,
                    (key, value, now),
                )
        return self.notion_configuration()

    def notion_configuration(self) -> dict[str, Any]:
        self.initialize()
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT key, value FROM notion_config ORDER BY key"
            ).fetchall()
        flat = {row["key"]: row["value"] for row in rows}
        return {
            "page_url": flat.get("page_url", ""),
            "page_id": flat.get("page_id", ""),
            "data_sources": {
                key.removeprefix("data_source."): value
                for key, value in flat.items()
                if key.startswith("data_source.")
            },
        }

    def enqueue_all_notion(self) -> dict[str, int]:
        self.initialize()
        tables = {
            "opportunity": "opportunities",
            "application": "applications",
            "application_event": "application_events",
            "scoring_profile": "scoring_profiles",
        }
        counts: dict[str, int] = {}
        with self.connect() as conn:
            for entity_type, table in tables.items():
                rows = conn.execute(f"SELECT id FROM {table}").fetchall()
                for row in rows:
                    self._queue_sync_conn(conn, entity_type, int(row["id"]))
                counts[entity_type] = len(rows)
        return counts

    def pending_notion_queue(self) -> list[dict[str, Any]]:
        self.initialize()
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT q.*, s.notion_page_id, s.notion_page_url,
                       s.content_hash AS synced_content_hash
                FROM notion_sync_queue q
                LEFT JOIN notion_sync_state s
                  ON s.entity_type = q.entity_type AND s.local_id = q.local_id
                WHERE q.status = 'PENDING'
                ORDER BY
                    CASE q.entity_type
                        WHEN 'opportunity' THEN 1
                        WHEN 'application' THEN 2
                        WHEN 'application_event' THEN 3
                        WHEN 'scoring_profile' THEN 4
                        ELSE 9
                    END,
                    q.id
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def set_notion_queue_payload(
        self, queue_id: int, payload: dict[str, Any], content_hash: str
    ) -> None:
        self.initialize()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE notion_sync_queue
                SET payload_json = ?, content_hash = ?, updated_at = ?
                WHERE id = ? AND status = 'PENDING'
                """,
                (
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    content_hash,
                    utc_now(),
                    queue_id,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"Unknown pending Notion queue item: {queue_id}")

    def notion_sync_ack(
        self,
        queue_id: int,
        notion_page_id: str,
        notion_page_url: str = "",
    ) -> dict[str, Any]:
        self.initialize()
        now = utc_now()
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT entity_type, local_id, content_hash
                FROM notion_sync_queue WHERE id = ?
                """,
                (queue_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Unknown Notion queue item: {queue_id}")
            conn.execute(
                """
                UPDATE notion_sync_queue
                SET status = 'SYNCED', attempt_count = attempt_count + 1,
                    last_error = NULL, updated_at = ?
                WHERE id = ?
                """,
                (now, queue_id),
            )
            conn.execute(
                """
                INSERT INTO notion_sync_state
                (entity_type, local_id, notion_page_id, notion_page_url,
                 content_hash, last_synced_at, sync_status, retry_count, last_error)
                VALUES (?, ?, ?, ?, ?, ?, 'SYNCED', 0, NULL)
                ON CONFLICT(entity_type, local_id) DO UPDATE SET
                    notion_page_id = excluded.notion_page_id,
                    notion_page_url = excluded.notion_page_url,
                    content_hash = excluded.content_hash,
                    last_synced_at = excluded.last_synced_at,
                    sync_status = 'SYNCED',
                    retry_count = 0,
                    last_error = NULL
                """,
                (
                    row["entity_type"],
                    int(row["local_id"]),
                    notion_page_id,
                    notion_page_url,
                    row["content_hash"],
                    now,
                ),
            )
            return {
                "queue_id": queue_id,
                "entity_type": row["entity_type"],
                "local_id": int(row["local_id"]),
                "status": "SYNCED",
            }

    def notion_sync_fail(self, queue_id: int, error: str) -> dict[str, Any]:
        self.initialize()
        now = utc_now()
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT entity_type, local_id
                FROM notion_sync_queue WHERE id = ?
                """,
                (queue_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Unknown Notion queue item: {queue_id}")
            conn.execute(
                """
                UPDATE notion_sync_queue
                SET status = 'FAILED', attempt_count = attempt_count + 1,
                    last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                (error, now, queue_id),
            )
            conn.execute(
                """
                INSERT INTO notion_sync_state
                (entity_type, local_id, sync_status, retry_count, last_error)
                VALUES (?, ?, 'FAILED', 1, ?)
                ON CONFLICT(entity_type, local_id) DO UPDATE SET
                    sync_status = 'FAILED',
                    retry_count = retry_count + 1,
                    last_error = excluded.last_error
                """,
                (row["entity_type"], int(row["local_id"]), error),
            )
            return {
                "queue_id": queue_id,
                "entity_type": row["entity_type"],
                "local_id": int(row["local_id"]),
                "status": "FAILED",
                "error": error,
            }

    def retry_notion_sync(self) -> int:
        self.initialize()
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT entity_type, local_id FROM notion_sync_queue WHERE status = 'FAILED'"
            ).fetchall()
            for row in rows:
                self._queue_sync_conn(
                    conn, row["entity_type"], int(row["local_id"])
                )
            return len(rows)

    def notion_state(
        self, entity_type: str | None = None, local_id: int | None = None
    ) -> list[dict[str, Any]]:
        self.initialize()
        query = "SELECT * FROM notion_sync_state"
        params: list[Any] = []
        conditions = []
        if entity_type:
            conditions.append("entity_type = ?")
            params.append(entity_type)
        if local_id is not None:
            conditions.append("local_id = ?")
            params.append(local_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY entity_type, local_id"
        with self.connect() as conn:
            return [
                dict(row) for row in conn.execute(query, tuple(params)).fetchall()
            ]

    def notion_sync_status(self) -> dict[str, Any]:
        self.initialize()
        with self.connect() as conn:
            queue_counts = {
                row["status"]: int(row["count"])
                for row in conn.execute(
                    """
                    SELECT status, COUNT(*) AS count
                    FROM notion_sync_queue GROUP BY status
                    """
                ).fetchall()
            }
            state_counts = {
                row["sync_status"]: int(row["count"])
                for row in conn.execute(
                    """
                    SELECT sync_status, COUNT(*) AS count
                    FROM notion_sync_state GROUP BY sync_status
                    """
                ).fetchall()
            }
            failures = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT entity_type, local_id, retry_count, last_error
                    FROM notion_sync_state
                    WHERE sync_status = 'FAILED'
                    ORDER BY retry_count DESC, entity_type, local_id
                    """
                ).fetchall()
            ]
        return {
            "configured": bool(
                self.notion_configuration()["data_sources"]
            ),
            "target": self.notion_configuration(),
            "queue": queue_counts,
            "state": state_counts,
            "failures": failures,
        }
