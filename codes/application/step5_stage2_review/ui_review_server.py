#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import threading
import time
import uuid
from collections import Counter, OrderedDict
from dataclasses import dataclass, field, replace
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import parse_qs, urlparse

import cv2

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

DEFAULT_TARGET_VIDEO_STEMS = [
    "20260211_171423",
    "20260211_171724",
    "20260211_172257",
    "20260211_172522",
]
SLOT_NAMES = [f"p{i}" for i in range(1, 8)]
VALID_SLOT_SOURCES = {"ai", "manual_draw", "manual_param", "absent", "occluded", "outside"}

FRAME_POOL_COLUMNS = ["video_stem", "frame_index", "timestamp_ms"]
COUNT_COLUMNS = ["video_stem", "frame_index", "timestamp_ms", "annotation_count"]
REVIEWED_COLUMNS = [
    "annotation_id",
    "video_stem",
    "frame_index",
    "timestamp_ms",
    "annotator_id",
    "submitted_at",
    "slots_json",
]


def _now_human() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="milliseconds")


def _safe_float(value: Any) -> float:
    return float(f"{float(value):.3f}")


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def empty_slot_record(slot_name: str) -> Dict[str, Any]:
    return {
        "slot": slot_name,
        "bbox_x": 0.0,
        "bbox_y": 0.0,
        "bbox_w": 0.0,
        "bbox_h": 0.0,
        "source": "not_set",
        "ai_track_id": "",
    }


def slot_summary_from_json(slots_json: str) -> str:
    try:
        slots = json.loads(slots_json)
    except Exception:
        return ""
    if not isinstance(slots, list):
        return ""
    parts: List[str] = []
    for item in slots:
        if not isinstance(item, dict):
            continue
        slot = str(item.get("slot", "")).strip()
        source = str(item.get("source", "")).strip()
        track = str(item.get("ai_track_id", "") or "").strip()
        if not slot:
            continue
        piece = f"{slot.upper()}:{source}"
        if track:
            piece += f"({track})"
        parts.append(piece)
    return " | ".join(parts)


@dataclass(frozen=True)
class FrameRecord:
    video_stem: str
    frame_index: int
    timestamp_ms: float


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
    anchor_candidates: List[int] = field(default_factory=list)
    repairability_score: float = 0.0
    fragmentation_score: int = 0
    expected_gain: int = 0
    trigger_reason: str = ""


class RunLogger:
    def __init__(self, run_log_path: Path, error_log_path: Path) -> None:
        self.run_log_path = run_log_path
        self.error_log_path = error_log_path
        self._lock = threading.Lock()
        self.run_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.error_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.run_log_path.touch(exist_ok=True)
        self.error_log_path.touch(exist_ok=True)

    def info(self, message: str) -> None:
        self._write("INFO", message)

    def error(self, message: str) -> None:
        self._write("ERROR", message, also_error=True)

    def _write(self, level: str, message: str, also_error: bool = False) -> None:
        line = f"[{_now_human()}] {level:<5} {message}\n"
        with self._lock:
            with self.run_log_path.open("a", encoding="utf-8") as f:
                f.write(line)
            if also_error:
                with self.error_log_path.open("a", encoding="utf-8") as f:
                    f.write(line)
        print(line, end="")


class VideoFrameReader:
    def __init__(self, video_paths: Dict[str, Path], jpeg_quality: int = 88) -> None:
        self._video_paths = video_paths
        self._captures: Dict[str, cv2.VideoCapture] = {}
        self._locks: Dict[str, threading.Lock] = {}
        self._meta: Dict[str, Tuple[int, int]] = {}
        self._jpeg_quality = int(max(10, min(100, jpeg_quality)))

    def get_dimensions(self, video_stem: str) -> Tuple[int, int]:
        self._ensure_open(video_stem)
        return self._meta[video_stem]

    def read_jpeg(self, video_stem: str, frame_index_1based: int) -> bytes:
        self._ensure_open(video_stem)
        cap = self._captures[video_stem]
        lock = self._locks[video_stem]
        with lock:
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_index_1based - 1))
            ok, frame = cap.read()
            if not ok or frame is None:
                raise ValueError(
                    f"failed to decode frame {frame_index_1based} from {video_stem}"
                )
            ok_encode, buf = cv2.imencode(
                ".jpg",
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality],
            )
            if not ok_encode:
                raise ValueError(
                    f"failed to encode frame {frame_index_1based} from {video_stem}"
                )
            return bytes(buf)

    def _ensure_open(self, video_stem: str) -> None:
        if video_stem in self._captures:
            return
        path = self._video_paths[video_stem]
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise ValueError(f"failed to open video: {path}")
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._captures[video_stem] = cap
        self._locks[video_stem] = threading.Lock()
        self._meta[video_stem] = (width, height)

    def close(self) -> None:
        for cap in self._captures.values():
            cap.release()
        self._captures.clear()
        self._locks.clear()
        self._meta.clear()


