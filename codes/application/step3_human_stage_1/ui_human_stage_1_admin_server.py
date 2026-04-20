#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlparse

from application.step3_human_stage_1.ui_human_stage_1_server import (
    TARGET_ANNOTATOR_FRAMES,
    slot_summary_from_json,
)


REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


@dataclass(frozen=True)
class SegmentMeta:
    segment_id: str
    video_stem: str
    segment_type: str
    start_frame: int
    end_frame: int
    representative_frame: int
    frame_count: int


class HumanStage1AdminState:
    def __init__(self, batch_dir: Path, static_dir: Path) -> None:
        self.batch_dir = batch_dir.resolve()
        self.static_dir = resolve_repo_path(static_dir)
        self.db_path = self.batch_dir / "human_stage_1" / "ui_human_stage_1.sqlite3"
        self.stage1_prep_dir = self.batch_dir / "human_stage_1_prep"
        self.segment_lookup: Dict[str, SegmentMeta] = {}
        self.segment_order: List[SegmentMeta] = []

    def initialize(self) -> None:
        if not self.db_path.exists():
            raise FileNotFoundError(f"stage1 db not found: {self.db_path}")
        if not self.stage1_prep_dir.exists():
            raise FileNotFoundError(f"stage1 prep dir not found: {self.stage1_prep_dir}")
        if not self.static_dir.exists():
            raise FileNotFoundError(f"admin static dir not found: {self.static_dir}")
        self.segment_order = self._load_segments()
        self.segment_lookup = {segment.segment_id: segment for segment in self.segment_order}

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30, isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _load_segments(self) -> List[SegmentMeta]:
        segments: List[SegmentMeta] = []
        for path in sorted(self.stage1_prep_dir.glob("*.segments.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            for item in payload.get("segments", []):
                segments.append(
                    SegmentMeta(
                        segment_id=str(item["segment_id"]),
                        video_stem=str(item["video_stem"]),
                        segment_type=str(item["segment_type"]),
                        start_frame=int(item["start_frame"]),
                        end_frame=int(item["end_frame"]),
                        representative_frame=int(item["representative_frame"]),
                        frame_count=int(item["frame_count"]),
                    )
                )
        segments.sort(key=lambda item: (item.video_stem, item.start_frame, item.end_frame, item.segment_id))
        return segments

    def _annotation_counts(self, conn: sqlite3.Connection) -> Dict[str, int]:
        rows = conn.execute(
            """
            SELECT segment_id, COUNT(*) AS annotation_count
            FROM coarse_labels
            GROUP BY segment_id
            """
        ).fetchall()
        return {str(row["segment_id"]): int(row["annotation_count"]) for row in rows}

    def overview(self) -> Dict[str, Any]:
        conn = self._connect()
        try:
            queue_row = conn.execute(
                """
                SELECT
                    COUNT(*) AS queue_total,
                    SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS queue_completed,
                    SUM(CASE WHEN status='completed' AND pass_index=1 THEN 1 ELSE 0 END) AS pass1_completed,
                    SUM(CASE WHEN status='completed' AND pass_index=2 THEN 1 ELSE 0 END) AS pass2_completed
                FROM stage1_assignment_queue
                """
            ).fetchone()
            annotation_row = conn.execute(
                """
                SELECT
                    COUNT(*) AS annotation_count,
                    COUNT(DISTINCT annotator_id) AS annotator_count
                FROM coarse_labels
                """
            ).fetchone()
            current_queue_row = conn.execute(
                """
                SELECT queue_id, segment_id, pass_index, queue_order
                FROM stage1_assignment_queue
                WHERE status='pending'
                ORDER BY queue_order ASC
                LIMIT 1
                """
            ).fetchone()
            annotator_rows = conn.execute(
                """
                SELECT annotator_id, segment_id
                FROM coarse_labels
                ORDER BY submitted_at ASC, annotation_id ASC
                """
            ).fetchall()
            annotation_counts = self._annotation_counts(conn)
        finally:
            conn.close()

        annotator_frame_counts: Dict[str, int] = {}
        for row in annotator_rows:
            annotator_id = str(row["annotator_id"])
            segment = self.segment_lookup.get(str(row["segment_id"]))
            if segment is None:
                continue
            annotator_frame_counts[annotator_id] = annotator_frame_counts.get(annotator_id, 0) + segment.frame_count

        segment_annotation_bins = {"0": 0, "1": 0, "2": 0, "3+": 0}
        for segment in self.segment_order:
            count = annotation_counts.get(segment.segment_id, 0)
            if count <= 0:
                segment_annotation_bins["0"] += 1
            elif count == 1:
                segment_annotation_bins["1"] += 1
            elif count == 2:
                segment_annotation_bins["2"] += 1
            else:
                segment_annotation_bins["3+"] += 1

        return {
            "segment_count": len(self.segment_order),
            "queue_total": int(queue_row["queue_total"] or 0),
            "queue_completed": int(queue_row["queue_completed"] or 0),
            "queue_pending": int((queue_row["queue_total"] or 0) - (queue_row["queue_completed"] or 0)),
            "pass1_completed": int(queue_row["pass1_completed"] or 0),
            "pass2_completed": int(queue_row["pass2_completed"] or 0),
            "annotation_count": int(annotation_row["annotation_count"] or 0),
            "annotator_count": int(annotation_row["annotator_count"] or 0),
            "current_queue": None
            if current_queue_row is None
            else {
                "queue_id": int(current_queue_row["queue_id"]),
                "segment_id": str(current_queue_row["segment_id"]),
                "pass_index": int(current_queue_row["pass_index"]),
                "queue_order": int(current_queue_row["queue_order"]),
            },
            "segment_annotation_bins": [
                {"label": "0", "count": segment_annotation_bins["0"]},
                {"label": "1", "count": segment_annotation_bins["1"]},
                {"label": "2", "count": segment_annotation_bins["2"]},
                {"label": "3+", "count": segment_annotation_bins["3+"]},
            ],
            "annotator_frame_counts": [
                {"annotator_id": annotator_id, "completed_frames": completed_frames}
                for annotator_id, completed_frames in sorted(
                    annotator_frame_counts.items(), key=lambda item: (-item[1], item[0])
                )
            ],
        }

    def annotator_stats(self) -> Dict[str, Any]:
        conn = self._connect()
        try:
            annotation_rows = conn.execute(
                """
                SELECT annotator_id, segment_id, submitted_at
                FROM coarse_labels
                ORDER BY submitted_at ASC, annotation_id ASC
                """
            ).fetchall()
            recent_rows = conn.execute(
                """
                SELECT
                    a.annotation_id,
                    a.annotator_id,
                    a.segment_id,
                    a.video_stem,
                    a.frame_index,
                    a.submitted_at,
                    a.slot_decisions_json,
                    COALESCE(q.pass_index, 0) AS pass_index
                FROM coarse_labels a
                LEFT JOIN stage1_assignment_queue q
                  ON q.annotation_id = a.annotation_id
                ORDER BY a.submitted_at DESC, a.annotation_id DESC
                LIMIT 500
                """
            ).fetchall()
        finally:
            conn.close()

        merged: Dict[str, Dict[str, Any]] = {}
        for row in annotation_rows:
            annotator_id = str(row["annotator_id"])
            segment = self.segment_lookup.get(str(row["segment_id"]))
            frame_count = int(segment.frame_count) if segment is not None else 0
            entry = merged.setdefault(
                annotator_id,
                {
                    "annotator_id": annotator_id,
                    "annotation_count": 0,
                    "completed_frames": 0,
                    "target_frames": TARGET_ANNOTATOR_FRAMES,
                    "progress_ratio": 0.0,
                    "latest_submitted_at": "",
                },
            )
            entry["annotation_count"] += 1
            entry["completed_frames"] += frame_count
            entry["latest_submitted_at"] = str(row["submitted_at"])

        for entry in merged.values():
            entry["progress_ratio"] = (
                entry["completed_frames"] / TARGET_ANNOTATOR_FRAMES if TARGET_ANNOTATOR_FRAMES > 0 else 0.0
            )

        annotators = sorted(
            merged.values(),
            key=lambda item: (-int(item["completed_frames"]), item["annotator_id"]),
        )

        recent_annotations = [
            {
                "annotation_id": str(row["annotation_id"]),
                "annotator_id": str(row["annotator_id"]),
                "segment_id": str(row["segment_id"]),
                "video_stem": str(row["video_stem"]),
                "frame_index": int(row["frame_index"]),
                "submitted_at": str(row["submitted_at"]),
                "pass_index": int(row["pass_index"]),
                "slots_summary": slot_summary_from_json(str(row["slot_decisions_json"])),
            }
            for row in recent_rows
        ]

        return {
            "annotators": annotators,
            "recent_annotations": recent_annotations,
        }

    def segments(self) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            annotation_counts = self._annotation_counts(conn)
        finally:
            conn.close()
        return [
            {
                "segment_id": segment.segment_id,
                "video_stem": segment.video_stem,
                "segment_type": segment.segment_type,
                "frame_count": segment.frame_count,
                "annotation_count": int(annotation_counts.get(segment.segment_id, 0)),
            }
            for segment in self.segment_order
        ]

    def segment_detail(self, segment_id: str) -> Dict[str, Any]:
        segment = self.segment_lookup.get(segment_id)
        if segment is None:
            raise ValueError(f"invalid segment_id: {segment_id}")

        conn = self._connect()
        try:
            queue_rows = conn.execute(
                """
                SELECT queue_id, pass_index, queue_order, status, annotation_id, completed_by, completed_at
                FROM stage1_assignment_queue
                WHERE segment_id=?
                ORDER BY pass_index ASC, queue_order ASC
                """,
                (segment_id,),
            ).fetchall()
            annotation_rows = conn.execute(
                """
                SELECT annotation_id, annotator_id, frame_index, submitted_at, slot_decisions_json
                FROM coarse_labels
                WHERE segment_id=?
                ORDER BY submitted_at ASC, annotation_id ASC
                """,
                (segment_id,),
            ).fetchall()
        finally:
            conn.close()

        return {
            "segment": {
                "segment_id": segment.segment_id,
                "video_stem": segment.video_stem,
                "segment_type": segment.segment_type,
                "start_frame": segment.start_frame,
                "end_frame": segment.end_frame,
                "representative_frame": segment.representative_frame,
                "frame_count": segment.frame_count,
            },
            "queue_items": [
                {
                    "queue_id": int(row["queue_id"]),
                    "pass_index": int(row["pass_index"]),
                    "queue_order": int(row["queue_order"]),
                    "status": str(row["status"]),
                    "annotation_id": str(row["annotation_id"]),
                    "completed_by": str(row["completed_by"]),
                    "completed_at": str(row["completed_at"]),
                }
                for row in queue_rows
            ],
            "annotations": [
                {
                    "annotation_id": str(row["annotation_id"]),
                    "annotator_id": str(row["annotator_id"]),
                    "frame_index": int(row["frame_index"]),
                    "submitted_at": str(row["submitted_at"]),
                    "slots_summary": slot_summary_from_json(str(row["slot_decisions_json"])),
                }
                for row in annotation_rows
            ],
        }


class HumanStage1AdminHandler(BaseHTTPRequestHandler):
    server_version = "HumanStage1Admin/1.0"

    @property
    def state(self) -> HumanStage1AdminState:
        return self.server.state  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/overview":
            return self._handle_overview()
        if path == "/api/annotators":
            return self._handle_annotators()
        if path == "/api/segments":
            return self._handle_segments()
        if path == "/api/segment_detail":
            return self._handle_segment_detail(parsed.query)

        if path == "/":
            return self._serve_static("index.html", "text/html; charset=utf-8")
        if path == "/styles.css":
            return self._serve_static("styles.css", "text/css; charset=utf-8")
        if path == "/app.js":
            return self._serve_static("app.js", "application/javascript; charset=utf-8")

        self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def _handle_overview(self) -> None:
        try:
            data = self.state.overview()
        except Exception as exc:
            return self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
        self._send_json(HTTPStatus.OK, {"ok": True, "overview": data})

    def _handle_annotators(self) -> None:
        try:
            data = self.state.annotator_stats()
        except Exception as exc:
            return self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
        self._send_json(HTTPStatus.OK, {"ok": True, **data})

    def _handle_segments(self) -> None:
        try:
            rows = self.state.segments()
        except Exception as exc:
            return self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
        self._send_json(HTTPStatus.OK, {"ok": True, "segments": rows})

    def _handle_segment_detail(self, query: str) -> None:
        q = parse_qs(query)
        segment_id = str(q.get("segment_id", [""])[0]).strip()
        try:
            detail = self.state.segment_detail(segment_id)
        except Exception as exc:
            return self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
        self._send_json(HTTPStatus.OK, {"ok": True, "detail": detail})

    def _serve_static(self, filename: str, content_type: str) -> None:
        path = self.state.static_dir / filename
        if not path.exists():
            return self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": f"missing static: {filename}"})
        content = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, status: HTTPStatus, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Human stage 1 admin panel server")
    parser.add_argument("--batch-dir", type=Path, required=True)
    parser.add_argument(
        "--static-dir",
        type=Path,
        default=Path("codes/application/step3_human_stage_1/admin_web"),
    )
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10087)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    batch_dir = resolve_repo_path(args.batch_dir)
    if not batch_dir.exists():
        raise SystemExit(f"batch directory does not exist: {batch_dir}")

    state = HumanStage1AdminState(batch_dir=batch_dir, static_dir=args.static_dir)
    state.initialize()

    server = ThreadingHTTPServer((args.host, args.port), HumanStage1AdminHandler)
    server.state = state  # type: ignore[attr-defined]
    try:
        print(
            json.dumps(
                {
                    "batch_dir": str(batch_dir),
                    "db_path": str(state.db_path),
                    "segment_count": len(state.segment_order),
                    "host": args.host,
                    "port": args.port,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
