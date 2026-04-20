#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import parse_qs, urlparse

from application.support.video_frame_reader import VideoFrameReader
from process.shared import segment_prep_common as common


REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SLOT_CONFIG = [
    ("p1", "P1(赵宇轩)"),
    ("p2", "P2(张络屹)"),
    ("p3", "P3(Alison)"),
    ("p4", "P4(刘浩贤)"),
    ("p5", "P5(何炳毅)"),
    ("p6", "P6(李泓睿)"),
    ("p7", "P7(梁芳舟)"),
    ("p8", "P8(谢灵韵)"),
]
SLOT_NAMES = [slot for slot, _display_name in SLOT_CONFIG]
SLOT_DISPLAY_NAMES = {slot: display_name for slot, display_name in SLOT_CONFIG}
ALLOWED_DECISIONS = ["ai_match", "absent", "needs_manual"]
AI_SELECTION_SOURCES = {"recommended_confirmed", "manual_selected"}
TARGET_ANNOTATOR_FRAMES = 2600


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="milliseconds")


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def slot_display_name(slot: str) -> str:
    normalized = str(slot).strip().lower()
    return SLOT_DISPLAY_NAMES.get(normalized, normalized.upper())


def slot_summary_from_json(slot_decisions_json: str) -> str:
    try:
        decisions = json.loads(slot_decisions_json)
    except Exception:
        return ""
    if not isinstance(decisions, list):
        return ""
    parts: List[str] = []
    for item in decisions:
        if not isinstance(item, dict):
            continue
        slot = str(item.get("slot", "")).strip().lower()
        decision_type = str(item.get("decision_type", "")).strip()
        ai_track_id = str(item.get("ai_track_id", "") or "").strip()
        selection_source = str(item.get("selection_source", "") or "").strip()
        if not slot or not decision_type:
            continue
        piece = f"{slot_display_name(slot)}:{decision_type}"
        if ai_track_id:
            piece += f"({ai_track_id}"
            if selection_source:
                piece += f"|{selection_source}"
            piece += ")"
        parts.append(piece)
    return " | ".join(parts)


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


