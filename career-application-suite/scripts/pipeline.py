#!/usr/bin/env python3
"""CLI entry point for Career Application Suite."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from adapters import boss as boss_adapter
from dashboard import serve
from evidence_guard import validate_file
from notion_sync import build_sync_plan
from store import CareerStore


DEFAULT_DB = Path("career-data/career.db")


def print_json(value) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def read_json_records(path: str) -> list[dict]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(value, dict):
        value = value.get("records") or value.get("items") or [value]
    if not isinstance(value, list):
        raise ValueError("Input must be a JSON object or list")
    return value


def opportunity_markdown(items: list[dict]) -> str:
    jobs = [item for item in items if item["kind"] == "JOB"]
    campaigns = [item for item in items if item["kind"] == "CAMPAIGN"]

    def section(title: str, records: list[dict]) -> list[str]:
        lines = [f"## {title}", ""]
        if not records:
            return [*lines, "_暂无记录。_", ""]
        lines.extend(
            [
                "| ID | 公司 | 岗位/批次 | 地点 | 评分 | 来源 | 截止时间 | 链接 |",
                "|---:|---|---|---|---:|---|---|---|",
            ]
        )
        for item in records:
            duplicate = (
                f" ⚠ 可能重复 #{item['possible_duplicate_of']}"
                if item.get("possible_duplicate_of")
                else ""
            )
            lines.append(
                f"| {item['id']} | {item['company']} | {item['title']}{duplicate} | "
                f"{item.get('location') or ''} | {item['score']} | "
                f"{item.get('sources') or ''} | {item.get('application_deadline') or ''} | "
                f"{item.get('url') or ''} |"
            )
        lines.append("")
        return lines

    return "\n".join(
        [
            "---",
            "generated_by: career-application-suite",
            "deduplicated: true",
            "---",
            "",
            "# 岗位机会报告",
            "",
            *section("具体岗位", jobs),
            *section("公司招聘批次", campaigns),
        ]
    )


def application_markdown(store: CareerStore) -> str:
    lines = [
        "---",
        "generated_by: career-application-suite",
        "---",
        "",
        "# 投递记录",
        "",
    ]
    applications = store.applications()
    if not applications:
        return "\n".join([*lines, "_暂无投递记录。_", ""])
    for application in applications:
        lines.extend(
            [
                f"## #{application['id']} {application['company']} — {application['title']}",
                "",
                f"- 当前阶段：`{application['status']}`",
                f"- 投递时间：{application['applied_at']}",
                f"- Base Revision：{application.get('base_revision_id') or '未记录'}",
                f"- 简历快照：{application.get('resume_path') or '未记录'}",
                "",
                "### 事件时间线",
                "",
            ]
        )
        for event in store.application_events(application["id"]):
            note = f" — {event['note']}" if event.get("note") else ""
            lines.append(
                f"- {event['occurred_at']} · `{event['stage']}` · "
                f"signal={event['signal']}{note}"
            )
        lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Initialize the database")

    vault_add = sub.add_parser("vault-add", help="Create a new Base revision")
    vault_add.add_argument("--input", required=True, help="Career vault Markdown")
    vault_add.add_argument("--summary", required=True)

    sub.add_parser("vault-history", help="List Base revisions")
    vault_export = sub.add_parser("vault-export", help="Export a Base revision")
    vault_export.add_argument("--revision", type=int)
    vault_export.add_argument("--output", required=True)

    import_cmd = sub.add_parser("import", help="Import normalized source records")
    import_cmd.add_argument(
        "--source",
        required=True,
        choices=["boss", "feishu", "qqdocs", "company_site", "manual"],
    )
    import_cmd.add_argument("--input", required=True, help="JSON file")

    boss_search = sub.add_parser("boss-search", help="Search BOSS read-only and import")
    boss_search.add_argument("keyword")
    boss_search.add_argument(
        "--boss-arg",
        action="append",
        default=[],
        help="One additional boss search argument; repeat as needed",
    )

    list_cmd = sub.add_parser("opportunities", help="List opportunities")
    list_cmd.add_argument("--kind", choices=["JOB", "CAMPAIGN"])
    list_cmd.add_argument("--markdown")

    score = sub.add_parser("opportunity-score", help="Set analyzed scoring features")
    score.add_argument("--opportunity", type=int, required=True)
    score.add_argument("--input", required=True, help="JSON feature object")
    score.add_argument(
        "--hard-eligible", choices=["true", "false", "unknown"], default="unknown"
    )

    relation = sub.add_parser(
        "opportunity-relate", help="Relate a campaign to a concrete job"
    )
    relation.add_argument("--campaign", type=int, required=True)
    relation.add_argument("--job", type=int, required=True)

    session = sub.add_parser("session-create", help="Create a JD session")
    session.add_argument("--opportunity", type=int, required=True)

    overlay = sub.add_parser("session-overlay", help="Set a session overlay")
    overlay.add_argument("--session", type=int, required=True)
    overlay.add_argument("--input", required=True)

    plan = sub.add_parser("session-plan", help="Set a session match plan")
    plan.add_argument("--session", type=int, required=True)
    plan.add_argument("--input", required=True)

    resume = sub.add_parser("resume-add", help="Register a resume artifact")
    resume.add_argument("--session", type=int, required=True)
    resume.add_argument("--format", required=True)
    resume.add_argument("--path", required=True)

    evidence = sub.add_parser("evidence-check", help="Validate evidence mapping JSON")
    evidence.add_argument("--mapping", required=True)

    application = sub.add_parser("application-create", help="Record an application")
    application.add_argument("--opportunity", type=int, required=True)
    application.add_argument("--session", type=int)
    application.add_argument("--resume", type=int)

    event = sub.add_parser("application-event", help="Record result and auto-learn")
    event.add_argument("--application", type=int, required=True)
    event.add_argument("--stage", required=True)
    event.add_argument("--note", default="")
    event.add_argument("--occurred-at")

    applications = sub.add_parser("applications", help="List applications")
    applications.add_argument("--markdown")
    sub.add_parser("weights", help="Show active scoring weights")
    history = sub.add_parser("weight-history", help="Show scoring history")
    activate = sub.add_parser("weight-activate", help="Restore a weight revision")
    activate.add_argument("--version", type=int, required=True)

    notion_config = sub.add_parser(
        "notion-config", help="Configure connector-based Notion synchronization"
    )
    notion_config.add_argument("--input", required=True, help="Notion target JSON")
    sub.add_parser("notion-enqueue-all", help="Queue all supported local records")
    notion_plan = sub.add_parser(
        "notion-plan", help="Print connector-ready Notion upsert operations"
    )
    notion_plan.add_argument("--limit", type=int, default=50)
    notion_ack = sub.add_parser(
        "notion-ack", help="Acknowledge a successful Notion connector upsert"
    )
    notion_ack.add_argument("--queue", type=int, required=True)
    notion_ack.add_argument("--page-id", required=True)
    notion_ack.add_argument("--page-url", default="")
    notion_fail = sub.add_parser(
        "notion-fail", help="Record a failed Notion connector upsert"
    )
    notion_fail.add_argument("--queue", type=int, required=True)
    notion_fail.add_argument("--error", required=True)
    sub.add_parser("notion-retry", help="Retry all failed Notion operations")
    notion_state = sub.add_parser(
        "notion-state", help="List local-to-Notion page mappings"
    )
    notion_state.add_argument(
        "--entity",
        choices=[
            "opportunity",
            "application",
            "application_event",
            "scoring_profile",
        ],
    )
    notion_state.add_argument("--local-id", type=int)
    sub.add_parser("notion-status", help="Show Notion sync health")

    dashboard = sub.add_parser("dashboard", help="Start local dashboard")
    dashboard.add_argument("--host", default="127.0.0.1")
    dashboard.add_argument("--port", type=int, default=8765)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = CareerStore(args.db)
    try:
        if args.command == "init":
            store.initialize()
            print_json({"database": str(store.path), "initialized": True})
        elif args.command == "vault-add":
            revision = store.add_base_revision(
                Path(args.input).read_text(encoding="utf-8"), args.summary
            )
            print_json({"revision": revision})
        elif args.command == "vault-history":
            print_json([dict(row) for row in store.base_history()])
        elif args.command == "vault-export":
            row = store.base_revision(args.revision)
            if row is None:
                raise ValueError("Base revision not found")
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(row["content_markdown"], encoding="utf-8")
            print_json({"revision": row["id"], "output": str(output.resolve())})
        elif args.command == "import":
            print_json(store.import_opportunities(args.source, read_json_records(args.input)))
        elif args.command == "boss-search":
            records = boss_adapter.search(args.keyword, args.boss_arg)
            print_json(store.import_opportunities("boss", records))
        elif args.command == "opportunities":
            items = store.list_opportunities(args.kind)
            if args.markdown:
                output = Path(args.markdown)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(opportunity_markdown(items), encoding="utf-8")
                print_json({"count": len(items), "markdown": str(output.resolve())})
            else:
                print_json(items)
        elif args.command == "opportunity-score":
            features = json.loads(Path(args.input).read_text(encoding="utf-8"))
            if not isinstance(features, dict):
                raise ValueError("Feature input must be a JSON object")
            hard_eligible = (
                None
                if args.hard_eligible == "unknown"
                else args.hard_eligible == "true"
            )
            store.update_opportunity_features(
                args.opportunity, features, hard_eligible
            )
            print_json({"opportunity": args.opportunity, "features_updated": True})
        elif args.command == "opportunity-relate":
            store.relate_opportunities(args.campaign, args.job)
            print_json(
                {
                    "campaign": args.campaign,
                    "job": args.job,
                    "relation": "CONTAINS",
                }
            )
        elif args.command == "session-create":
            print_json({"session": store.create_session(args.opportunity)})
        elif args.command in {"session-overlay", "session-plan"}:
            field = (
                "overlay_markdown"
                if args.command == "session-overlay"
                else "match_plan_markdown"
            )
            store.update_session_file(
                args.session, field, Path(args.input).read_text(encoding="utf-8")
            )
            print_json({"session": args.session, "updated": field})
        elif args.command == "resume-add":
            print_json(
                {"resume": store.add_resume(args.session, args.format, args.path)}
            )
        elif args.command == "evidence-check":
            result = validate_file(args.mapping)
            print_json(result)
            return 0 if result["passed"] else 2
        elif args.command == "application-create":
            print_json(
                {
                    "application": store.create_application(
                        args.opportunity, args.session, args.resume
                    )
                }
            )
        elif args.command == "application-event":
            print_json(
                store.record_event(
                    args.application, args.stage, args.note, args.occurred_at
                )
            )
        elif args.command == "applications":
            if args.markdown:
                output = Path(args.markdown)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(application_markdown(store), encoding="utf-8")
                print_json({"markdown": str(output.resolve())})
            else:
                print_json(store.applications())
        elif args.command == "weights":
            print_json(store.active_profile())
        elif args.command == "weight-history":
            print_json(store.profile_history())
        elif args.command == "weight-activate":
            store.activate_profile(args.version)
            print_json({"active_version": args.version})
        elif args.command == "notion-config":
            config = json.loads(Path(args.input).read_text(encoding="utf-8"))
            if not isinstance(config, dict):
                raise ValueError("Notion config must be a JSON object")
            print_json(store.configure_notion(config))
        elif args.command == "notion-enqueue-all":
            print_json({"queued": store.enqueue_all_notion()})
        elif args.command == "notion-plan":
            if args.limit < 1:
                raise ValueError("--limit must be at least 1")
            print_json(build_sync_plan(store, args.limit))
        elif args.command == "notion-ack":
            print_json(
                store.notion_sync_ack(
                    args.queue, args.page_id, args.page_url
                )
            )
        elif args.command == "notion-fail":
            print_json(store.notion_sync_fail(args.queue, args.error))
        elif args.command == "notion-retry":
            print_json({"retried": store.retry_notion_sync()})
        elif args.command == "notion-state":
            print_json(store.notion_state(args.entity, args.local_id))
        elif args.command == "notion-status":
            print_json(store.notion_sync_status())
        elif args.command == "dashboard":
            serve(args.db, args.host, args.port)
        return 0
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print_json({"error": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())