class AnnotationState:
    def __init__(
        self,
        batch_dir: Path,
        static_dir: Path,
        seed: int,
        reset_storage: bool,
        frame_cache_dir: Path | None,
        frame_cache_prewarm: bool,
        frame_cache_max: int,
        frame_cache_quality: int,
    ) -> None:
        self.batch_dir = batch_dir
        self.static_dir = static_dir
        self.ui_task_dir = self.batch_dir / "ui_tasks"
        self.reviewed_raw_dir = self.batch_dir / "reviewed_raw"
        self.reviewed_dir = self.batch_dir / "reviewed"
        self.logs_dir = self.batch_dir / "logs"
        self.manifest_path = self.batch_dir / "manifests" / "annotation_tasks.csv"
        self.frame_pool_path = self.ui_task_dir / "frame_pool.csv"
        self.count_path = self.ui_task_dir / "frame_annotation_counts.csv"
        self.db_path = self.ui_task_dir / "ui_review.sqlite3"

        self.logger = RunLogger(
            run_log_path=self.logs_dir / "run.log",
            error_log_path=self.logs_dir / "errors.log",
        )
        self._lock = threading.Lock()
        self.reset_storage = reset_storage
        self.frame_cache_dir = frame_cache_dir
        self.frame_cache_prewarm = frame_cache_prewarm
        self.frame_cache_quality = frame_cache_quality

        self.video_paths: Dict[str, Path] = {}
        self.timestamp_paths: Dict[str, Path] = {}
        self.video_stems: List[str] = []
        self.frame_pool: List[FrameRecord] = []
        self.frame_lookup: Dict[Tuple[str, int], FrameRecord] = {}
        self.ai_boxes: Dict[Tuple[str, int], List[Dict[str, float | int]]] = {}
        self.segment_pool: List[SegmentRecord] = []
        self.segment_lookup: Dict[str, SegmentRecord] = {}
        self.segment_frames: Dict[str, Dict[int, str]] = {}
        self.reader: VideoFrameReader | None = None
        self._frame_cache: OrderedDict[Tuple[str, int], bytes] = OrderedDict()
        self._frame_cache_lock = threading.Lock()
        self._frame_cache_max = int(max(0, frame_cache_max))
        self._dispatch_generation = 0
        self._segment_dispatch_index = 0

    def initialize(self) -> None:
        self.ui_task_dir.mkdir(parents=True, exist_ok=True)
        self.reviewed_raw_dir.mkdir(parents=True, exist_ok=True)
        self.reviewed_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        if self.reset_storage:
            self._reset_storage_artifacts()

        self.logger.info("UI review service init start")
        self.video_paths, self.timestamp_paths, self.video_stems = self._load_manifest_assets()
        self.frame_pool = self._build_frame_pool()
        self.frame_lookup = {(r.video_stem, r.frame_index): r for r in self.frame_pool}
        self.ai_boxes = self._load_ai_boxes()
        self.segment_pool = self._load_segment_pool()
        self.segment_lookup = {segment.segment_id: segment for segment in self.segment_pool}
        self.segment_frames = self._load_segment_frame_lookup()
        self._init_review_files()
        self._init_database()
        self._sync_counts_csv_from_db()
        self.reader = VideoFrameReader(self.video_paths, jpeg_quality=self.frame_cache_quality)
        self._dispatch_generation = 0
        self._segment_dispatch_index = 0
        if self.frame_cache_dir is not None:
            self.frame_cache_dir.mkdir(parents=True, exist_ok=True)
            if self.frame_cache_prewarm:
                thread = threading.Thread(target=self._prewarm_disk_cache, daemon=True)
                thread.start()
        self.logger.info(
            f"UI review service init done, total_frames={len(self.frame_pool)}, db={self.db_path}"
        )

    def close(self) -> None:
        if self.reader is not None:
            self.reader.close()

    def assign_next_segment(self, annotator_id: str) -> Dict[str, Any]:
        with self._lock:
            segment = self._pick_next_segment_unlocked(annotator_id=annotator_id)
            return self._segment_payload(segment)

    def submit_segment(
        self,
        annotator_id: str,
        segment_id: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        with self._lock:
            segment = self.segment_lookup.get(segment_id)
            if segment is None:
                raise ValueError("segment not found")

            fallback: Dict[str, Any] | None = None
            if segment.segment_type == "stable_segment":
                slots = self._validate_slots_payload(payload.get("slots"))
                resolved_slots = self._resolve_stable_segment_slots(
                    video_stem=segment.video_stem,
                    representative_frame=segment.representative_frame,
                    slots=slots,
                )
                frame_records = self._build_segment_frame_records(
                    annotator_id=annotator_id,
                    segment=segment,
                    slots_by_frame={
                        frame_index: self._expand_segment_slots_for_frame(
                            base_slots=resolved_slots,
                            video_stem=segment.video_stem,
                            representative_frame=segment.representative_frame,
                            frame_index=frame_index,
                        )
                        for frame_index in range(segment.start_frame, segment.end_frame + 1)
                    },
                )
            elif segment.segment_type == "non_simple_single_frame":
                record = self._validate_and_build_record(annotator_id, payload)
                if int(record["frame_index"]) != segment.representative_frame:
                    raise ValueError("non-simple segment submission must target representative frame")
                frame_records = [record]
            elif segment.segment_type == "repair_window":
                anchors = self._validate_repair_window_anchor_payload(segment, payload)
                slots_by_frame, fallback = self._build_repair_window_slots_by_frame(segment, anchors)
                if fallback is None and slots_by_frame is not None:
                    frame_records = self._build_segment_frame_records(
                        annotator_id=annotator_id,
                        segment=segment,
                        slots_by_frame=slots_by_frame,
                    )
                else:
                    frame_records = []
            else:
                raise ValueError(f"unsupported segment type: {segment.segment_type}")

            if fallback is not None:
                next_segment_payload = None
                suggested_anchor_frames = [int(v) for v in fallback.get("suggested_anchor_frames", [])]
                if suggested_anchor_frames:
                    merged_anchors = sorted({*segment.anchor_candidates, *suggested_anchor_frames})
                    next_anchor_index = merged_anchors.index(suggested_anchor_frames[0])
                    next_segment_payload = self._segment_payload(
                        replace(
                            segment,
                            anchor_candidates=merged_anchors,
                            representative_frame=merged_anchors[0],
                        ),
                        current_anchor_index=next_anchor_index,
                    )
                return {
                    "submitted": {
                        "segment_id": segment.segment_id,
                        "video_stem": segment.video_stem,
                        "start_frame": segment.start_frame,
                        "end_frame": segment.end_frame,
                        "representative_frame": segment.representative_frame,
                    },
                    "submitted_frame_count": 0,
                    "fallback": fallback,
                    "next_segment": next_segment_payload,
                }

            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                for record in frame_records:
                    key = (record["video_stem"], int(record["frame_index"]))
                    self._insert_annotation(conn, record)
                    self._update_track_person_stats(conn, record)
                    conn.execute(
                        """
                        UPDATE frame_counts
                        SET annotation_count = annotation_count + 1
                        WHERE video_stem=? AND frame_index=?
                        """,
                        (key[0], key[1]),
                    )
                self._mark_segment_resolved(conn, segment, annotator_id, "segment")
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

            for record in frame_records:
                self._append_jsonl_record(record)
                self._append_reviewed_csv(record)
            self._sync_counts_csv_from_db()
            next_segment_record = self._pick_next_segment_unlocked(annotator_id=annotator_id, allow_none=True)
            next_segment = self._segment_payload(next_segment_record) if next_segment_record is not None else None
            return {
                "submitted": {
                    "segment_id": segment.segment_id,
                    "video_stem": segment.video_stem,
                    "start_frame": segment.start_frame,
                    "end_frame": segment.end_frame,
                    "representative_frame": segment.representative_frame,
                },
                "submitted_frame_count": len(frame_records),
                "next_segment": next_segment,
            }

    def export_reviewed_csvs(self) -> Dict[str, int]:
        exported: Dict[str, int] = {}
        with self._lock:
            conn = self._connect()
            try:
                for stem in self.video_stems:
                    rows = conn.execute(
                        """
                        SELECT
                            annotation_id,
                            video_stem,
                            frame_index,
                            timestamp_ms,
                            annotator_id,
                            submitted_at,
                            slots_json
                        FROM annotations
                        WHERE video_stem=?
                        ORDER BY submitted_at ASC, annotation_id ASC
                        """,
                        (stem,),
                    ).fetchall()

                    reviewed_csv = self.reviewed_dir / f"{stem}.reviewed.csv"
                    jsonl_path = self.reviewed_raw_dir / f"{stem}.frame_records.jsonl"

                    with reviewed_csv.open("w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=REVIEWED_COLUMNS)
                        writer.writeheader()
                        for row in rows:
                            writer.writerow({k: row[k] for k in REVIEWED_COLUMNS})

                    with jsonl_path.open("w", encoding="utf-8") as f:
                        for row in rows:
                            data = {k: row[k] for k in REVIEWED_COLUMNS}
                            f.write(json.dumps(data, ensure_ascii=False) + "\n")

                    exported[stem] = len(rows)
            finally:
                conn.close()

        self.logger.info(
            "export reviewed csv done "
            + ", ".join(f"{stem}={count}" for stem, count in exported.items())
        )
        return exported

    def export_reviewed_csv_for_stem(self, stem: str) -> int:
        if stem not in self.video_stems:
            raise ValueError(f"invalid video_stem: {stem}")
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT
                    annotation_id,
                    video_stem,
                    frame_index,
                    timestamp_ms,
                    annotator_id,
                    submitted_at,
                    slots_json
                FROM annotations
                WHERE video_stem=?
                ORDER BY submitted_at ASC, annotation_id ASC
                """,
                (stem,),
            ).fetchall()
        finally:
            conn.close()

        reviewed_csv = self.reviewed_dir / f"{stem}.reviewed.csv"
        jsonl_path = self.reviewed_raw_dir / f"{stem}.frame_records.jsonl"

        with reviewed_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=REVIEWED_COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row[k] for k in REVIEWED_COLUMNS})

        with jsonl_path.open("w", encoding="utf-8") as f:
            for row in rows:
                data = {k: row[k] for k in REVIEWED_COLUMNS}
                f.write(json.dumps(data, ensure_ascii=False) + "\n")

        self.logger.info(f"export reviewed csv done stem={stem} count={len(rows)}")
        return len(rows)

    def status_summary(self) -> Dict[str, Any]:
        with self._lock:
            conn = self._connect()
            try:
                overall = conn.execute(
                    """
                    SELECT
                        COUNT(*) AS total_frames,
                        SUM(CASE WHEN annotation_count < 3 THEN 1 ELSE 0 END) AS lt3_frames,
                        MIN(annotation_count) AS min_count,
                        MAX(annotation_count) AS max_count
                    FROM frame_counts
                    """
                ).fetchone()

                by_video_rows = conn.execute(
                    """
                    SELECT
                        video_stem,
                        COUNT(*) AS total_frames,
                        SUM(CASE WHEN annotation_count < 3 THEN 1 ELSE 0 END) AS lt3_frames,
                        MIN(annotation_count) AS min_count,
                        MAX(annotation_count) AS max_count
                    FROM frame_counts
                    GROUP BY video_stem
                    ORDER BY video_stem
                    """
                ).fetchall()
            finally:
                conn.close()

        by_video: Dict[str, Dict[str, int]] = {}
        for row in by_video_rows:
            by_video[str(row["video_stem"])] = {
                "total_frames": int(row["total_frames"] or 0),
                "lt3_frames": int(row["lt3_frames"] or 0),
                "min_count": int(row["min_count"] or 0),
                "max_count": int(row["max_count"] or 0),
            }

        return {
            "total_frames": int(overall["total_frames"] or 0),
            "lt3_frames": int(overall["lt3_frames"] or 0),
            "min_count": int(overall["min_count"] or 0),
            "max_count": int(overall["max_count"] or 0),
            "by_video": by_video,
            "db_path": str(self.db_path),
        }

    def frame_image_bytes(self, video_stem: str, frame_index: int) -> bytes:
        if self.reader is None:
            raise RuntimeError("state not initialized")
        key = (video_stem, frame_index)
        cached = self._get_cached_frame(key)
        if cached is not None:
            return cached
        if self.frame_cache_dir is not None:
            disk_path = self._frame_cache_path(video_stem, frame_index)
            if disk_path.exists():
                image = disk_path.read_bytes()
                self._set_cached_frame(key, image)
                return image

        image = self.reader.read_jpeg(video_stem, frame_index)
        self._set_cached_frame(key, image)
        if self.frame_cache_dir is not None:
            self._write_disk_cache(video_stem, frame_index, image)
        return image

    def list_annotations_for_annotator(self, annotator_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """
                    SELECT
                        annotation_id,
                        video_stem,
                        frame_index,
                        timestamp_ms,
                        submitted_at,
                        slots_json
                    FROM annotations
                    WHERE annotator_id=?
                    ORDER BY submitted_at DESC, annotation_id DESC
                    """,
                    (annotator_id,),
                ).fetchall()
            finally:
                conn.close()

        return [
            {
                "annotation_id": str(r["annotation_id"]),
                "video_stem": str(r["video_stem"]),
                "frame_index": int(r["frame_index"]),
                "timestamp_ms": float(r["timestamp_ms"]),
                "submitted_at": str(r["submitted_at"]),
                "slots_json": str(r["slots_json"]),
                "slots_summary": slot_summary_from_json(str(r["slots_json"])),
            }
            for r in rows
        ]

    def annotation_detail(self, annotator_id: str, annotation_id: str) -> Dict[str, Any]:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM annotations WHERE annotation_id=? AND annotator_id=?",
                    (annotation_id, annotator_id),
                ).fetchone()
                if row is None:
                    raise ValueError("annotation not found for annotator")

                stem = str(row["video_stem"])
                frame_index = int(row["frame_index"])
                key = (stem, frame_index)
                if key not in self.frame_lookup:
                    raise ValueError("frame not found in frame pool")

                count_row = conn.execute(
                    """
                    SELECT annotation_count
                    FROM frame_counts
                    WHERE video_stem=? AND frame_index=?
                    """,
                    (stem, frame_index),
                ).fetchone()
                count_before = int(count_row["annotation_count"]) if count_row else 0
            finally:
                conn.close()

        if self.reader is None:
            raise RuntimeError("state not initialized")
        width, height = self.reader.get_dimensions(stem)
        frame = {
            "video_stem": stem,
            "frame_index": frame_index,
            "timestamp_ms": _safe_float(row["timestamp_ms"]),
            "annotation_count": count_before,
            "total_frames": len(self.frame_pool),
            "image_width": width,
            "image_height": height,
            "ai_boxes": self.ai_boxes.get(key, []),
            "recommendations": [],
            "slot_names": SLOT_NAMES,
            "image_url": f"/api/frame_image?video_stem={stem}&frame_index={frame_index}",
        }

        annotation = {k: row[k] for k in REVIEWED_COLUMNS}
        annotation["annotation_id"] = str(annotation["annotation_id"])
        annotation["annotator_id"] = str(annotation["annotator_id"])
        annotation["video_stem"] = str(annotation["video_stem"])
        annotation["submitted_at"] = str(annotation["submitted_at"])
        try:
            parsed_slots = json.loads(str(annotation["slots_json"]))
        except Exception:
            parsed_slots = [empty_slot_record(slot) for slot in SLOT_NAMES]
        if not isinstance(parsed_slots, list):
            parsed_slots = [empty_slot_record(slot) for slot in SLOT_NAMES]
        annotation["slots"] = parsed_slots
        return {"frame": frame, "annotation": annotation}

    def segment_detail(self, segment_id: str) -> Dict[str, Any]:
        segment = self.segment_lookup.get(segment_id)
        if segment is None:
            raise ValueError("segment not found")
        return self._segment_payload(segment)

    def update_annotation(self, annotator_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        annotation_id = str(payload.get("annotation_id", "")).strip()
        if not annotation_id:
            raise ValueError("annotation_id is required")

        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT * FROM annotations WHERE annotation_id=?",
                    (annotation_id,),
                ).fetchone()
                if row is None:
                    raise ValueError("annotation not found")
                if str(row["annotator_id"]) != annotator_id:
                    raise ValueError("annotator_id does not match annotation")

                stem = str(row["video_stem"])
                frame_index = int(row["frame_index"])
                timestamp_ms = float(row["timestamp_ms"])

                # validate payload consistency
                if str(payload.get("video_stem", "")).strip() != stem:
                    raise ValueError("video_stem mismatch")
                if int(payload.get("frame_index", 0)) != frame_index:
                    raise ValueError("frame_index mismatch")
                if abs(float(payload.get("timestamp_ms", 0.0)) - timestamp_ms) > 1.0:
                    raise ValueError("timestamp mismatch")

                slots = self._validate_slots_payload(payload.get("slots"))
                submitted_at = _now_iso()

                conn.execute(
                    """
                    UPDATE annotations
                    SET
                        submitted_at=?,
                        slots_json=?
                    WHERE annotation_id=?
                    """,
                    (
                        submitted_at,
                        json.dumps(slots, ensure_ascii=False),
                        annotation_id,
                    ),
                )

                self._rebuild_track_person_stats(conn)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

        self.export_reviewed_csv_for_stem(stem)
        return {
            "annotation_id": annotation_id,
            "submitted_at": submitted_at,
            "video_stem": stem,
            "frame_index": frame_index,
        }

    def _get_cached_frame(self, key: Tuple[str, int]) -> bytes | None:
        with self._frame_cache_lock:
            data = self._frame_cache.get(key)
            if data is None:
                return None
            self._frame_cache.move_to_end(key)
            return data

    def _set_cached_frame(self, key: Tuple[str, int], data: bytes) -> None:
        with self._frame_cache_lock:
            self._frame_cache[key] = data
            self._frame_cache.move_to_end(key)
            while len(self._frame_cache) > self._frame_cache_max:
                self._frame_cache.popitem(last=False)

    def _frame_cache_path(self, video_stem: str, frame_index: int) -> Path:
        if self.frame_cache_dir is None:
            raise RuntimeError("disk cache not enabled")
        safe_stem = video_stem.replace("/", "_")
        return self.frame_cache_dir / safe_stem / f"{frame_index:06d}.jpg"

    def _write_disk_cache(self, video_stem: str, frame_index: int, data: bytes) -> None:
        path = self._frame_cache_path(video_stem, frame_index)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".tmp")
        try:
            tmp_path.write_bytes(data)
            tmp_path.replace(path)
        except Exception:
            tmp_path.unlink(missing_ok=True)

    def _prewarm_disk_cache(self) -> None:
        if self.frame_cache_dir is None:
            return
        self.logger.info("frame cache prewarm started")
        for stem, video_path in self.video_paths.items():
            try:
                cap = cv2.VideoCapture(str(video_path))
                if not cap.isOpened():
                    self.logger.error(f"frame cache prewarm failed to open video: {video_path}")
                    continue
                frame_index = 0
                while True:
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        break
                    frame_index += 1
                    cache_path = self._frame_cache_path(stem, frame_index)
                    if cache_path.exists():
                        continue
                    ok_encode, buf = cv2.imencode(
                        ".jpg",
                        frame,
                        [cv2.IMWRITE_JPEG_QUALITY, self.frame_cache_quality],
                    )
                    if not ok_encode:
                        continue
                    self._write_disk_cache(stem, frame_index, bytes(buf))
                    if frame_index % 300 == 0:
                        self.logger.info(
                            f"frame cache prewarm {stem}: cached {frame_index} frames"
                        )
            finally:
                if "cap" in locals():
                    cap.release()
        self.logger.info("frame cache prewarm finished")

    def prewarm_disk_cache_blocking(self) -> None:
        self._prewarm_disk_cache()

    def _reset_storage_artifacts(self) -> None:
        self.db_path.unlink(missing_ok=True)
        self.count_path.unlink(missing_ok=True)
        for stem in self.video_stems or DEFAULT_TARGET_VIDEO_STEMS:
            (self.reviewed_raw_dir / f"{stem}.frame_records.jsonl").unlink(missing_ok=True)
            (self.reviewed_dir / f"{stem}.reviewed.csv").unlink(missing_ok=True)
        self.logger.info("storage reset requested: removed existing db and review artifacts")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=30,
            isolation_level=None,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_database(self) -> None:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            if self.reset_storage:
                conn.executescript(
                    """
                    DROP TABLE IF EXISTS segment_reviews;
                    DROP TABLE IF EXISTS track_person_stats;
                    DROP TABLE IF EXISTS annotations;
                    DROP TABLE IF EXISTS frame_counts;
                    DROP TABLE IF EXISTS frames;
                    """
                )
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS frames (
                    video_stem TEXT NOT NULL,
                    frame_index INTEGER NOT NULL,
                    timestamp_ms REAL NOT NULL,
                    PRIMARY KEY (video_stem, frame_index)
                );

                CREATE TABLE IF NOT EXISTS frame_counts (
                    video_stem TEXT NOT NULL,
                    frame_index INTEGER NOT NULL,
                    annotation_count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (video_stem, frame_index),
                    FOREIGN KEY (video_stem, frame_index)
                        REFERENCES frames(video_stem, frame_index)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS annotations (
                    annotation_id TEXT PRIMARY KEY,
                    video_stem TEXT NOT NULL,
                    frame_index INTEGER NOT NULL,
                    timestamp_ms REAL NOT NULL,
                    annotator_id TEXT NOT NULL,
                    submitted_at TEXT NOT NULL,
                    slots_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS track_person_stats (
                    video_stem TEXT NOT NULL,
                    ai_track_id TEXT NOT NULL,
                    p1_count INTEGER NOT NULL DEFAULT 0,
                    p2_count INTEGER NOT NULL DEFAULT 0,
                    last_updated_at TEXT NOT NULL,
                    PRIMARY KEY (video_stem, ai_track_id)
                );

                CREATE TABLE IF NOT EXISTS segment_reviews (
                    segment_id TEXT PRIMARY KEY,
                    resolved_at TEXT NOT NULL,
                    annotator_id TEXT NOT NULL,
                    segment_type TEXT NOT NULL,
                    representative_frame INTEGER NOT NULL,
                    resolution_kind TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_annotations_annotator
                ON annotations (annotator_id);
                CREATE INDEX IF NOT EXISTS idx_annotations_frame
                ON annotations (video_stem, frame_index);
                CREATE INDEX IF NOT EXISTS idx_annotations_submitted
                ON annotations (submitted_at);
                """
            )

            conn.executemany(
                """
                INSERT OR REPLACE INTO frames (video_stem, frame_index, timestamp_ms)
                VALUES (?, ?, ?)
                """,
                [(r.video_stem, r.frame_index, r.timestamp_ms) for r in self.frame_pool],
            )

            conn.executemany(
                """
                INSERT OR IGNORE INTO frame_counts (video_stem, frame_index, annotation_count)
                VALUES (?, ?, 0)
                """,
                [(r.video_stem, r.frame_index) for r in self.frame_pool],
            )

            conn.execute(
                """
                DELETE FROM frame_counts
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM frames f
                    WHERE f.video_stem=frame_counts.video_stem
                      AND f.frame_index=frame_counts.frame_index
                )
                """
            )

            # Recompute counts from annotations to keep consistency.
            conn.execute("UPDATE frame_counts SET annotation_count=0")
            conn.execute(
                """
                UPDATE frame_counts
                SET annotation_count = (
                    SELECT COUNT(*)
                    FROM annotations a
                    WHERE a.video_stem = frame_counts.video_stem
                      AND a.frame_index = frame_counts.frame_index
                )
                """
            )

            if not self.reset_storage:
                row = conn.execute(
                    "SELECT COUNT(*) AS c FROM track_person_stats"
                ).fetchone()
                if row is not None and int(row["c"] or 0) == 0:
                    self._rebuild_track_person_stats(conn)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _load_manifest_assets(self) -> Tuple[Dict[str, Path], Dict[str, Path], List[str]]:
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"manifest not found: {self.manifest_path}")
        video_paths: Dict[str, Path] = {}
        timestamp_paths: Dict[str, Path] = {}
        with self.manifest_path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                stem = row.get("video_stem", "").strip()
                if not stem:
                    continue
                status = row.get("status", "").strip().lower()
                if status == "blocked":
                    continue
                raw_video_path = Path(row.get("video_path", "").strip())
                video_path = (
                    raw_video_path
                    if raw_video_path.is_absolute()
                    else (REPO_ROOT / raw_video_path)
                )
                if not video_path.exists():
                    raise FileNotFoundError(f"video path missing for {stem}: {video_path}")
                raw_timestamp_path = Path(row.get("timestamp_path", "").strip())
                timestamp_path = (
                    raw_timestamp_path
                    if raw_timestamp_path.is_absolute()
                    else (REPO_ROOT / raw_timestamp_path)
                )
                if not timestamp_path.exists():
                    raise FileNotFoundError(f"timestamp path missing for {stem}: {timestamp_path}")
                video_paths[stem] = video_path
                timestamp_paths[stem] = timestamp_path
        video_stems = sorted(video_paths)
        if not video_stems:
            raise ValueError(f"manifest has no usable video stems: {self.manifest_path}")
        return video_paths, timestamp_paths, video_stems

    def _build_frame_pool(self) -> List[FrameRecord]:
        all_records: List[FrameRecord] = []
        for stem in self.video_stems:
            ts_path = self.timestamp_paths[stem]
            if not ts_path.exists():
                raise FileNotFoundError(f"timestamp csv not found: {ts_path}")
            with ts_path.open("r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if not {"frame_index", "timestamp_ms"}.issubset(set(reader.fieldnames or [])):
                    raise ValueError(f"timestamp file missing required columns: {ts_path}")
                for row in reader:
                    try:
                        frame_index = int(row["frame_index"])
                        timestamp_ms = float(row["timestamp_ms"])
                    except Exception:
                        continue
                    all_records.append(
                        FrameRecord(
                            video_stem=stem,
                            frame_index=frame_index,
                            timestamp_ms=timestamp_ms,
                        )
                    )

        with self.frame_pool_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FRAME_POOL_COLUMNS)
            writer.writeheader()
            for rec in all_records:
                writer.writerow(
                    {
                        "video_stem": rec.video_stem,
                        "frame_index": rec.frame_index,
                        "timestamp_ms": f"{rec.timestamp_ms:.3f}",
                    }
                )
        self.logger.info(f"frame pool generated: {self.frame_pool_path}")
        return all_records

    def _load_ai_boxes(self) -> Dict[Tuple[str, int], List[Dict[str, float | int]]]:
        ai_boxes: Dict[Tuple[str, int], List[Dict[str, float | int]]] = {}
        for stem in self.video_stems:
            path = self.batch_dir / "pseudo_labels" / f"{stem}.auto.csv"
            if not path.exists():
                raise FileNotFoundError(f"missing pseudo label file: {path}")
            with path.open("r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        frame_index = int(row["frame_index"])
                        bbox_w = float(row["bbox_w"])
                        bbox_h = float(row["bbox_h"])
                        if bbox_w <= 0 or bbox_h <= 0:
                            continue
                        box = {
                            "track_id": int(float(row["track_id"])),
                            "bbox_x": _safe_float(row["bbox_x"]),
                            "bbox_y": _safe_float(row["bbox_y"]),
                            "bbox_w": _safe_float(bbox_w),
                            "bbox_h": _safe_float(bbox_h),
                            "score": _safe_float(row.get("score", 0.0)),
                        }
                    except Exception:
                        continue
                    key = (stem, frame_index)
                    ai_boxes.setdefault(key, []).append(box)
        for key, boxes in ai_boxes.items():
            boxes.sort(key=lambda b: (-float(b["score"]), int(b["track_id"])))
        return ai_boxes


    def _load_segment_pool(self) -> List[SegmentRecord]:
        segment_prep_dir = self.batch_dir / "segment_prep"
        if not segment_prep_dir.exists():
            return []
        segments: List[SegmentRecord] = []
        for path in sorted(segment_prep_dir.glob("*.segments.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            for item in payload.get("segments", []):
                if not isinstance(item, dict):
                    continue
                try:
                    segments.append(
                        SegmentRecord(
                            segment_id=str(item["segment_id"]).strip(),
                            video_stem=str(item["video_stem"]).strip(),
                            segment_type=str(item["segment_type"]).strip(),
                            start_frame=int(item["start_frame"]),
                            end_frame=int(item["end_frame"]),
                            representative_frame=int(item["representative_frame"]),
                            track_ids=[int(v) for v in item.get("track_ids", [])],
                            frame_count=int(item["frame_count"]),
                            anchor_candidates=[int(v) for v in item.get("anchor_candidates", [])],
                            repairability_score=float(item.get("repairability_score", 0.0) or 0.0),
                            fragmentation_score=int(item.get("fragmentation_score", 0) or 0),
                            expected_gain=int(item.get("expected_gain", 0) or 0),
                            trigger_reason=str(item.get("trigger_reason", "") or ""),
                        )
                    )
                except Exception:
                    continue
        segments.sort(key=lambda item: (item.video_stem, item.start_frame, item.end_frame, item.segment_id))
        return segments

    def _load_segment_frame_lookup(self) -> Dict[str, Dict[int, str]]:
        segment_prep_dir = self.batch_dir / "segment_prep"
        if not segment_prep_dir.exists():
            return {}
        lookup: Dict[str, Dict[int, str]] = {}
        for path in sorted(segment_prep_dir.glob("*.segment_frames.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            video_stem = str(payload.get("video_stem", "")).strip()
            if not video_stem:
                continue
            frame_map: Dict[int, str] = {}
            raw = payload.get("frame_to_segment", {})
            if isinstance(raw, dict):
                for key, value in raw.items():
                    try:
                        frame_map[int(key)] = str(value)
                    except Exception:
                        continue
            lookup[video_stem] = frame_map
        return lookup

    def _expand_slots_for_frame(
        self,
        base_slots: List[Dict[str, Any]],
        video_stem: str,
        frame_index: int,
    ) -> List[Dict[str, Any]]:
        key = (video_stem, frame_index)
        ai_by_track = {
            str(int(float(box["track_id"]))): box
            for box in self.ai_boxes.get(key, [])
        }
        expanded: List[Dict[str, Any]] = []
        for item in base_slots:
            slot = str(item.get("slot", "")).strip().lower()
            source = str(item.get("source", "")).strip()
            if source in {"absent", "occluded", "outside"}:
                expanded.append(empty_slot_record(slot) | {"slot": slot, "source": source})
                continue
            if source == "ai":
                track_id = str(item.get("ai_track_id", "")).strip()
                box = ai_by_track.get(track_id)
                if box is None:
                    expanded.append(empty_slot_record(slot) | {"slot": slot, "source": "absent"})
                    continue
                expanded.append(
                    {
                        "slot": slot,
                        "bbox_x": _safe_float(box["bbox_x"]),
                        "bbox_y": _safe_float(box["bbox_y"]),
                        "bbox_w": _safe_float(box["bbox_w"]),
                        "bbox_h": _safe_float(box["bbox_h"]),
                        "source": "ai",
                        "ai_track_id": track_id,
                    }
                )
                continue
            expanded.append(
                {
                    "slot": slot,
                    "bbox_x": _safe_float(item.get("bbox_x", 0.0)),
                    "bbox_y": _safe_float(item.get("bbox_y", 0.0)),
                    "bbox_w": _safe_float(item.get("bbox_w", 0.0)),
                    "bbox_h": _safe_float(item.get("bbox_h", 0.0)),
                    "source": source,
                    "ai_track_id": str(item.get("ai_track_id", "")).strip(),
                }
            )
        return expanded

    def _resolve_stable_segment_slots(
        self,
        video_stem: str,
        representative_frame: int,
        slots: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        key = (video_stem, representative_frame)
        ai_boxes = self.ai_boxes.get(key, [])
        ai_by_track = {
            str(int(float(box["track_id"]))): box
            for box in ai_boxes
        }
        claimed: set[str] = set()
        resolved: List[Dict[str, Any]] = []
        for item in slots:
            slot = str(item.get("slot", "")).strip().lower()
            source = str(item.get("source", "")).strip()
            if source in {"absent", "not_set"}:
                resolved.append(empty_slot_record(slot) | {"slot": slot, "source": "absent"})
                continue
            if source in {"occluded", "outside"}:
                raise ValueError("stable segments do not accept occluded/outside states")
            track_id = str(item.get("ai_track_id", "") or "").strip()
            if track_id:
                if track_id not in ai_by_track:
                    raise ValueError(f"{slot} ai_track_id {track_id} not found on representative frame")
                if track_id in claimed:
                    raise ValueError(f"duplicate ai_track_id assignment: {track_id}")
                claimed.add(track_id)
                resolved.append({**item, "slot": slot, "ai_track_id": track_id})
                continue
            bbox = (
                _safe_float(item.get("bbox_x", 0.0)),
                _safe_float(item.get("bbox_y", 0.0)),
                _safe_float(item.get("bbox_w", 0.0)),
                _safe_float(item.get("bbox_h", 0.0)),
            )
            best_track_id = self._infer_track_id_for_bbox(ai_by_track, bbox, claimed)
            if not best_track_id:
                raise ValueError(f"{slot} could not be matched to a unique AI track on representative frame")
            claimed.add(best_track_id)
            resolved.append({**item, "slot": slot, "ai_track_id": best_track_id})
        return self._validate_slots_payload(resolved)

    def _infer_track_id_for_bbox(
        self,
        ai_by_track: Dict[str, Dict[str, Any]],
        bbox: Tuple[float, float, float, float],
        claimed: set[str],
    ) -> str | None:
        x, y, w, h = bbox
        if w <= 0 or h <= 0:
            return None
        candidates: List[Tuple[float, str]] = []
        for track_id, box in ai_by_track.items():
            if track_id in claimed:
                continue
            overlap = self._bbox_iou(
                bbox,
                (
                    float(box["bbox_x"]),
                    float(box["bbox_y"]),
                    float(box["bbox_w"]),
                    float(box["bbox_h"]),
                ),
            )
            candidates.append((overlap, track_id))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (-item[0], int(item[1])))
        best_overlap, best_track_id = candidates[0]
        if best_overlap <= 0.0:
            return None
        if len(candidates) > 1 and abs(candidates[1][0] - best_overlap) < 1e-9:
            return None
        return best_track_id

    def _bbox_iou(
        self,
        box_a: Tuple[float, float, float, float],
        box_b: Tuple[float, float, float, float],
    ) -> float:
        ax, ay, aw, ah = box_a
        bx, by, bw, bh = box_b
        ax2, ay2 = ax + aw, ay + ah
        bx2, by2 = bx + bw, by + bh
        ix1, iy1 = max(ax, bx), max(ay, by)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
        inter = iw * ih
        if inter <= 0:
            return 0.0
        union = aw * ah + bw * bh - inter
        return inter / union if union > 0 else 0.0

    def _expand_segment_slots_for_frame(
        self,
        base_slots: List[Dict[str, Any]],
        video_stem: str,
        representative_frame: int,
        frame_index: int,
    ) -> List[Dict[str, Any]]:
        rep_ai = {
            str(int(float(box["track_id"]))): box
            for box in self.ai_boxes.get((video_stem, representative_frame), [])
        }
        cur_ai = {
            str(int(float(box["track_id"]))): box
            for box in self.ai_boxes.get((video_stem, frame_index), [])
        }
        expanded: List[Dict[str, Any]] = []
        for item in base_slots:
            slot = str(item.get("slot", "")).strip().lower()
            source = str(item.get("source", "")).strip()
            if source == "absent":
                expanded.append(empty_slot_record(slot) | {"slot": slot, "source": "absent"})
                continue
            track_id = str(item.get("ai_track_id", "")).strip()
            if not track_id:
                raise ValueError(f"{slot} missing ai_track_id for stable segment expansion")
            target = cur_ai.get(track_id)
            if target is None:
                raise ValueError(f"track {track_id} missing on frame {frame_index}")
            if source == "ai":
                expanded.append(
                    {
                        "slot": slot,
                        "bbox_x": _safe_float(target["bbox_x"]),
                        "bbox_y": _safe_float(target["bbox_y"]),
                        "bbox_w": _safe_float(target["bbox_w"]),
                        "bbox_h": _safe_float(target["bbox_h"]),
                        "source": "ai",
                        "ai_track_id": track_id,
                    }
                )
                continue
            rep_box = rep_ai.get(track_id)
            if rep_box is None:
                raise ValueError(f"track {track_id} missing on representative frame")
            dx = _safe_float(float(item.get("bbox_x", 0.0)) - float(rep_box["bbox_x"]))
            dy = _safe_float(float(item.get("bbox_y", 0.0)) - float(rep_box["bbox_y"]))
            dw = _safe_float(float(item.get("bbox_w", 0.0)) - float(rep_box["bbox_w"]))
            dh = _safe_float(float(item.get("bbox_h", 0.0)) - float(rep_box["bbox_h"]))
            expanded.append(
                {
                    "slot": slot,
                    "bbox_x": _safe_float(float(target["bbox_x"]) + dx),
                    "bbox_y": _safe_float(float(target["bbox_y"]) + dy),
                    "bbox_w": _safe_float(float(target["bbox_w"]) + dw),
                    "bbox_h": _safe_float(float(target["bbox_h"]) + dh),
                    "source": "manual_param",
                    "ai_track_id": track_id,
                }
            )
        return expanded

    def _build_segment_frame_records(
        self,
        annotator_id: str,
        segment: SegmentRecord,
        slots_by_frame: Dict[int, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        frame_records: List[Dict[str, Any]] = []
        for frame_index in range(segment.start_frame, segment.end_frame + 1):
            key = (segment.video_stem, frame_index)
            if key not in self.frame_lookup:
                continue
            rec = self.frame_lookup[key]
            frame_records.append(
                {
                    "annotation_id": f"ann_{int(time.time() * 1000)}_{uuid.uuid4().hex[:10]}",
                    "video_stem": segment.video_stem,
                    "frame_index": frame_index,
                    "timestamp_ms": _safe_float(rec.timestamp_ms),
                    "annotator_id": annotator_id,
                    "submitted_at": _now_iso(),
                    "slots_json": json.dumps(slots_by_frame[frame_index], ensure_ascii=False),
                }
            )
        return frame_records

    def _expand_single_slot(
        self,
        item: Dict[str, Any],
        video_stem: str,
        frame_index: int,
    ) -> Dict[str, Any]:
        slot = str(item.get("slot", "")).strip().lower()
        source = str(item.get("source", "")).strip()
        if source in {"absent", "occluded", "outside"}:
            return empty_slot_record(slot) | {"slot": slot, "source": source}
        if source == "ai":
            expanded = self._expand_slots_for_frame([item], video_stem, frame_index)
            return expanded[0] if expanded else empty_slot_record(slot) | {"slot": slot, "source": "absent"}
        return {
            "slot": slot,
            "bbox_x": _safe_float(item.get("bbox_x", 0.0)),
            "bbox_y": _safe_float(item.get("bbox_y", 0.0)),
            "bbox_w": _safe_float(item.get("bbox_w", 0.0)),
            "bbox_h": _safe_float(item.get("bbox_h", 0.0)),
            "source": source,
            "ai_track_id": str(item.get("ai_track_id", "")).strip(),
        }

    def _interpolate_slot_ranges(
        self,
        start_frame: int,
        end_frame: int,
        start_slots: List[Dict[str, Any]],
        end_slots: List[Dict[str, Any]],
    ) -> Dict[int, List[Dict[str, Any]]]:
        if end_frame < start_frame:
            raise ValueError("end_frame must be >= start_frame")
        start_map = {
            str(item.get("slot", "")).strip().lower(): item
            for item in start_slots
            if isinstance(item, dict)
        }
        end_map = {
            str(item.get("slot", "")).strip().lower(): item
            for item in end_slots
            if isinstance(item, dict)
        }
        span = max(1, end_frame - start_frame)
        interpolated: Dict[int, List[Dict[str, Any]]] = {}
        for frame_index in range(start_frame, end_frame + 1):
            t = 0.0 if span == 0 else (frame_index - start_frame) / span
            frame_slots: List[Dict[str, Any]] = []
            for slot_name in SLOT_NAMES:
                start_item = start_map.get(slot_name)
                end_item = end_map.get(slot_name)
                if not start_item or not end_item:
                    continue
                start_source = str(start_item.get("source", "")).strip()
                end_source = str(end_item.get("source", "")).strip()
                if start_source in {"manual_draw", "manual_param"} and end_source in {"manual_draw", "manual_param"}:
                    frame_slots.append(
                        {
                            "slot": slot_name,
                            "bbox_x": _safe_float((1 - t) * float(start_item.get("bbox_x", 0.0)) + t * float(end_item.get("bbox_x", 0.0))),
                            "bbox_y": _safe_float((1 - t) * float(start_item.get("bbox_y", 0.0)) + t * float(end_item.get("bbox_y", 0.0))),
                            "bbox_w": _safe_float((1 - t) * float(start_item.get("bbox_w", 0.0)) + t * float(end_item.get("bbox_w", 0.0))),
                            "bbox_h": _safe_float((1 - t) * float(start_item.get("bbox_h", 0.0)) + t * float(end_item.get("bbox_h", 0.0))),
                            "source": "manual_param",
                            "ai_track_id": "",
                        }
                    )
            interpolated[frame_index] = frame_slots
        return interpolated

    def _expand_interpolated_slots_for_frame(
        self,
        video_stem: str,
        frame_index: int,
        start_frame: int,
        end_frame: int,
        start_slots: List[Dict[str, Any]],
        end_slots: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        start_map = {
            str(item.get("slot", "")).strip().lower(): item
            for item in start_slots
            if isinstance(item, dict)
        }
        end_map = {
            str(item.get("slot", "")).strip().lower(): item
            for item in end_slots
            if isinstance(item, dict)
        }
        manual_interp = self._interpolate_slot_ranges(
            start_frame=start_frame,
            end_frame=end_frame,
            start_slots=start_slots,
            end_slots=end_slots,
        ).get(frame_index, [])
        manual_map = {str(item["slot"]).strip().lower(): item for item in manual_interp}

        result: List[Dict[str, Any]] = []
        midpoint = (start_frame + end_frame) / 2.0
        for slot_name in SLOT_NAMES:
            if slot_name in manual_map:
                result.append(manual_map[slot_name])
                continue
            start_item = start_map.get(slot_name)
            end_item = end_map.get(slot_name)
            if start_item and end_item:
                start_source = str(start_item.get("source", "")).strip()
                end_source = str(end_item.get("source", "")).strip()
                if start_source == "absent" and end_source == "absent":
                    result.append(empty_slot_record(slot_name) | {"slot": slot_name, "source": "absent"})
                    continue
                if (
                    start_source == "ai"
                    and end_source == "ai"
                    and str(start_item.get("ai_track_id", "")).strip()
                    and str(start_item.get("ai_track_id", "")).strip() == str(end_item.get("ai_track_id", "")).strip()
                ):
                    result.append(self._expand_single_slot(start_item, video_stem, frame_index))
                    continue
                chosen = start_item if frame_index <= midpoint else end_item
                result.append(self._expand_single_slot(chosen, video_stem, frame_index))
                continue
            if start_item:
                result.append(self._expand_single_slot(start_item, video_stem, frame_index))
                continue
            if end_item:
                result.append(self._expand_single_slot(end_item, video_stem, frame_index))
        return result

    def _validate_repair_window_anchor_payload(
        self,
        segment: SegmentRecord,
        payload: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        anchors = payload.get("anchor_annotations")
        if not isinstance(anchors, list) or not anchors:
            raise ValueError("repair_window anchor_annotations are required")
        required_frames = segment.anchor_candidates or [segment.start_frame, segment.end_frame]
        provided: Dict[int, Dict[str, Any]] = {}
        for item in anchors:
            if not isinstance(item, dict):
                raise ValueError("repair_window anchors must be objects")
            frame_index = int(item.get("frame_index", 0))
            key = (segment.video_stem, frame_index)
            if frame_index not in required_frames:
                raise ValueError(f"unexpected repair_window anchor frame: {frame_index}")
            if frame_index in provided:
                raise ValueError(f"duplicate repair_window anchor frame: {frame_index}")
            if key not in self.frame_lookup:
                raise ValueError("invalid video_stem or frame_index")
            timestamp_ms = float(item.get("timestamp_ms", 0.0))
            expected_ts = self.frame_lookup[key].timestamp_ms
            if abs(expected_ts - timestamp_ms) > 1.0:
                raise ValueError("timestamp does not match frame pool mapping")
            provided[frame_index] = {
                "frame_index": frame_index,
                "timestamp_ms": _safe_float(timestamp_ms),
                "slots": self._validate_slots_payload(item.get("slots")),
            }
        missing = [frame for frame in required_frames if frame not in provided]
        if missing:
            raise ValueError(f"repair_window missing anchor annotations: {missing}")
        return [provided[frame] for frame in sorted(provided)]

    def _frame_ai_lookup(self, video_stem: str, frame_index: int) -> Dict[str, Dict[str, Any]]:
        return {
            str(int(float(box["track_id"]))): box
            for box in self.ai_boxes.get((video_stem, frame_index), [])
        }

    def _strict_ai_slot_for_frame(
        self,
        slot_name: str,
        video_stem: str,
        frame_index: int,
        track_id: str,
    ) -> Tuple[Dict[str, Any] | None, Dict[str, Any] | None]:
        ai_by_track = self._frame_ai_lookup(video_stem, frame_index)
        target = ai_by_track.get(track_id)
        if target is None:
            return None, {
                "reason": "missing_ai_track",
                "missing_frames": [frame_index],
                "slot": slot_name,
                "ai_track_id": track_id,
            }
        return (
            {
                "slot": slot_name,
                "bbox_x": _safe_float(target["bbox_x"]),
                "bbox_y": _safe_float(target["bbox_y"]),
                "bbox_w": _safe_float(target["bbox_w"]),
                "bbox_h": _safe_float(target["bbox_h"]),
                "source": "ai",
                "ai_track_id": track_id,
            },
            None,
        )

    def _repair_window_slot_between_anchors(
        self,
        video_stem: str,
        frame_index: int,
        start_frame: int,
        end_frame: int,
        start_item: Dict[str, Any],
        end_item: Dict[str, Any],
    ) -> Tuple[Dict[str, Any] | None, Dict[str, Any] | None]:
        slot_name = str(start_item.get("slot", "")).strip().lower()
        start_source = str(start_item.get("source", "") or "absent").strip()
        end_source = str(end_item.get("source", "") or "absent").strip()
        if start_source == "not_set":
            start_source = "absent"
        if end_source == "not_set":
            end_source = "absent"

        if start_source == "absent" and end_source == "absent":
            return empty_slot_record(slot_name) | {"slot": slot_name, "source": "absent"}, None

        start_track = str(start_item.get("ai_track_id", "") or "").strip()
        end_track = str(end_item.get("ai_track_id", "") or "").strip()
        if start_source == "ai" and end_source == "ai" and start_track and start_track == end_track:
            return self._strict_ai_slot_for_frame(slot_name, video_stem, frame_index, start_track)

        if start_source in {"manual_draw", "manual_param"} and end_source in {"manual_draw", "manual_param"}:
            span = max(1, end_frame - start_frame)
            t = 0.0 if span == 0 else (frame_index - start_frame) / span
            return (
                {
                    "slot": slot_name,
                    "bbox_x": _safe_float((1 - t) * float(start_item.get("bbox_x", 0.0)) + t * float(end_item.get("bbox_x", 0.0))),
                    "bbox_y": _safe_float((1 - t) * float(start_item.get("bbox_y", 0.0)) + t * float(end_item.get("bbox_y", 0.0))),
                    "bbox_w": _safe_float((1 - t) * float(start_item.get("bbox_w", 0.0)) + t * float(end_item.get("bbox_w", 0.0))),
                    "bbox_h": _safe_float((1 - t) * float(start_item.get("bbox_h", 0.0)) + t * float(end_item.get("bbox_h", 0.0))),
                    "source": "manual_param",
                    "ai_track_id": start_track if start_track and start_track == end_track else "",
                },
                None,
            )

        midpoint = (start_frame + end_frame) / 2.0
        chosen = start_item if frame_index <= midpoint else end_item
        chosen_source = str(chosen.get("source", "") or "absent").strip()
        if chosen_source == "not_set":
            chosen_source = "absent"
        if chosen_source in {"absent", "occluded", "outside"}:
            return empty_slot_record(slot_name) | {"slot": slot_name, "source": chosen_source}, None
        chosen_track = str(chosen.get("ai_track_id", "") or "").strip()
        if chosen_source == "ai" and chosen_track:
            return self._strict_ai_slot_for_frame(slot_name, video_stem, frame_index, chosen_track)
        return (
            {
                "slot": slot_name,
                "bbox_x": _safe_float(chosen.get("bbox_x", 0.0)),
                "bbox_y": _safe_float(chosen.get("bbox_y", 0.0)),
                "bbox_w": _safe_float(chosen.get("bbox_w", 0.0)),
                "bbox_h": _safe_float(chosen.get("bbox_h", 0.0)),
                "source": chosen_source,
                "ai_track_id": chosen_track,
            },
            None,
        )

    def _build_repair_window_slots_by_frame(
        self,
        segment: SegmentRecord,
        anchors: List[Dict[str, Any]],
    ) -> Tuple[Dict[int, List[Dict[str, Any]]] | None, Dict[str, Any] | None]:
        slots_by_frame: Dict[int, List[Dict[str, Any]]] = {
            int(anchor["frame_index"]): anchor["slots"]
            for anchor in anchors
        }
        sorted_anchors = sorted(anchors, key=lambda item: int(item["frame_index"]))
        for idx in range(len(sorted_anchors) - 1):
            start_anchor = sorted_anchors[idx]
            end_anchor = sorted_anchors[idx + 1]
            start_frame = int(start_anchor["frame_index"])
            end_frame = int(end_anchor["frame_index"])
            start_map = {str(item.get("slot", "")).strip().lower(): item for item in start_anchor["slots"]}
            end_map = {str(item.get("slot", "")).strip().lower(): item for item in end_anchor["slots"]}
            for frame_index in range(start_frame, end_frame + 1):
                if frame_index in slots_by_frame:
                    continue
                frame_slots: List[Dict[str, Any]] = []
                for slot_name in SLOT_NAMES:
                    start_item = start_map.get(slot_name, empty_slot_record(slot_name))
                    end_item = end_map.get(slot_name, empty_slot_record(slot_name))
                    slot_payload, fallback = self._repair_window_slot_between_anchors(
                        segment.video_stem,
                        frame_index,
                        start_frame,
                        end_frame,
                        start_item,
                        end_item,
                    )
                    if fallback is not None:
                        candidate_frames = sorted({*segment.anchor_candidates, *fallback.get("missing_frames", [])})
                        if len(candidate_frames) <= 4:
                            fallback = {
                                **fallback,
                                "suggested_anchor_frames": [frame for frame in fallback.get("missing_frames", []) if frame not in segment.anchor_candidates],
                            }
                        return None, fallback
                    assert slot_payload is not None
                    frame_slots.append(slot_payload)
                slots_by_frame[frame_index] = frame_slots
        for frame_index in range(segment.start_frame, segment.end_frame + 1):
            if frame_index not in slots_by_frame:
                return None, {
                    "reason": "incomplete_fill",
                    "missing_frames": [frame_index],
                }
        return slots_by_frame, None

    def _resolved_segment_ids(self, conn: sqlite3.Connection | None = None) -> set[str]:
        own_conn = conn is None
        if conn is None:
            conn = self._connect()
        try:
            rows = conn.execute("SELECT segment_id FROM segment_reviews").fetchall()
            return {str(row["segment_id"]) for row in rows}
        finally:
            if own_conn:
                conn.close()

    def _pick_next_segment_unlocked(
        self,
        annotator_id: str | None = None,
        allow_none: bool = False,
    ) -> SegmentRecord | None:
        del annotator_id
        if not self.segment_pool:
            if allow_none:
                return None
            raise ValueError("segment pool is empty")
        resolved_ids = self._resolved_segment_ids()
        unresolved = [segment for segment in self.segment_pool if segment.segment_id not in resolved_ids]
        if not unresolved:
            if allow_none:
                return None
            raise ValueError("no unresolved segments left")
        segment = unresolved[self._segment_dispatch_index % len(unresolved)]
        self._segment_dispatch_index += 1
        return segment

    def _mark_segment_resolved(
        self,
        conn: sqlite3.Connection,
        segment: SegmentRecord,
        annotator_id: str,
        resolution_kind: str,
    ) -> None:
        conn.execute(
            """
            INSERT OR REPLACE INTO segment_reviews (
                segment_id,
                resolved_at,
                annotator_id,
                segment_type,
                representative_frame,
                resolution_kind
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                segment.segment_id,
                _now_iso(),
                annotator_id,
                segment.segment_type,
                segment.representative_frame,
                resolution_kind,
            ),
        )

    def _annotation_count_for_frame(self, video_stem: str, frame_index: int) -> int:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT annotation_count
                FROM frame_counts
                WHERE video_stem=? AND frame_index=?
                """,
                (video_stem, frame_index),
            ).fetchone()
            return int(row["annotation_count"]) if row is not None else 0
        finally:
            conn.close()

    def _build_frame_payload(
        self,
        stem: str,
        frame_index: int,
        annotation_count: int,
        recommendations: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        key = (stem, frame_index)
        if key not in self.frame_lookup:
            raise ValueError("frame not found in frame pool")
        if self.reader is None:
            raise RuntimeError("state not initialized")
        rec = self.frame_lookup[key]
        width, height = self.reader.get_dimensions(stem)
        return {
            "video_stem": stem,
            "frame_index": frame_index,
            "timestamp_ms": _safe_float(rec.timestamp_ms),
            "annotation_count": annotation_count,
            "total_frames": len(self.frame_pool),
            "image_width": width,
            "image_height": height,
            "ai_boxes": self.ai_boxes.get(key, []),
            "recommendations": recommendations or [],
            "slot_names": SLOT_NAMES,
            "image_url": f"/api/frame_image?video_stem={stem}&frame_index={frame_index}",
        }

    def _segment_payload(self, segment: SegmentRecord, current_anchor_index: int = 0) -> Dict[str, Any]:
        repair_payload: Dict[str, Any] | None = None
        if segment.segment_type == "repair_window":
            anchor_frames = segment.anchor_candidates or [segment.start_frame, segment.end_frame]
            anchor_payloads = [
                self._build_frame_payload(
                    segment.video_stem,
                    frame_index,
                    self._annotation_count_for_frame(segment.video_stem, frame_index),
                    recommendations=[],
                )
                for frame_index in anchor_frames
            ]
            frame = anchor_payloads[0]
            repair_payload = {
                "anchor_frames": anchor_frames,
                "anchor_count": len(anchor_frames),
                "current_anchor_index": max(0, min(current_anchor_index, len(anchor_frames) - 1)),
                "anchors": anchor_payloads,
            }
        else:
            annotation_count = self._annotation_count_for_frame(segment.video_stem, segment.representative_frame)
            recommendations: List[Dict[str, Any]] = []
            conn = self._connect()
            try:
                recommendations = self._build_recommendations(
                    conn=conn,
                    video_stem=segment.video_stem,
                    ai_boxes=self.ai_boxes.get((segment.video_stem, segment.representative_frame), []),
                )
            finally:
                conn.close()
            frame = self._build_frame_payload(
                segment.video_stem,
                segment.representative_frame,
                annotation_count,
                recommendations=recommendations,
            )
        segment_payload = {
            "segment_id": segment.segment_id,
            "video_stem": segment.video_stem,
            "segment_type": segment.segment_type,
            "start_frame": segment.start_frame,
            "end_frame": segment.end_frame,
            "representative_frame": segment.representative_frame,
            "track_ids": segment.track_ids,
            "frame_count": segment.frame_count,
        }
        if segment.segment_type == "repair_window":
            segment_payload.update(
                {
                    "anchor_candidates": segment.anchor_candidates,
                    "repairability_score": segment.repairability_score,
                    "fragmentation_score": segment.fragmentation_score,
                    "expected_gain": segment.expected_gain,
                    "trigger_reason": segment.trigger_reason,
                }
            )
        payload = {
            "segment": segment_payload,
            "frame": frame,
        }
        if repair_payload is not None:
            payload["repair_window"] = repair_payload
        return payload

    def _init_review_files(self) -> None:
        for stem in self.video_stems:
            jsonl_path = self.reviewed_raw_dir / f"{stem}.frame_records.jsonl"
            reviewed_csv = self.reviewed_dir / f"{stem}.reviewed.csv"
            jsonl_path.touch(exist_ok=True)
            if reviewed_csv.exists():
                continue
            with reviewed_csv.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=REVIEWED_COLUMNS)
                writer.writeheader()

    def _sync_counts_csv_from_db(self) -> None:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT
                    f.video_stem,
                    f.frame_index,
                    f.timestamp_ms,
                    fc.annotation_count
                FROM frames f
                JOIN frame_counts fc
                  ON fc.video_stem=f.video_stem
                 AND fc.frame_index=f.frame_index
                ORDER BY f.video_stem ASC, f.frame_index ASC
                """
            ).fetchall()
        finally:
            conn.close()

        with self.count_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COUNT_COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "video_stem": row["video_stem"],
                        "frame_index": int(row["frame_index"]),
                        "timestamp_ms": f"{float(row['timestamp_ms']):.3f}",
                        "annotation_count": int(row["annotation_count"]),
                    }
                )

    def _build_recommendations(
        self,
        conn: sqlite3.Connection,
        video_stem: str,
        ai_boxes: List[Dict[str, float | int]],
    ) -> List[Dict[str, str]]:
        if not ai_boxes:
            return []

        rows = conn.execute(
            """
            SELECT slots_json
            FROM annotations
            WHERE video_stem=?
            ORDER BY submitted_at ASC, annotation_id ASC
            """,
            (video_stem,),
        ).fetchall()
        if not rows:
            return []

        slot_rank = {slot: idx for idx, slot in enumerate(SLOT_NAMES)}
        votes_by_track: Dict[str, Counter[str]] = {}
        for row in rows:
            try:
                slots = json.loads(str(row["slots_json"]))
            except Exception:
                continue
            if not isinstance(slots, list):
                continue
            for item in slots:
                if not isinstance(item, dict):
                    continue
                slot = str(item.get("slot", "")).strip().lower()
                if slot not in slot_rank:
                    continue
                source = str(item.get("source", "")).strip()
                if source in {"absent", "occluded", "outside", "not_set"}:
                    continue
                ai_track_id = str(item.get("ai_track_id", "") or "").strip()
                if not ai_track_id:
                    continue
                votes_by_track.setdefault(ai_track_id, Counter())[slot] += 1

        candidates: List[Dict[str, Any]] = []
        visible_track_ids = sorted({str(int(float(box["track_id"]))) for box in ai_boxes})
        for ai_track_id in visible_track_ids:
            counts = votes_by_track.get(ai_track_id)
            if not counts:
                continue
            ranked = sorted(
                counts.items(),
                key=lambda item: (-item[1], slot_rank[item[0]]),
            )
            if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
                continue
            slot, vote_count = ranked[0]
            total_votes = sum(counts.values())
            if vote_count <= 0 or total_votes <= 0:
                continue
            candidates.append(
                {
                    "slot": slot,
                    "ai_track_id": ai_track_id,
                    "vote_count": vote_count,
                    "confidence": _safe_float(vote_count / total_votes),
                    "reason": "history_majority",
                }
            )

        candidates.sort(
            key=lambda item: (
                -int(item["vote_count"]),
                -float(item["confidence"]),
                int(str(item["ai_track_id"])),
            )
        )
        recommendations: List[Dict[str, Any]] = []
        used_slots: set[str] = set()
        used_tracks: set[str] = set()
        for item in candidates:
            slot = str(item["slot"])
            ai_track_id = str(item["ai_track_id"])
            if slot in used_slots or ai_track_id in used_tracks:
                continue
            used_slots.add(slot)
            used_tracks.add(ai_track_id)
            recommendations.append(item)
        return recommendations

    def _insert_annotation(self, conn: sqlite3.Connection, record: Dict[str, Any]) -> None:
        conn.execute(
            """
            INSERT INTO annotations (
                annotation_id,
                video_stem,
                frame_index,
                timestamp_ms,
                annotator_id,
                submitted_at,
                slots_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            tuple(record[k] for k in REVIEWED_COLUMNS),
        )

    def _update_track_person_stats(self, conn: sqlite3.Connection, record: Dict[str, Any]) -> None:
        return

    def _rebuild_track_person_stats(self, conn: sqlite3.Connection) -> None:
        conn.execute("DELETE FROM track_person_stats")

    def _validate_and_build_record(
        self, annotator_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        stem = str(payload.get("video_stem", "")).strip()
        frame_index = int(payload.get("frame_index", 0))
        timestamp_ms = float(payload.get("timestamp_ms", 0.0))
        key = (stem, frame_index)
        if key not in self.frame_lookup:
            raise ValueError("invalid video_stem or frame_index")
        expected_ts = self.frame_lookup[key].timestamp_ms
        if abs(expected_ts - timestamp_ms) > 1.0:
            raise ValueError("timestamp does not match frame pool mapping")

        slots = self._validate_slots_payload(payload.get("slots"))
        annotation_id = f"ann_{int(time.time() * 1000)}_{uuid.uuid4().hex[:10]}"
        record = {
            "annotation_id": annotation_id,
            "video_stem": stem,
            "frame_index": frame_index,
            "timestamp_ms": _safe_float(timestamp_ms),
            "annotator_id": annotator_id,
            "submitted_at": _now_iso(),
            "slots_json": json.dumps(slots, ensure_ascii=False),
        }
        return record

    def _validate_slots_payload(self, slots: Any) -> List[Dict[str, Any]]:
        if not isinstance(slots, list):
            raise ValueError("slots payload is missing")

        slot_map: Dict[str, Dict[str, Any]] = {}
        for item in slots:
            if not isinstance(item, dict):
                raise ValueError("slot payload must be objects")
            slot_name = str(item.get("slot", "")).strip().lower()
            if slot_name not in SLOT_NAMES:
                raise ValueError(f"invalid slot name: {slot_name}")
            source = str(item.get("source", "")).strip()
            if source not in VALID_SLOT_SOURCES:
                raise ValueError(
                    f"{slot_name} source must be one of ai/manual_draw/manual_param/absent/occluded/outside"
                )

            if source in {"absent", "occluded", "outside"}:
                slot_map[slot_name] = {
                    "slot": slot_name,
                    "bbox_x": 0.0,
                    "bbox_y": 0.0,
                    "bbox_w": 0.0,
                    "bbox_h": 0.0,
                    "source": source,
                    "ai_track_id": "",
                }
                continue

            x = _safe_float(item.get("bbox_x", 0.0))
            y = _safe_float(item.get("bbox_y", 0.0))
            w = _safe_float(item.get("bbox_w", 0.0))
            h = _safe_float(item.get("bbox_h", 0.0))
            if w <= 0 or h <= 0:
                raise ValueError(f"{slot_name} bbox must have w>0 and h>0")
            ai_track = item.get("ai_track_id", "")
            if ai_track in ("", None):
                ai_track_str = ""
            else:
                ai_track_str = str(int(float(ai_track)))
            slot_map[slot_name] = {
                "slot": slot_name,
                "bbox_x": x,
                "bbox_y": y,
                "bbox_w": w,
                "bbox_h": h,
                "source": source,
                "ai_track_id": ai_track_str,
            }

        normalized: List[Dict[str, Any]] = []
        for slot_name in SLOT_NAMES:
            normalized.append(slot_map.get(slot_name, empty_slot_record(slot_name)))
        return normalized

    def _append_jsonl_record(self, record: Dict[str, Any]) -> None:
        path = self.reviewed_raw_dir / f"{record['video_stem']}.frame_records.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _append_reviewed_csv(self, record: Dict[str, Any]) -> None:
        path = self.reviewed_dir / f"{record['video_stem']}.reviewed.csv"
        file_exists = path.exists()
        with path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=REVIEWED_COLUMNS)
            if not file_exists:
                writer.writeheader()
            writer.writerow({k: record.get(k, "") for k in REVIEWED_COLUMNS})


class UiHandler(BaseHTTPRequestHandler):
    server_version = "UIReviewServer/2.0"

    @property
    def state(self) -> AnnotationState:
        return self.server.state  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: Any) -> None:
        msg = fmt % args
        self.state.logger.info(f"http {self.address_string()} {msg}")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/status":
            return self._send_json(HTTPStatus.OK, {"ok": True, "status": self.state.status_summary()})
        if path == "/api/my_annotations":
            return self._handle_my_annotations(parsed.query)
        if path == "/api/annotation_detail":
            return self._handle_annotation_detail(parsed.query)
        if path == "/api/segment_detail":
            return self._handle_segment_detail(parsed.query)
        if path == "/api/frame_image":
            return self._handle_frame_image(parsed.query)
        if path == "/":
            return self._serve_static_file("index.html", "text/html; charset=utf-8")
        if path == "/styles.css":
            return self._serve_static_file("styles.css", "text/css; charset=utf-8")
        if path == "/app.js":
            return self._serve_static_file("app.js", "application/javascript; charset=utf-8")
        self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/next_segment":
            return self._handle_next_segment()
        if path == "/api/submit_segment":
            return self._handle_submit_segment()
        if path == "/api/update_annotation":
            return self._handle_update_annotation()
        if path == "/api/export":
            return self._handle_export()
        self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def _handle_frame_image(self, query: str) -> None:
        q = parse_qs(query)
        stem = str(q.get("video_stem", [""])[0]).strip()
        frame_index_raw = str(q.get("frame_index", ["0"])[0]).strip()
        try:
            frame_index = int(frame_index_raw)
            if frame_index <= 0:
                raise ValueError("frame_index must be > 0")
            image = self.state.frame_image_bytes(stem, frame_index)
        except Exception as exc:
            self.state.logger.error(f"frame image failed stem={stem} frame={frame_index_raw}: {exc}")
            return self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": str(exc)},
            )
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(image)))
        self.end_headers()
        self.wfile.write(image)

    def _handle_next_segment(self) -> None:
        payload = self._read_json_payload()
        if payload is None:
            return
        annotator_id = str(payload.get("annotator_id", "")).strip() or "annotator_unknown"
        try:
            result = self.state.assign_next_segment(annotator_id=annotator_id)
        except Exception as exc:
            self.state.logger.error(f"next_segment failed annotator={annotator_id}: {exc}")
            return self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"ok": False, "error": str(exc)},
            )
        self._send_json(HTTPStatus.OK, {"ok": True, **result})

    def _handle_submit_segment(self) -> None:
        payload = self._read_json_payload()
        if payload is None:
            return
        annotator_id = str(payload.get("annotator_id", "")).strip() or "annotator_unknown"
        segment_id = str(payload.get("segment_id", "")).strip()
        if not segment_id:
            return self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "segment_id is required"},
            )
        try:
            result = self.state.submit_segment(
                annotator_id=annotator_id,
                segment_id=segment_id,
                payload=payload,
            )
        except Exception as exc:
            self.state.logger.error(f"submit_segment failed annotator={annotator_id} segment_id={segment_id}: {exc}")
            return self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": str(exc)},
            )
        self._send_json(HTTPStatus.OK, {"ok": True, **result})

    def _handle_update_annotation(self) -> None:
        payload = self._read_json_payload()
        if payload is None:
            return
        annotator_id = str(payload.get("annotator_id", "")).strip() or "annotator_unknown"
        try:
            result = self.state.update_annotation(annotator_id=annotator_id, payload=payload)
        except Exception as exc:
            self.state.logger.error(f"update_annotation failed annotator={annotator_id}: {exc}")
            return self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": str(exc)},
            )
        self._send_json(HTTPStatus.OK, {"ok": True, "updated": result})

    def _handle_export(self) -> None:
        try:
            counts = self.state.export_reviewed_csvs()
        except Exception as exc:
            self.state.logger.error(f"export failed: {exc}")
            return self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"ok": False, "error": str(exc)},
            )
        self._send_json(HTTPStatus.OK, {"ok": True, "exported": counts})

    def _serve_static_file(self, filename: str, content_type: str) -> None:
        path = self.state.static_dir / filename
        if not path.exists():
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": f"missing static file: {filename}"})
            return
        content = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _read_json_payload(self) -> Dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except Exception:
            length = 0
        if length <= 0:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "request body is required"},
            )
            return None
        body = self.rfile.read(length)
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "invalid json body"},
            )
            return None
        if not isinstance(payload, dict):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "json body must be an object"},
            )
            return None
        return payload

    def _handle_my_annotations(self, query: str) -> None:
        q = parse_qs(query)
        annotator_id = str(q.get("annotator_id", [""])[0]).strip() or "annotator_unknown"
        try:
            annotations = self.state.list_annotations_for_annotator(annotator_id)
        except Exception as exc:
            self.state.logger.error(f"my_annotations failed annotator={annotator_id}: {exc}")
            return self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"ok": False, "error": str(exc)},
            )
        self._send_json(HTTPStatus.OK, {"ok": True, "annotations": annotations})

    def _handle_annotation_detail(self, query: str) -> None:
        q = parse_qs(query)
        annotator_id = str(q.get("annotator_id", [""])[0]).strip() or "annotator_unknown"
        annotation_id = str(q.get("annotation_id", [""])[0]).strip()
        if not annotation_id:
            return self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "annotation_id is required"},
            )
        try:
            data = self.state.annotation_detail(annotator_id, annotation_id)
        except Exception as exc:
            self.state.logger.error(
                f"annotation_detail failed annotator={annotator_id} annotation_id={annotation_id}: {exc}"
            )
            return self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": str(exc)},
            )
        self._send_json(HTTPStatus.OK, {"ok": True, **data})

    def _handle_segment_detail(self, query: str) -> None:
        q = parse_qs(query)
        segment_id = str(q.get("segment_id", [""])[0]).strip()
        if not segment_id:
            return self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "segment_id is required"},
            )
        try:
            data = self.state.segment_detail(segment_id)
        except Exception as exc:
            self.state.logger.error(f"segment_detail failed segment_id={segment_id}: {exc}")
            return self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": str(exc)},
            )
        self._send_json(HTTPStatus.OK, {"ok": True, **data})

    def _send_json(self, status: HTTPStatus, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Segment-mode review service for stage-two annotation"
    )
    parser.add_argument(
        "--batch-dir",
        type=Path,
        required=True,
        help="Batch directory path, e.g. ./annotation/batch_20260305_v03",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Bind host, default 0.0.0.0",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=10086,
        help="Bind port, default 10086",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260305,
        help="Random seed for frame assignment",
    )
    parser.add_argument(
        "--reset-storage",
        action="store_true",
        help="Reset sqlite/file storage and start from clean state",
    )
    parser.add_argument(
        "--init-only",
        action="store_true",
        help="Initialize storage and exit without starting HTTP server",
    )
    parser.add_argument(
        "--frame-cache-disk",
        action="store_true",
        help="Enable on-disk JPEG cache under batch_dir/ui_tasks/frame_cache",
    )
    parser.add_argument(
        "--frame-cache-prewarm",
        action="store_true",
        help="Prewarm disk cache in background by decoding full videos",
    )
    parser.add_argument(
        "--frame-cache-prewarm-only",
        action="store_true",
        help="Prewarm disk cache in foreground then exit (requires --frame-cache-disk)",
    )
    parser.add_argument(
        "--frame-cache-max",
        type=int,
        default=256,
        help="In-memory LRU cache size for frames (0 to disable)",
    )
    parser.add_argument(
        "--frame-cache-jpeg-quality",
        type=int,
        default=88,
        help="JPEG quality for cached frames (1-100)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    batch_dir = resolve_repo_path(args.batch_dir)
    if not batch_dir.exists():
        raise SystemExit(f"batch directory does not exist: {batch_dir}")

    static_dir = (Path(__file__).resolve().parent / "web").resolve()
    if not args.init_only and not static_dir.exists():
        raise SystemExit(f"static directory does not exist: {static_dir}")
    if args.frame_cache_prewarm_only and not args.frame_cache_disk:
        raise SystemExit("--frame-cache-prewarm-only requires --frame-cache-disk")
    if args.frame_cache_prewarm_only and args.init_only:
        raise SystemExit("--frame-cache-prewarm-only should not be combined with --init-only")

    state = AnnotationState(
        batch_dir=batch_dir,
        static_dir=static_dir,
        seed=args.seed,
        reset_storage=args.reset_storage,
        frame_cache_dir=(batch_dir / "ui_tasks" / "frame_cache") if args.frame_cache_disk else None,
        frame_cache_prewarm=args.frame_cache_prewarm and not args.frame_cache_prewarm_only,
        frame_cache_max=args.frame_cache_max,
        frame_cache_quality=args.frame_cache_jpeg_quality,
    )
    state.initialize()

    if args.frame_cache_prewarm_only:
        state.prewarm_disk_cache_blocking()
        state.logger.info("frame cache prewarm-only done")
        state.close()
        return

    if args.init_only:
        state.logger.info("init-only done")
        state.close()
        return

    server = ThreadingHTTPServer((args.host, args.port), UiHandler)
    server.state = state  # type: ignore[attr-defined]
    state.logger.info(
        f"UI review server running at http://localhost:{args.port} "
        f"batch_dir={batch_dir}"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        state.logger.info("UI review server interrupted, shutting down")
    finally:
        server.server_close()
        state.close()


if __name__ == "__main__":
    main()
