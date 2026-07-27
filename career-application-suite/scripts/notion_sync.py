#!/usr/bin/env python3
"""Build deterministic Notion connector upsert plans from local SQLite data."""

from __future__ import annotations

import json
import re
from typing import Any

from store import CareerStore, stable_hash


SOURCE_NAMES = {
    "boss": "BOSS",
    "feishu": "飞书",
    "qqdocs": "腾讯文档",
    "company_site": "公司官网",
    "manual": "手动",
}

LEGACY_APPLICATION_STATUS = {
    "PREPARING": "待投递",
    "APPLIED": "等消息",
    "VIEWED": "等消息",
    "CONTACTED": "等消息",
    "WRITTEN_TEST": "待面试",
    "INTERVIEW_1": "一面等消息",
    "INTERVIEW_2": "待面试",
    "FINAL_INTERVIEW": "待面试",
    "OFFER": "中了",
    "REJECTED_SCREEN": "很遗憾",
    "REJECTED_AFTER_INTERVIEW": "很遗憾",
    "NO_RESPONSE": "等消息",
    "WITHDRAWN": "很遗憾",
    "JOB_CLOSED": "很遗憾",
}

WEIGHT_PROPERTY_NAMES = {
    "role_match": "岗位方向匹配",
    "skill_match": "技能匹配",
    "evidence_strength": "证据强度",
    "domain_match": "行业匹配",
    "impact_match": "成果匹配",
    "job_freshness": "岗位新鲜度",
    "source_quality": "来源质量",
    "location_fit": "地点匹配",
}

ENTITY_META = {
    "opportunity": {
        "identity_property": "本地机会ID",
        "title_property": "机会",
    },
    "application": {
        "identity_property": "本地投递ID",
        "title_property": "投递",
    },
    "application_event": {
        "identity_property": "本地事件ID",
        "title_property": "事件",
    },
    "scoring_profile": {
        "identity_property": "版本号",
        "title_property": "权重版本",
    },
}


def _put(properties: dict[str, Any], name: str, value: Any) -> None:
    if value not in (None, ""):
        properties[name] = value


def _put_date(
    properties: dict[str, Any], name: str, value: Any, is_datetime: bool
) -> None:
    text = str(value or "").strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}", text):
        return
    properties[f"date:{name}:start"] = text
    properties[f"date:{name}:is_datetime"] = 1 if is_datetime else 0


def _source_name(source: str | None) -> str:
    return SOURCE_NAMES.get(str(source or "").lower(), "手动")


def _recruitment_batch(value: str | None) -> str | None:
    text = str(value or "")
    for option in ("暑期实习", "秋招", "提前批", "春招", "日常实习"):
        if option in text:
            return option
    return "其他" if text else None


def _legacy_batch(value: str | None) -> str | None:
    text = str(value or "")
    for option in ("暑期实习", "秋招"):
        if option in text:
            return option
    return None


def _score(features_json: str, weights_json: str) -> float:
    features = json.loads(features_json or "{}")
    weights = json.loads(weights_json or "{}")
    return round(
        100
        * sum(
            float(weight)
            * max(0.0, min(1.0, float(features.get(name, 0.5))))
            for name, weight in weights.items()
        ),
        1,
    )


def _state_url(
    conn, entity_type: str, local_id: int
) -> str | None:
    row = conn.execute(
        """
        SELECT notion_page_url, notion_page_id
        FROM notion_sync_state
        WHERE entity_type = ? AND local_id = ? AND sync_status = 'SYNCED'
        """,
        (entity_type, local_id),
    ).fetchone()
    if row is None:
        return None
    return row["notion_page_url"] or row["notion_page_id"]


