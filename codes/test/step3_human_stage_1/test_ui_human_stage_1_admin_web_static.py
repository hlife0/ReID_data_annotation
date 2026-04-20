#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path


class HumanStage1AdminWebStaticTests(unittest.TestCase):
    def test_human_stage_1_admin_ui_exposes_stage1_specific_sections(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        html = (
            repo_root / "codes" / "application" / "step3_human_stage_1" / "admin_web" / "index.html"
        ).read_text(encoding="utf-8")
        js = (
            repo_root / "codes" / "application" / "step3_human_stage_1" / "admin_web" / "app.js"
        ).read_text(encoding="utf-8")
        css = (
            repo_root / "codes" / "application" / "step3_human_stage_1" / "admin_web" / "styles.css"
        ).read_text(encoding="utf-8")

        self.assertIn("human_stage_1", html)
        self.assertIn('id="mQueueTotal"', html)
        self.assertIn('id="mQueueCompleted"', html)
        self.assertIn('id="mPass1Completed"', html)
        self.assertIn('id="mPass2Completed"', html)
        self.assertIn('id="segmentCountChart"', html)
        self.assertIn('id="annotatorProgressChart"', html)
        self.assertIn('id="annotatorBody"', html)
        self.assertIn('id="recentBody"', html)
        self.assertIn('id="segmentIdSelect"', html)
        self.assertIn('id="querySegmentBtn"', html)
        self.assertIn('id="segmentSummary"', html)
        self.assertIn('id="segmentDetailBody"', html)
        self.assertIn("function renderOverview(", js)
        self.assertIn("function renderAnnotatorTable(", js)
        self.assertIn("function renderRecentTable(", js)
        self.assertIn("function renderSegmentDetail(", js)
        self.assertIn('href="/admin/styles.css"', html)
        self.assertIn('src="/admin/app.js"', html)
        self.assertIn('fetchJson("/api/admin/overview")', js)
        self.assertIn('fetchJson("/api/admin/annotators")', js)
        self.assertIn('fetchJson("/api/admin/segments")', js)
        self.assertIn("/api/admin/segment_detail?segment_id=", js)
        self.assertIn(".metric-grid", css)
        self.assertIn(".panel-grid", css)
        self.assertIn(".bar-chart", css)

        self.assertNotIn("ui_review.sqlite3", js)
        self.assertNotIn("frame_query_title", html)
        self.assertNotIn('id="frameIndexInput"', html)


if __name__ == "__main__":
    unittest.main()
