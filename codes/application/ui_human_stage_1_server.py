#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import parse_qs, urlparse

from application.ui_review_server import VideoFrameReader
from process import segment_prep_common as common


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SLOT_NAMES = [f"p{i}" for i in range(1, 8)]
ALLOWED_DECISIONS = ["ai_match", "absent", "needs_manual"]


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="milliseconds")


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


@dataclass(frozen=True)
class SegmentRecord:
    segment_id: str
    video_stem: str
    segment_type: str
    start_frame: int
    end_frame: int
    representative_frame: int
    track_ids: List[int]
    frame_count: int
    source_segment_ids: List[str]
    source_segment_types: List[str]


class HumanStage1State:
    def __init__(
        self,
        batch_dir: Path,
        static_dir: Path,
        seed: int,
        reset_storage: bool,
    ) -> None:
        self.batch_dir = batch_dir.resolve()
        self.static_dir = resolve_repo_path(static_dir)
        self.seed = int(seed)
        self.reset_storage = bool(reset_storage)

        self.stage1_prep_dir = self.batch_dir / "human_stage_1_prep"
        self.stage1_dir = self.batch_dir / "human_stage_1"
        self.raw_dir = self.stage1_dir / "coarse_labels_raw"
        self.export_dir = self.stage1_dir / "coarse_labels_export"
        self.assignment_log_path = self.stage1_dir / "assignment_log.csv"
        self.db_path = self.stage1_dir / "ui_human_stage_1.sqlite3"
        self.manifest_path = self.batch_dir / "manifests" / "annotation_tasks.csv"

        self.video_paths: Dict[str, Path] = {}
        self.timestamp_paths: Dict[str, Path] = {}
        self.timestamp_lookup: Dict[Tuple[str, int], float] = {}
        self.ai_boxes: Dict[Tuple[str, int], List[Dict[str, Any]]] = {}
        self.segment_pool: List[SegmentRecord] = []
        self.segment_lookup: Dict[str, SegmentRecord] = {}
        self.reader: VideoFrameReader | None = None

    def initialize(self) -> None:
        self.stage1_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        if self.reset_storage:
            if self.db_path.exists():
                self.db_path.unlink()
            if self.assignment_log_path.exists():
                self.assignment_log_path.unlink()
        self.video_paths, self.timestamp_paths = self._load_manifest_assets()
        self.timestamp_lookup = self._load_frame_timestamps()
        self.ai_boxes = self._load_ai_boxes()
        self.segment_pool = self._load_segment_pool()
        self.segment_lookup = {segment.segment_id: segment for segment in self.segment_pool}
        self._init_database()
        self._init_assignment_log()
        self.reader = VideoFrameReader(self.video_paths)

    def close(self) -> None:
        if self.reader is not None:
            self.reader.close()
            self.reader = None

    def assign_next_segment(self, annotator_id: str) -> Dict[str, Any]:
        completed_segment_ids = self._completed_segment_ids_for_annotator(annotator_id)
        for segment in self.segment_pool:
            if segment.segment_id not in completed_segment_ids:
                payload = self._segment_payload(segment)
                self._append_assignment_log(annotator_id, payload["segment"]["segment_id"])
                return payload
        raise ValueError("no stage-1 segments remaining")

    def segment_detail(self, segment_id: str) -> Dict[str, Any]:
        segment = self.segment_lookup.get(segment_id)
        if segment is None:
            raise ValueError("segment not found")
        return self._segment_payload(segment)

    def submit_segment(
        self,
        annotator_id: str,
        segment_id: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        segment = self.segment_lookup.get(segment_id)
        if segment is None:
            raise ValueError("segment not found")
        if str(payload.get("segment_id", "")).strip() != segment.segment_id:
            raise ValueError("segment_id mismatch")
        if str(payload.get("video_stem", "")).strip() != segment.video_stem:
            raise ValueError("video_stem mismatch")
        if int(payload.get("frame_index", 0)) != segment.representative_frame:
            raise ValueError("frame_index must target the representative frame")

        slot_decisions = self._validate_slot_decisions(
            video_stem=segment.video_stem,
            frame_index=segment.representative_frame,
            slot_decisions=payload.get("slot_decisions"),
        )
        record = {
            "annotation_id": f"stage1_{uuid.uuid4().hex[:12]}",
            "segment_id": segment.segment_id,
            "segment_type": segment.segment_type,
            "video_stem": segment.video_stem,
            "frame_index": segment.representative_frame,
            "annotator_id": annotator_id,
            "submitted_at": _now_iso(),
            "slot_decisions_json": json.dumps(slot_decisions, ensure_ascii=False),
        }
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO coarse_labels (
                    annotation_id,
                    segment_id,
                    segment_type,
                    video_stem,
                    frame_index,
                    annotator_id,
                    submitted_at,
                    slot_decisions_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["annotation_id"],
                    record["segment_id"],
                    record["segment_type"],
                    record["video_stem"],
                    record["frame_index"],
                    record["annotator_id"],
                    record["submitted_at"],
                    record["slot_decisions_json"],
                ),
            )
            conn.commit()
        finally:
            conn.close()

        (self.raw_dir / f"{record['annotation_id']}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return {
            "annotation_id": record["annotation_id"],
            "segment_id": segment.segment_id,
            "frame_index": segment.representative_frame,
            "submitted_slot_count": len(slot_decisions),
        }

    def _segment_payload(self, segment: SegmentRecord) -> Dict[str, Any]:
        frame_index = segment.representative_frame
        return {
            "segment": {
                "segment_id": segment.segment_id,
                "video_stem": segment.video_stem,
                "segment_type": segment.segment_type,
                "start_frame": segment.start_frame,
                "end_frame": segment.end_frame,
                "representative_frame": segment.representative_frame,
                "track_ids": segment.track_ids,
                "frame_count": segment.frame_count,
                "source_segment_ids": segment.source_segment_ids,
                "source_segment_types": segment.source_segment_types,
            },
            "frame": {
                "video_stem": segment.video_stem,
                "frame_index": frame_index,
                "timestamp_ms": self.timestamp_lookup.get((segment.video_stem, frame_index), 0.0),
                "ai_boxes": self.ai_boxes.get((segment.video_stem, frame_index), []),
                "image_url": f"/api/frame_jpeg?video_stem={segment.video_stem}&frame_index={frame_index}",
            },
            "slot_names": SLOT_NAMES,
            "allowed_decisions": ALLOWED_DECISIONS,
            "manual_draw_enabled": False,
        }

    def _validate_slot_decisions(
        self,
        video_stem: str,
        frame_index: int,
        slot_decisions: Any,
    ) -> List[Dict[str, str]]:
        if not isinstance(slot_decisions, list):
            raise ValueError("slot_decisions must be a list")
        visible_track_ids = {
            str(item["track_id"]) for item in self.ai_boxes.get((video_stem, frame_index), [])
        }
        seen_slots: set[str] = set()
        used_tracks: set[str] = set()
        validated: List[Dict[str, str]] = []
        for item in slot_decisions:
            if not isinstance(item, dict):
                raise ValueError("slot decision must be an object")
            slot = str(item.get("slot", "")).strip()
            decision_type = str(item.get("decision_type", "")).strip()
            ai_track_id = str(item.get("ai_track_id", "") or "").strip()
            if slot not in SLOT_NAMES:
                raise ValueError("invalid slot")
            if slot in seen_slots:
                raise ValueError("duplicate slot decision")
            if decision_type not in ALLOWED_DECISIONS:
                raise ValueError("invalid decision_type")
            if decision_type == "ai_match":
                if not ai_track_id:
                    raise ValueError("ai_match requires ai_track_id")
                if ai_track_id not in visible_track_ids:
                    raise ValueError("ai_match must reference a visible AI track")
                if ai_track_id in used_tracks:
                    raise ValueError("duplicate AI track assignment")
                used_tracks.add(ai_track_id)
            else:
                if ai_track_id:
                    raise ValueError("non-ai decisions must not include ai_track_id")
            seen_slots.add(slot)
            validated.append(
                {
                    "slot": slot,
                    "decision_type": decision_type,
                    "ai_track_id": ai_track_id,
                }
            )
        return validated

    def _completed_segment_ids_for_annotator(self, annotator_id: str) -> set[str]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT segment_id FROM coarse_labels WHERE annotator_id=?",
                (annotator_id,),
            ).fetchall()
        finally:
            conn.close()
        return {str(row[0]) for row in rows}

    def _load_manifest_assets(self) -> Tuple[Dict[str, Path], Dict[str, Path]]:
        video_paths: Dict[str, Path] = {}
        timestamp_paths: Dict[str, Path] = {}
        with self.manifest_path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                video_stem = str(row.get("video_stem", "")).strip()
                if not video_stem:
                    continue
                video_paths[video_stem] = Path(str(row.get("video_path", "")).strip())
                timestamp_paths[video_stem] = Path(str(row.get("timestamp_path", "")).strip())
        return video_paths, timestamp_paths

    def _load_ai_boxes(self) -> Dict[Tuple[str, int], List[Dict[str, Any]]]:
        ai_boxes: Dict[Tuple[str, int], List[Dict[str, Any]]] = {}
        for pseudo_path in sorted((self.batch_dir / "pseudo_labels").glob("*.auto.csv")):
            detections = common.load_detections(pseudo_path)
            for frame_index, items in common.group_by_frame(detections).items():
                ai_boxes[(items[0].video_stem, frame_index)] = [
                    {
                        "track_id": int(item.track_id),
                        "bbox_x": float(item.bbox_x),
                        "bbox_y": float(item.bbox_y),
                        "bbox_w": float(item.bbox_w),
                        "bbox_h": float(item.bbox_h),
                        "score": float(item.score),
                    }
                    for item in items
                ]
        return ai_boxes

    def _load_frame_timestamps(self) -> Dict[Tuple[str, int], float]:
        timestamp_lookup: Dict[Tuple[str, int], float] = {}
        for video_stem, csv_path in self.timestamp_paths.items():
            with csv_path.open("r", newline="", encoding="utf-8") as f:
                rows = csv.DictReader(f)
                for row in rows:
                    try:
                        timestamp_lookup[(video_stem, int(row["frame_index"]))] = float(row["timestamp_ms"])
                    except Exception:
                        continue
        return timestamp_lookup

    def _load_segment_pool(self) -> List[SegmentRecord]:
        segments: List[SegmentRecord] = []
        for path in sorted(self.stage1_prep_dir.glob("*.segments.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            for item in payload.get("segments", []):
                segments.append(
                    SegmentRecord(
                        segment_id=str(item["segment_id"]),
                        video_stem=str(item["video_stem"]),
                        segment_type=str(item["segment_type"]),
                        start_frame=int(item["start_frame"]),
                        end_frame=int(item["end_frame"]),
                        representative_frame=int(item["representative_frame"]),
                        track_ids=[int(track_id) for track_id in item.get("track_ids", [])],
                        frame_count=int(item["frame_count"]),
                        source_segment_ids=[str(value) for value in item.get("source_segment_ids", [])],
                        source_segment_types=[str(value) for value in item.get("source_segment_types", [])],
                    )
                )
        segments.sort(key=lambda item: (item.video_stem, item.start_frame, item.end_frame, item.segment_id))
        return segments

    def _init_database(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS coarse_labels (
                    annotation_id TEXT PRIMARY KEY,
                    segment_id TEXT NOT NULL,
                    segment_type TEXT NOT NULL,
                    video_stem TEXT NOT NULL,
                    frame_index INTEGER NOT NULL,
                    annotator_id TEXT NOT NULL,
                    submitted_at TEXT NOT NULL,
                    slot_decisions_json TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def _init_assignment_log(self) -> None:
        if self.assignment_log_path.exists():
            return
        with self.assignment_log_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["assigned_at", "annotator_id", "segment_id"])

    def _append_assignment_log(self, annotator_id: str, segment_id: str) -> None:
        with self.assignment_log_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([_now_iso(), annotator_id, segment_id])

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def read_frame_jpeg(self, video_stem: str, frame_index: int) -> bytes:
        if self.reader is None:
            raise ValueError("frame reader not initialized")
        return self.reader.read_jpeg(video_stem, frame_index)


class HumanStage1RequestHandler(BaseHTTPRequestHandler):
    server: "HumanStage1HTTPServer"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/next_segment":
            self._handle_next_segment(parsed)
            return
        if parsed.path == "/api/segment_detail":
            self._handle_segment_detail(parsed)
            return
        if parsed.path == "/api/frame_jpeg":
            self._handle_frame_jpeg(parsed)
            return
        self._serve_static(parsed.path)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/submit_segment":
            self._handle_submit_segment()
            return
        self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def _handle_next_segment(self, parsed) -> None:
        query = parse_qs(parsed.query)
        annotator_id = str(query.get("annotator_id", ["annotator_demo"])[0]).strip() or "annotator_demo"
        try:
            payload = self.server.state.assign_next_segment(annotator_id)
            self._send_json(payload)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def _handle_segment_detail(self, parsed) -> None:
        query = parse_qs(parsed.query)
        segment_id = str(query.get("segment_id", [""])[0]).strip()
        try:
            payload = self.server.state.segment_detail(segment_id)
            self._send_json(payload)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def _handle_submit_segment(self) -> None:
        try:
            body = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
            payload = json.loads(body.decode("utf-8"))
            annotator_id = str(payload.get("annotator_id", "")).strip() or "annotator_demo"
            result = self.server.state.submit_segment(
                annotator_id=annotator_id,
                segment_id=str(payload.get("segment_id", "")).strip(),
                payload=payload,
            )
            self._send_json(result)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def _handle_frame_jpeg(self, parsed) -> None:
        query = parse_qs(parsed.query)
        video_stem = str(query.get("video_stem", [""])[0]).strip()
        frame_index = int(query.get("frame_index", ["0"])[0])
        try:
            data = self.server.state.read_frame_jpeg(video_stem, frame_index)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def _serve_static(self, request_path: str) -> None:
        relative = request_path.lstrip("/") or "index.html"
        path = (self.server.static_dir / relative).resolve()
        if not path.exists() or self.server.static_dir not in path.parents and path != self.server.static_dir / "index.html":
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
            return
        content_type = "text/html; charset=utf-8"
        if path.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"
        elif path.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: Dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class HumanStage1HTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: Tuple[str, int], state: HumanStage1State) -> None:
        self.state = state
        self.static_dir = state.static_dir
        super().__init__(server_address, HumanStage1RequestHandler)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve human stage 1 coarse-labeling UI")
    parser.add_argument("--batch-dir", type=Path, required=True)
    parser.add_argument(
        "--static-dir",
        type=Path,
        default=Path("codes/application/ui_human_stage_1_web"),
    )
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--reset-storage", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10089)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    state = HumanStage1State(
        batch_dir=args.batch_dir,
        static_dir=args.static_dir,
        seed=args.seed,
        reset_storage=args.reset_storage,
    )
    state.initialize()
    server = HumanStage1HTTPServer((args.host, args.port), state)
    try:
        print(
            json.dumps(
                {
                    "batch_dir": str(args.batch_dir.resolve()),
                    "segment_count": len(state.segment_pool),
                    "db_path": str(state.db_path),
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
        state.close()


if __name__ == "__main__":
    main()