@dataclass(frozen=True)
class QueueRecord:
    queue_id: int
    segment_id: str
    pass_index: int
    queue_order: int
    status: str
    annotation_id: str
    completed_by: str
    completed_at: str


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
        self.queue_lookup: Dict[int, QueueRecord] = {}
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
        self._init_assignment_queue()
        self.queue_lookup = self._load_queue_lookup()
        self.reader = VideoFrameReader(self.video_paths)

    def close(self) -> None:
        if self.reader is not None:
            self.reader.close()
            self.reader = None

    def assign_next_segment(self, annotator_id: str) -> Dict[str, Any]:
        queue_item = self._next_pending_queue_item()
        if queue_item is None:
            raise ValueError("no stage-1 segments remaining")
        segment = self.segment_lookup.get(queue_item.segment_id)
        if segment is None:
            raise ValueError("segment not found")
        payload = self._segment_payload(segment, queue_item=queue_item)
        payload["annotator_progress"] = self._annotator_progress(annotator_id)
        self._append_assignment_log(annotator_id, payload["segment"]["segment_id"])
        return payload

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
        try:
            queue_id = int(payload.get("queue_id", 0))
        except Exception as exc:
            raise ValueError("queue_id is required") from exc
        queue_item = self._queue_item_by_id(queue_id)
        if queue_item is None:
            raise ValueError("queue_id not found")
        if queue_item.segment_id != segment.segment_id:
            raise ValueError("queue_id does not match segment_id")

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
            cursor = conn.execute(
                """
                UPDATE stage1_assignment_queue
                SET status='completed', annotation_id=?, completed_by=?, completed_at=?
                WHERE queue_id=? AND status='pending'
                """,
                (record["annotation_id"], annotator_id, record["submitted_at"], queue_id),
            )
            conn.commit()
        finally:
            conn.close()
        queue_completed = cursor.rowcount > 0
        if queue_completed:
            self.queue_lookup[queue_id] = QueueRecord(
                queue_id=queue_item.queue_id,
                segment_id=queue_item.segment_id,
                pass_index=queue_item.pass_index,
                queue_order=queue_item.queue_order,
                status="completed",
                annotation_id=record["annotation_id"],
                completed_by=annotator_id,
                completed_at=record["submitted_at"],
            )

        (self.raw_dir / f"{record['annotation_id']}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return {
            "annotation_id": record["annotation_id"],
            "segment_id": segment.segment_id,
            "frame_index": segment.representative_frame,
            "submitted_slot_count": len(slot_decisions),
            "queue_id": queue_id,
            "queue_completed": queue_completed,
        }

    def list_annotations_for_annotator(self, annotator_id: str) -> Dict[str, Any]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT
                    annotation_id,
                    segment_id,
                    segment_type,
                    video_stem,
                    frame_index,
                    submitted_at,
                    slot_decisions_json
                FROM coarse_labels
                WHERE annotator_id=?
                ORDER BY submitted_at DESC, annotation_id DESC
                """,
                (annotator_id,),
            ).fetchall()
        finally:
            conn.close()
        return {
            "annotations": [
                {
                    "annotation_id": str(row["annotation_id"]),
                    "segment_id": str(row["segment_id"]),
                    "segment_type": str(row["segment_type"]),
                    "video_stem": str(row["video_stem"]),
                    "frame_index": int(row["frame_index"]),
                    "submitted_at": str(row["submitted_at"]),
                    "slot_decisions_json": str(row["slot_decisions_json"]),
                    "slots_summary": slot_summary_from_json(str(row["slot_decisions_json"])),
                }
                for row in rows
            ],
            "annotator_progress": self._annotator_progress(annotator_id),
        }

    def annotation_detail(self, annotator_id: str, annotation_id: str) -> Dict[str, Any]:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT *
                FROM coarse_labels
                WHERE annotation_id=? AND annotator_id=?
                """,
                (annotation_id, annotator_id),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise ValueError("annotation not found for annotator")
        segment = self.segment_lookup.get(str(row["segment_id"]))
        if segment is None:
            raise ValueError("segment not found")
        payload = self._segment_payload(segment)
        payload["annotation"] = {
            "annotation_id": str(row["annotation_id"]),
            "segment_id": str(row["segment_id"]),
            "segment_type": str(row["segment_type"]),
            "video_stem": str(row["video_stem"]),
            "frame_index": int(row["frame_index"]),
            "annotator_id": str(row["annotator_id"]),
            "submitted_at": str(row["submitted_at"]),
            "slot_decisions": json.loads(str(row["slot_decisions_json"])),
        }
        payload["annotator_progress"] = self._annotator_progress(annotator_id)
        return payload

    def update_annotation(self, annotator_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        annotation_id = str(payload.get("annotation_id", "")).strip()
        if not annotation_id:
            raise ValueError("annotation_id is required")
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT segment_id, segment_type, video_stem, frame_index
                FROM coarse_labels
                WHERE annotation_id=? AND annotator_id=?
                """,
                (annotation_id, annotator_id),
            ).fetchone()
            if row is None:
                raise ValueError("annotation not found for annotator")
        finally:
            conn.close()
        segment_id = str(row["segment_id"])
        segment = self.segment_lookup.get(segment_id)
        if segment is None:
            raise ValueError("segment not found")
        if str(payload.get("video_stem", "")).strip() != segment.video_stem:
            raise ValueError("video_stem mismatch")
        if int(payload.get("frame_index", 0)) != segment.representative_frame:
            raise ValueError("frame_index mismatch")
        slot_decisions = self._validate_slot_decisions(
            video_stem=segment.video_stem,
            frame_index=segment.representative_frame,
            slot_decisions=payload.get("slot_decisions"),
        )
        serialized = json.dumps(slot_decisions, ensure_ascii=False)
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE coarse_labels
                SET slot_decisions_json=?, submitted_at=?
                WHERE annotation_id=? AND annotator_id=?
                """,
                (serialized, _now_iso(), annotation_id, annotator_id),
            )
            conn.commit()
        finally:
            conn.close()
        raw_path = self.raw_dir / f"{annotation_id}.json"
        if raw_path.exists():
            raw_payload = json.loads(raw_path.read_text(encoding="utf-8"))
            raw_payload["slot_decisions_json"] = serialized
            raw_payload["submitted_at"] = _now_iso()
            raw_path.write_text(json.dumps(raw_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"annotation_id": annotation_id, "updated_slot_count": len(slot_decisions)}

    def _segment_payload(self, segment: SegmentRecord, queue_item: QueueRecord | None = None) -> Dict[str, Any]:
        frame_index = segment.representative_frame
        payload = {
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
                "recommendations": self._build_recommendations(
                    video_stem=segment.video_stem,
                    ai_boxes=self.ai_boxes.get((segment.video_stem, frame_index), []),
                ),
            },
            "slot_names": SLOT_NAMES,
            "slot_display_names": SLOT_DISPLAY_NAMES,
            "allowed_decisions": ALLOWED_DECISIONS,
            "manual_draw_enabled": False,
        }
        if queue_item is not None:
            payload["queue"] = {
                "queue_id": queue_item.queue_id,
                "pass_index": queue_item.pass_index,
                "queue_order": queue_item.queue_order,
                "status": queue_item.status,
            }
        return payload

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
            selection_source = str(item.get("selection_source", "") or "").strip()
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
                if selection_source and selection_source not in AI_SELECTION_SOURCES:
                    raise ValueError("invalid ai selection_source")
                if not selection_source:
                    selection_source = "manual_selected"
                used_tracks.add(ai_track_id)
            else:
                if ai_track_id:
                    raise ValueError("non-ai decisions must not include ai_track_id")
                selection_source = decision_type
            seen_slots.add(slot)
            validated.append(
                {
                    "slot": slot,
                    "decision_type": decision_type,
                    "ai_track_id": ai_track_id,
                    "selection_source": selection_source,
                }
            )
        return validated

    def _queue_record_from_row(self, row: sqlite3.Row | tuple[Any, ...] | None) -> QueueRecord | None:
        if row is None:
            return None
        return QueueRecord(
            queue_id=int(row["queue_id"] if isinstance(row, sqlite3.Row) else row[0]),
            segment_id=str(row["segment_id"] if isinstance(row, sqlite3.Row) else row[1]),
            pass_index=int(row["pass_index"] if isinstance(row, sqlite3.Row) else row[2]),
            queue_order=int(row["queue_order"] if isinstance(row, sqlite3.Row) else row[3]),
            status=str(row["status"] if isinstance(row, sqlite3.Row) else row[4]),
            annotation_id=str(row["annotation_id"] if isinstance(row, sqlite3.Row) else row[5]),
            completed_by=str(row["completed_by"] if isinstance(row, sqlite3.Row) else row[6]),
            completed_at=str(row["completed_at"] if isinstance(row, sqlite3.Row) else row[7]),
        )

    def _next_pending_queue_item(self) -> QueueRecord | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT queue_id, segment_id, pass_index, queue_order, status, annotation_id, completed_by, completed_at
                FROM stage1_assignment_queue
                WHERE status='pending'
                ORDER BY queue_order ASC
                LIMIT 1
                """
            ).fetchone()
        finally:
            conn.close()
        return self._queue_record_from_row(row)

    def _annotator_progress(self, annotator_id: str) -> Dict[str, Any]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT segment_id
                FROM coarse_labels
                WHERE annotator_id=?
                """,
                (annotator_id,),
            ).fetchall()
        finally:
            conn.close()

        completed_frames = 0
        for row in rows:
            segment = self.segment_lookup.get(str(row["segment_id"]))
            if segment is None:
                continue
            completed_frames += int(segment.frame_count)

        return {
            "completed_frames": completed_frames,
            "target_frames": TARGET_ANNOTATOR_FRAMES,
            "ratio": completed_frames / TARGET_ANNOTATOR_FRAMES if TARGET_ANNOTATOR_FRAMES > 0 else 0.0,
        }

    def _queue_item_by_id(self, queue_id: int) -> QueueRecord | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT queue_id, segment_id, pass_index, queue_order, status, annotation_id, completed_by, completed_at
                FROM stage1_assignment_queue
                WHERE queue_id=?
                """,
                (queue_id,),
            ).fetchone()
        finally:
            conn.close()
        return self._queue_record_from_row(row)

    def _load_queue_lookup(self) -> Dict[int, QueueRecord]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT queue_id, segment_id, pass_index, queue_order, status, annotation_id, completed_by, completed_at
                FROM stage1_assignment_queue
                ORDER BY queue_order ASC
                """
            ).fetchall()
        finally:
            conn.close()
        records = [self._queue_record_from_row(row) for row in rows]
        return {record.queue_id: record for record in records if record is not None}

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

    def _build_recommendations(
        self,
        video_stem: str,
        ai_boxes: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not ai_boxes:
            return []

        visible_track_ids = sorted({str(int(float(box["track_id"]))) for box in ai_boxes}, key=lambda item: int(item))
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT slot_decisions_json
                FROM coarse_labels
                WHERE video_stem=?
                ORDER BY submitted_at ASC, annotation_id ASC
                """,
                (video_stem,),
            ).fetchall()
        finally:
            conn.close()
        if not rows:
            return []

        counts_by_slot: Dict[str, Counter[str]] = {slot: Counter() for slot in SLOT_NAMES}
        for row in rows:
            try:
                decisions = json.loads(str(row["slot_decisions_json"]))
            except Exception:
                continue
            if not isinstance(decisions, list):
                continue
            for item in decisions:
                if not isinstance(item, dict):
                    continue
                slot = str(item.get("slot", "")).strip().lower()
                if slot not in counts_by_slot:
                    continue
                if str(item.get("decision_type", "")).strip() != "ai_match":
                    continue
                ai_track_id = str(item.get("ai_track_id", "") or "").strip()
                if not ai_track_id:
                    continue
                counts_by_slot[slot][ai_track_id] += 1

        slot_rank = {slot: idx for idx, slot in enumerate(SLOT_NAMES)}
        ranked_choices: Dict[str, List[Tuple[str, int]]] = {}
        for slot in SLOT_NAMES:
            visible_counts = [
                (track_id, counts_by_slot[slot][track_id])
                for track_id in visible_track_ids
                if counts_by_slot[slot][track_id] > 0
            ]
            if not visible_counts:
                continue
            visible_counts.sort(key=lambda item: (-item[1], int(item[0])))
            ranked_choices[slot] = visible_counts

        ordered_slots = sorted(
            ranked_choices,
            key=lambda slot: (-ranked_choices[slot][0][1], slot_rank[slot]),
        )
        recommendations: List[Dict[str, Any]] = []
        used_tracks: set[str] = set()
        for slot in ordered_slots:
            for track_id, vote_count in ranked_choices[slot]:
                if track_id in used_tracks:
                    continue
                used_tracks.add(track_id)
                total_votes = sum(counts_by_slot[slot].values())
                recommendations.append(
                    {
                        "slot": slot,
                        "ai_track_id": track_id,
                        "vote_count": vote_count,
                        "confidence": round(vote_count / total_votes, 3) if total_votes > 0 else 0.0,
                        "reason": "history_majority",
                    }
                )
                break
        return recommendations

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

    def _init_assignment_queue(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stage1_assignment_queue (
                    queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    segment_id TEXT NOT NULL,
                    video_stem TEXT NOT NULL,
                    pass_index INTEGER NOT NULL,
                    queue_order INTEGER NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    annotation_id TEXT NOT NULL DEFAULT '',
                    completed_by TEXT NOT NULL DEFAULT '',
                    completed_at TEXT NOT NULL DEFAULT ''
                )
                """
            )
            queue_count = int(
                conn.execute("SELECT COUNT(*) FROM stage1_assignment_queue").fetchone()[0]
            )
            if queue_count == 0:
                queue_rows: List[tuple[str, str, int, int, str]] = []
                queue_order = 1
                for pass_index in (1, 2):
                    for segment in self.segment_pool:
                        queue_rows.append(
                            (
                                segment.segment_id,
                                segment.video_stem,
                                pass_index,
                                queue_order,
                                "pending",
                            )
                        )
                        queue_order += 1
                conn.executemany(
                    """
                    INSERT INTO stage1_assignment_queue (
                        segment_id,
                        video_stem,
                        pass_index,
                        queue_order,
                        status
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    queue_rows,
                )
                historical_rows = conn.execute(
                    """
                    SELECT annotation_id, segment_id, annotator_id, submitted_at
                    FROM coarse_labels
                    ORDER BY submitted_at ASC, annotation_id ASC
                    """
                ).fetchall()
                for row in historical_rows:
                    pending_queue_row = conn.execute(
                        """
                        SELECT queue_id
                        FROM stage1_assignment_queue
                        WHERE segment_id=? AND status='pending'
                        ORDER BY queue_order ASC
                        LIMIT 1
                        """,
                        (str(row["segment_id"]),),
                    ).fetchone()
                    if pending_queue_row is None:
                        continue
                    conn.execute(
                        """
                        UPDATE stage1_assignment_queue
                        SET status='completed', annotation_id=?, completed_by=?, completed_at=?
                        WHERE queue_id=?
                        """,
                        (
                            str(row["annotation_id"]),
                            str(row["annotator_id"]),
                            str(row["submitted_at"]),
                            int(pending_queue_row["queue_id"]),
                        ),
                    )
            conn.commit()
        finally:
            conn.close()

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
        if parsed.path == "/api/admin/overview":
            self._handle_admin_overview()
            return
        if parsed.path == "/api/admin/annotators":
            self._handle_admin_annotators()
            return
        if parsed.path == "/api/admin/segments":
            self._handle_admin_segments()
            return
        if parsed.path == "/api/admin/segment_detail":
            self._handle_admin_segment_detail(parsed)
            return
        if parsed.path == "/api/my_annotations":
            self._handle_my_annotations(parsed)
            return
        if parsed.path == "/api/annotation_detail":
            self._handle_annotation_detail(parsed)
            return
        if parsed.path == "/api/segment_detail":
            self._handle_segment_detail(parsed)
            return
        if parsed.path == "/api/frame_jpeg":
            self._handle_frame_jpeg(parsed)
            return
        if parsed.path in {"/admin", "/admin/"}:
            self._serve_admin_static("index.html", "text/html; charset=utf-8")
            return
        if parsed.path == "/admin/styles.css":
            self._serve_admin_static("styles.css", "text/css; charset=utf-8")
            return
        if parsed.path == "/admin/app.js":
            self._serve_admin_static("app.js", "application/javascript; charset=utf-8")
            return
        self._serve_static(parsed.path)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/submit_segment":
            self._handle_submit_segment()
            return
        if parsed.path == "/api/update_annotation":
            self._handle_update_annotation()
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

    def _handle_my_annotations(self, parsed) -> None:
        query = parse_qs(parsed.query)
        annotator_id = str(query.get("annotator_id", ["annotator_demo"])[0]).strip() or "annotator_demo"
        try:
            annotations = self.server.state.list_annotations_for_annotator(annotator_id)
            self._send_json({"annotations": annotations})
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def _handle_annotation_detail(self, parsed) -> None:
        query = parse_qs(parsed.query)
        annotator_id = str(query.get("annotator_id", ["annotator_demo"])[0]).strip() or "annotator_demo"
        annotation_id = str(query.get("annotation_id", [""])[0]).strip()
        try:
            payload = self.server.state.annotation_detail(annotator_id, annotation_id)
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

    def _handle_update_annotation(self) -> None:
        try:
            body = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
            payload = json.loads(body.decode("utf-8"))
            annotator_id = str(payload.get("annotator_id", "")).strip() or "annotator_demo"
            result = self.server.state.update_annotation(annotator_id=annotator_id, payload=payload)
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

    def _handle_admin_overview(self) -> None:
        try:
            data = self.server.admin_state.overview()
            self._send_json({"ok": True, "overview": data})
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def _handle_admin_annotators(self) -> None:
        try:
            data = self.server.admin_state.annotator_stats()
            self._send_json({"ok": True, **data})
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def _handle_admin_segments(self) -> None:
        try:
            rows = self.server.admin_state.segments()
            self._send_json({"ok": True, "segments": rows})
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def _handle_admin_segment_detail(self, parsed) -> None:
        query = parse_qs(parsed.query)
        segment_id = str(query.get("segment_id", [""])[0]).strip()
        try:
            detail = self.server.admin_state.segment_detail(segment_id)
            self._send_json({"ok": True, "detail": detail})
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

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

    def _serve_admin_static(self, filename: str, content_type: str) -> None:
        path = self.server.admin_static_dir / filename
        if not path.exists():
            self._send_json({"ok": False, "error": f"missing admin static: {filename}"}, status=HTTPStatus.NOT_FOUND)
            return
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
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
    def __init__(self, server_address: Tuple[str, int], state: HumanStage1State, admin_state) -> None:
        self.state = state
        self.static_dir = state.static_dir
        self.admin_state = admin_state
        self.admin_static_dir = admin_state.static_dir
        super().__init__(server_address, HumanStage1RequestHandler)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve human stage 1 coarse-labeling UI")
    parser.add_argument("--batch-dir", type=Path, required=True)
    parser.add_argument(
        "--static-dir",
        type=Path,
        default=Path("codes/application/step3_human_stage_1/web"),
    )
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--reset-storage", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10089)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    from application.step3_human_stage_1.ui_human_stage_1_admin_server import HumanStage1AdminState

    state = HumanStage1State(
        batch_dir=args.batch_dir,
        static_dir=args.static_dir,
        seed=args.seed,
        reset_storage=args.reset_storage,
    )
    state.initialize()
    admin_state = HumanStage1AdminState(
        batch_dir=args.batch_dir,
        static_dir=Path("codes/application/step3_human_stage_1/admin_web"),
    )
    admin_state.initialize()
    server = HumanStage1HTTPServer((args.host, args.port), state, admin_state)
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