def _opportunity_payload(store: CareerStore, local_id: int) -> dict[str, Any]:
    with store.connect() as conn:
        row = conn.execute(
            """
            SELECT o.*, GROUP_CONCAT(DISTINCT sr.source) AS sources,
                   sp.weights_json
            FROM opportunities o
            LEFT JOIN opportunity_sources os ON os.opportunity_id = o.id
            LEFT JOIN source_records sr ON sr.id = os.source_record_id
            CROSS JOIN scoring_profiles sp
            WHERE o.id = ? AND sp.active = 1
            GROUP BY o.id
            """,
            (local_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Unknown opportunity: {local_id}")
        parents = conn.execute(
            """
            SELECT parent_id FROM opportunity_relations
            WHERE child_id = ? AND relation_type = 'CONTAINS'
            ORDER BY parent_id
            """,
            (local_id,),
        ).fetchall()
        relation_refs = [
            {
                "property": "上级招聘批次",
                "entity_type": "opportunity",
                "local_id": int(parent["parent_id"]),
                "notion_page_url": _state_url(
                    conn, "opportunity", int(parent["parent_id"])
                ),
            }
            for parent in parents
        ]

    sources = [
        _source_name(source)
        for source in sorted(set((row["sources"] or "").split(",")))
        if source
    ]
    properties: dict[str, Any] = {
        "机会": f"{row['company']}｜{row['title']}",
        "本地机会ID": int(row["id"]),
        "实体类型": row["kind"],
        "公司": row["company"],
        "岗位": row["title"],
        "来源": sources,
        "主来源": _source_name(row["primary_source"]),
        "推荐评分": _score(row["features_json"], row["weights_json"]),
        "重复状态": (
            "可能重复"
            if row["possible_duplicate_of"]
            else ("已合并" if len(sources) > 1 else "唯一")
        ),
        "机会状态": "开放" if row["status"] == "OPEN" else "已关闭",
    }
    _put(properties, "工作地点", row["location"])
    _put(properties, "招聘批次", _recruitment_batch(row["recruitment_type"]))
    _put(properties, "JD链接", row["url"])
    if row["hard_eligible"] is not None:
        properties["硬性条件通过"] = (
            "__YES__" if int(row["hard_eligible"]) else "__NO__"
        )
    _put_date(properties, "开始时间", row["application_start"], False)
    _put_date(properties, "截止时间", row["application_deadline"], False)
    _put_date(properties, "最近同步", row["updated_at"], True)
    return {"properties": properties, "relation_refs": relation_refs}


def _application_payload(store: CareerStore, local_id: int) -> dict[str, Any]:
    with store.connect() as conn:
        row = conn.execute(
            """
            SELECT a.*, o.company, o.title, o.url, o.recruitment_type,
                   o.primary_source, o.features_json, sp.weights_json,
                   js.base_revision_id, ra.id AS resume_id,
                   ra.path AS resume_path, ra.content_hash AS resume_hash,
                   (
                       SELECT ae.note FROM application_events ae
                       WHERE ae.application_id = a.id
                       ORDER BY ae.occurred_at DESC, ae.id DESC LIMIT 1
                   ) AS latest_feedback
            FROM applications a
            JOIN opportunities o ON o.id = a.opportunity_id
            CROSS JOIN scoring_profiles sp
            LEFT JOIN job_sessions js ON js.id = a.job_session_id
            LEFT JOIN resume_artifacts ra ON ra.id = a.resume_artifact_id
            WHERE a.id = ? AND sp.active = 1
            """,
            (local_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Unknown application: {local_id}")
        opportunity_url = _state_url(
            conn, "opportunity", int(row["opportunity_id"])
        )

    properties: dict[str, Any] = {
        "投递": f"{row['company']}｜{row['title']}",
        "本地投递ID": int(row["id"]),
        "公司": row["company"],
        "岗位": row["title"],
        "来源": _source_name(row["primary_source"]),
        "投递状态": LEGACY_APPLICATION_STATUS[row["status"]],
        "标准阶段": row["status"],
        "岗位评分": _score(row["features_json"], row["weights_json"]),
    }
    _put(properties, "招聘批次", _legacy_batch(row["recruitment_type"]))
    _put(properties, "JD链接", row["url"])
    _put(properties, "Base Revision", row["base_revision_id"])
    _put(properties, "Job Session ID", row["job_session_id"])
    if row["resume_id"] is not None:
        properties["简历版本"] = (
            f"artifact-{row['resume_id']} · {str(row['resume_hash'])[:12]}"
        )
    _put(properties, "简历路径", row["resume_path"])
    _put(properties, "最新反馈", row["latest_feedback"])
    _put_date(properties, "投递时间", row["applied_at"], True)
    _put_date(properties, "最近更新", row["updated_at"], True)
    relation_refs = [
        {
            "property": "岗位机会",
            "entity_type": "opportunity",
            "local_id": int(row["opportunity_id"]),
            "notion_page_url": opportunity_url,
        }
    ]
    return {"properties": properties, "relation_refs": relation_refs}


def _application_event_payload(
    store: CareerStore, local_id: int
) -> dict[str, Any]:
    with store.connect() as conn:
        row = conn.execute(
            """
            SELECT ae.*, o.company, o.title
            FROM application_events ae
            JOIN applications a ON a.id = ae.application_id
            JOIN opportunities o ON o.id = a.opportunity_id
            WHERE ae.id = ?
            """,
            (local_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Unknown application event: {local_id}")
        application_url = _state_url(
            conn, "application", int(row["application_id"])
        )
    properties: dict[str, Any] = {
        "事件": f"{row['company']}｜{row['title']}｜{row['stage']}",
        "本地事件ID": int(row["id"]),
        "事件阶段": row["stage"],
        "学习信号": float(row["signal"]),
        "参与学习": "__YES__" if row["counts_for_learning"] else "__NO__",
        "结果来源": "手动",
    }
    _put(properties, "备注", row["note"])
    _put_date(properties, "发生时间", row["occurred_at"], True)
    relation_refs = [
        {
            "property": "投递记录",
            "entity_type": "application",
            "local_id": int(row["application_id"]),
            "notion_page_url": application_url,
        }
    ]
    return {"properties": properties, "relation_refs": relation_refs}


def _scoring_profile_payload(
    store: CareerStore, local_id: int
) -> dict[str, Any]:
    with store.connect() as conn:
        row = conn.execute(
            "SELECT * FROM scoring_profiles WHERE id = ?", (local_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Unknown scoring profile: {local_id}")
        changes = conn.execute(
            """
            SELECT feature, old_weight, new_weight, delta
            FROM weight_changes
            WHERE scoring_profile_id = ?
            ORDER BY ABS(delta) DESC, feature
            """,
            (local_id,),
        ).fetchall()
    weights = json.loads(row["weights_json"])
    summary = "; ".join(
        f"{change['feature']} {change['old_weight']:.3f}→{change['new_weight']:.3f}"
        for change in changes
    )
    properties: dict[str, Any] = {
        "权重版本": f"v{row['version']}",
        "版本号": int(row["version"]),
        "当前使用": "__YES__" if row["active"] else "__NO__",
        "样本数量": int(row["sample_count"]),
        "调整原因": row["reason"],
        "变化摘要": summary or "baseline",
    }
    for feature, notion_name in WEIGHT_PROPERTY_NAMES.items():
        properties[notion_name] = float(weights[feature])
    _put_date(properties, "创建时间", row["created_at"], True)
    return {"properties": properties, "relation_refs": []}


BUILDERS = {
    "opportunity": _opportunity_payload,
    "application": _application_payload,
    "application_event": _application_event_payload,
    "scoring_profile": _scoring_profile_payload,
}


def build_sync_plan(store: CareerStore, limit: int = 50) -> dict[str, Any]:
    """Return connector-ready upserts without making any external writes."""
    config = store.notion_configuration()
    data_sources = config["data_sources"]
    missing = sorted(set(ENTITY_META) - set(data_sources))
    if missing:
        raise ValueError(
            f"Notion is not configured; missing: {', '.join(missing)}"
        )

    operations = []
    skipped = 0
    for queue_item in store.pending_notion_queue():
        if len(operations) >= limit:
            break
        entity_type = queue_item["entity_type"]
        built = BUILDERS[entity_type](store, int(queue_item["local_id"]))
        payload = {
            "entity_type": entity_type,
            "local_id": int(queue_item["local_id"]),
            "data_source_id": data_sources[entity_type],
            "identity_property": ENTITY_META[entity_type]["identity_property"],
            "identity_value": (
                built["properties"]["版本号"]
                if entity_type == "scoring_profile"
                else int(queue_item["local_id"])
            ),
            "title_property": ENTITY_META[entity_type]["title_property"],
            "properties": built["properties"],
            "relation_refs": built["relation_refs"],
        }
        content_hash = stable_hash(
            json.dumps(payload, ensure_ascii=False, sort_keys=True)
        )
        store.set_notion_queue_payload(
            int(queue_item["id"]), payload, content_hash
        )
        if (
            queue_item.get("notion_page_id")
            and queue_item.get("synced_content_hash") == content_hash
        ):
            store.notion_sync_ack(
                int(queue_item["id"]),
                queue_item["notion_page_id"],
                queue_item.get("notion_page_url") or "",
            )
            skipped += 1
            continue
        unresolved = [
            {
                "entity_type": ref["entity_type"],
                "local_id": ref["local_id"],
            }
            for ref in built["relation_refs"]
            if not ref.get("notion_page_url")
        ]
        properties = dict(built["properties"])
        for ref in built["relation_refs"]:
            if ref.get("notion_page_url"):
                properties[ref["property"]] = [ref["notion_page_url"]]
        operations.append(
            {
                "queue_id": int(queue_item["id"]),
                "action": "UPSERT",
                "ready": not unresolved,
                "unresolved_dependencies": unresolved,
                "notion_page_id": queue_item.get("notion_page_id"),
                "notion_page_url": queue_item.get("notion_page_url"),
                **payload,
                "properties": properties,
                "content_hash": content_hash,
            }
        )
    return {
        "target_page_url": config.get("page_url"),
        "operation_count": len(operations),
        "skipped_unchanged": skipped,
        "operations": operations,
    }
