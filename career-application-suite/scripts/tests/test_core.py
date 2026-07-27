#!/usr/bin/env python3
"""Minimal end-to-end self-test."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from evidence_guard import validate_mapping  # noqa: E402
from notion_sync import build_sync_plan  # noqa: E402
from store import CareerStore  # noqa: E402


class CareerSuiteTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "career.db"
        self.store = CareerStore(self.db)
        self.store.initialize()
        self.store.add_base_revision("# Career Vault\n\n- [EV-0001] Built product", "init")

    def tearDown(self):
        self.temp.cleanup()

    def test_dedupe_session_tracking_and_learning(self):
        features = {
            "role_match": 0.9,
            "skill_match": 0.8,
            "evidence_strength": 0.9,
        }
        first = self.store.import_opportunities(
            "boss",
            [
                {
                    "securityId": "a",
                    "companyName": "示例科技",
                    "jobName": "AI 产品经理",
                    "city": "上海",
                    "features": features,
                }
            ],
        )
        second = self.store.import_opportunities(
            "company_site",
            [
                {
                    "id": "official-a",
                    "company": "示例科技",
                    "title": "AI 产品经理",
                    "location": "上海",
                    "url": "https://example.com/jobs/a",
                    "features": features,
                }
            ],
        )
        self.assertEqual(first["imported"], 1)
        self.assertEqual(second["merged"], 1)
        opportunity = self.store.list_opportunities()[0]
        self.assertIn("boss", opportunity["sources"])
        self.assertIn("company_site", opportunity["sources"])
        self.store.update_opportunity_features(
            opportunity["id"],
            {"role_match": 0.95, "skill_match": 0.85},
            hard_eligible=True,
        )

        for stage in ("CONTACTED", "INTERVIEW_1", "OFFER"):
            session = self.store.create_session(opportunity["id"])
            application = self.store.create_application(opportunity["id"], session, None)
            result = self.store.record_event(application, stage)
        self.assertTrue(result["learning"]["updated"])
        self.assertEqual(self.store.active_profile()["version"], 2)
        with self.assertRaisesRegex(ValueError, "at least 21 days"):
            self.store.record_event(application, "NO_RESPONSE")
        old_date = (datetime.now(timezone.utc) + timedelta(days=22)).isoformat()
        no_response = self.store.record_event(
            application, "NO_RESPONSE", occurred_at=old_date
        )
        self.assertEqual(no_response["event_stage"], "NO_RESPONSE")

    def test_campaign_job_isolation_and_evidence_guard(self):
        self.store.import_opportunities(
            "feishu",
            [
                {
                    "company": "示例科技",
                    "title": "2027 秋招",
                    "recruitment_type": "秋招",
                    "kind": "CAMPAIGN",
                }
            ],
        )
        self.store.import_opportunities(
            "boss",
            [
                {
                    "company": "示例科技",
                    "title": "产品经理",
                    "kind": "JOB",
                }
            ],
        )
        records = self.store.list_opportunities()
        self.assertEqual(len(records), 2)
        campaign = next(item for item in records if item["kind"] == "CAMPAIGN")
        job = next(item for item in records if item["kind"] == "JOB")
        self.store.relate_opportunities(campaign["id"], job["id"])
        passed = validate_mapping(
            {
                "claims": [
                    {
                        "claim": "Built product",
                        "source_type": "base",
                        "source_ref": "EV-0001",
                        "supported": True,
                    }
                ]
            }
        )
        self.assertTrue(passed["passed"], json.dumps(passed))

    def test_notion_queue_dependencies_ack_and_retry(self):
        self.store.configure_notion(
            {
                "page_url": "https://notion.example/job",
                "page_id": "job",
                "data_sources": {
                    "opportunity": "opportunities",
                    "application": "applications",
                    "application_event": "events",
                    "scoring_profile": "profiles",
                },
            }
        )
        self.store.import_opportunities(
            "feishu",
            [
                {
                    "company": "示例科技",
                    "title": "2027 秋招",
                    "recruitment_type": "秋招",
                    "kind": "CAMPAIGN",
                }
            ],
        )
        self.store.import_opportunities(
            "boss",
            [
                {
                    "company": "示例科技",
                    "title": "AI 产品经理",
                    "kind": "JOB",
                }
            ],
        )
        opportunities = self.store.list_opportunities()
        campaign = next(item for item in opportunities if item["kind"] == "CAMPAIGN")
        job = next(item for item in opportunities if item["kind"] == "JOB")
        self.store.relate_opportunities(campaign["id"], job["id"])
        session = self.store.create_session(job["id"])
        application = self.store.create_application(job["id"], session, None)

        first_plan = build_sync_plan(self.store)
        campaign_op = next(
            item
            for item in first_plan["operations"]
            if item["entity_type"] == "opportunity"
            and item["local_id"] == campaign["id"]
        )
        job_op = next(
            item
            for item in first_plan["operations"]
            if item["entity_type"] == "opportunity"
            and item["local_id"] == job["id"]
        )
        application_op = next(
            item
            for item in first_plan["operations"]
            if item["entity_type"] == "application"
            and item["local_id"] == application
        )
        self.assertTrue(campaign_op["ready"])
        self.assertFalse(job_op["ready"])
        self.assertFalse(application_op["ready"])
        self.assertNotIn("人工备注", application_op["properties"])
        self.assertNotIn("下一步行动", application_op["properties"])
        self.assertNotIn("下一步时间", application_op["properties"])

        self.store.notion_sync_ack(
            campaign_op["queue_id"],
            "campaign-page",
            "https://notion.example/campaign-page",
        )
        second_plan = build_sync_plan(self.store)
        job_op = next(
            item
            for item in second_plan["operations"]
            if item["entity_type"] == "opportunity"
            and item["local_id"] == job["id"]
        )
        self.assertTrue(job_op["ready"])
        self.assertEqual(
            job_op["properties"]["上级招聘批次"],
            ["https://notion.example/campaign-page"],
        )

        failed = self.store.notion_sync_fail(job_op["queue_id"], "test failure")
        self.assertEqual(failed["status"], "FAILED")
        self.assertEqual(self.store.retry_notion_sync(), 1)
        self.assertEqual(
            self.store.notion_sync_status()["queue"].get("PENDING"), 4
        )


if __name__ == "__main__":
    unittest.main()
