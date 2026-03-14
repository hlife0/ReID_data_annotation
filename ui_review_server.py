#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import random
import sqlite3
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import parse_qs, urlparse

import cv2

TARGET_VIDEO_STEMS = [
    "20260211_171423",
    "20260211_171724",
    "20260211_172257",
    "20260211_172522",
]

FRAME_POOL_COLUMNS = ["video_stem", "frame_index", "timestamp_ms"]
COUNT_COLUMNS = ["video_stem", "frame_index", "timestamp_ms", "annotation_count"]
ASSIGNMENT_COLUMNS = [
    "assignment_id",
    "assigned_at",
    "annotator_id",
    "video_stem",
    "frame_index",
    "timestamp_ms",
    "count_before",
    "reason",
]
REVIEWED_COLUMNS = [
    "annotation_id",
    "video_stem",
    "frame_index",
    "timestamp_ms",
    "annotator_id",
    "submitted_at",
    "p1_bbox_x",
    "p1_bbox_y",
    "p1_bbox_w",
    "p1_bbox_h",
    "p1_source",
    "p1_ai_track_id",
    "p2_bbox_x",
    "p2_bbox_y",
    "p2_bbox_w",
    "p2_bbox_h",
    "p2_source",
    "p2_ai_track_id",
]


def _now_human() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="milliseconds")


def _safe_float(value: Any) -> float:
    return float(f"{float(value):.3f}")


@dataclass(frozen=True)
class FrameRecord:
    video_stem: str
    frame_index: int
    timestamp_ms: float


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
        self.assignment_log_path = self.ui_task_dir / "assignment_log.csv"
        self.db_path = self.ui_task_dir / "ui_review.sqlite3"

        self.logger = RunLogger(
            run_log_path=self.logs_dir / "run.log",
            error_log_path=self.logs_dir / "errors.log",
        )
        self._rng = random.Random(seed)
        self._lock = threading.Lock()
        self.reset_storage = reset_storage
        self.frame_cache_dir = frame_cache_dir
        self.frame_cache_prewarm = frame_cache_prewarm
        self.frame_cache_quality = frame_cache_quality

        self.video_paths: Dict[str, Path] = {}
        self.frame_pool: List[FrameRecord] = []
        self.frame_lookup: Dict[Tuple[str, int], FrameRecord] = {}
        self.ai_boxes: Dict[Tuple[str, int], List[Dict[str, float | int]]] = {}
        self.reader: VideoFrameReader | None = None
        self._frame_cache: OrderedDict[Tuple[str, int], bytes] = OrderedDict()
        self._frame_cache_lock = threading.Lock()
        self._frame_cache_max = int(max(0, frame_cache_max))

    def initialize(self) -> None:
        self.ui_task_dir.mkdir(parents=True, exist_ok=True)
        self.reviewed_raw_dir.mkdir(parents=True, exist_ok=True)
        self.reviewed_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        if self.reset_storage:
            self._reset_storage_artifacts()

        self.logger.info("UI review service init start")
        self.video_paths = self._load_manifest_video_paths()
        self.frame_pool = self._build_frame_pool()
        self.frame_lookup = {(r.video_stem, r.frame_index): r for r in self.frame_pool}
        self.ai_boxes = self._load_ai_boxes()
        self._init_review_files()
        self._init_database()
        self._sync_counts_csv_from_db()
        self._sync_assignment_log_csv_from_db()
        self.reader = VideoFrameReader(self.video_paths, jpeg_quality=self.frame_cache_quality)
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

    def assign_next_frame(self, annotator_id: str, reason: str) -> Dict[str, Any]:
        with self._lock:
            conn = self._connect()
            assignment_csv_row: Dict[str, Any] | None = None
            try:
                conn.execute("BEGIN IMMEDIATE")
                picked_row = self._pick_next_frame_row(conn)
                assignment, assignment_csv_row = self._create_and_insert_assignment(
                    conn=conn,
                    picked_row=picked_row,
                    annotator_id=annotator_id,
                    reason=reason,
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

            if assignment_csv_row is not None:
                self._append_assignment_csv_row(assignment_csv_row)
            return assignment

    def submit_and_assign_next(
        self,
        annotator_id: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        with self._lock:
            annotation_record = self._validate_and_build_record(annotator_id, payload)
            key = (annotation_record["video_stem"], int(annotation_record["frame_index"]))
            if key not in self.frame_lookup:
                raise ValueError("frame does not exist in frame pool, cannot submit annotation")

            count_after_submit = 0
            next_assignment: Dict[str, Any] | None = None
            next_assignment_csv_row: Dict[str, Any] | None = None

            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    """
                    SELECT annotation_count
                    FROM frame_counts
                    WHERE video_stem=? AND frame_index=?
                    """,
                    (key[0], key[1]),
                ).fetchone()
                if row is None:
                    raise ValueError("frame does not exist in database")
                before = int(row["annotation_count"])

                self._insert_annotation(conn, annotation_record)
                self._update_track_person_stats(conn, annotation_record)
                conn.execute(
                    """
                    UPDATE frame_counts
                    SET annotation_count = annotation_count + 1
                    WHERE video_stem=? AND frame_index=?
                    """,
                    (key[0], key[1]),
                )
                count_after_submit = before + 1

                picked_row = self._pick_next_frame_row(conn)
                next_assignment, next_assignment_csv_row = self._create_and_insert_assignment(
                    conn=conn,
                    picked_row=picked_row,
                    annotator_id=annotator_id,
                    reason="after_submit",
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

            self._append_jsonl_record(annotation_record)
            self._append_reviewed_csv(annotation_record)
            if next_assignment_csv_row is not None:
                self._append_assignment_csv_row(next_assignment_csv_row)
            self._sync_counts_csv_from_db()

            self.logger.info(
                "submit ok "
                f"annotation_id={annotation_record['annotation_id']} "
                f"video_stem={annotation_record['video_stem']} "
                f"frame_index={annotation_record['frame_index']} "
                f"count_after={count_after_submit}"
            )
            return {
                "submitted": {
                    "annotation_id": annotation_record["annotation_id"],
                    "video_stem": annotation_record["video_stem"],
                    "frame_index": annotation_record["frame_index"],
                    "count_after_submit": count_after_submit,
                },
                "next_frame": next_assignment,
            }

    def export_reviewed_csvs(self) -> Dict[str, int]:
        exported: Dict[str, int] = {}
        with self._lock:
            conn = self._connect()
            try:
                for stem in TARGET_VIDEO_STEMS:
                    rows = conn.execute(
                        """
                        SELECT
                            annotation_id,
                            video_stem,
                            frame_index,
                            timestamp_ms,
                            annotator_id,
                            submitted_at,
                            p1_bbox_x,
                            p1_bbox_y,
                            p1_bbox_w,
                            p1_bbox_h,
                            p1_source,
                            p1_ai_track_id,
                            p2_bbox_x,
                            p2_bbox_y,
                            p2_bbox_w,
                            p2_bbox_h,
                            p2_source,
                            p2_ai_track_id
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
        self.assignment_log_path.unlink(missing_ok=True)
        for stem in TARGET_VIDEO_STEMS:
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

                CREATE TABLE IF NOT EXISTS assignments (
                    assignment_id TEXT PRIMARY KEY,
                    assigned_at TEXT NOT NULL,
                    annotator_id TEXT NOT NULL,
                    video_stem TEXT NOT NULL,
                    frame_index INTEGER NOT NULL,
                    timestamp_ms REAL NOT NULL,
                    count_before INTEGER NOT NULL,
                    reason TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_assignments_annotator
                ON assignments (annotator_id);
                CREATE INDEX IF NOT EXISTS idx_assignments_frame
                ON assignments (video_stem, frame_index);

                CREATE TABLE IF NOT EXISTS annotations (
                    annotation_id TEXT PRIMARY KEY,
                    video_stem TEXT NOT NULL,
                    frame_index INTEGER NOT NULL,
                    timestamp_ms REAL NOT NULL,
                    annotator_id TEXT NOT NULL,
                    submitted_at TEXT NOT NULL,
                    p1_bbox_x REAL NOT NULL,
                    p1_bbox_y REAL NOT NULL,
                    p1_bbox_w REAL NOT NULL,
                    p1_bbox_h REAL NOT NULL,
                    p1_source TEXT NOT NULL,
                    p1_ai_track_id TEXT,
                    p2_bbox_x REAL NOT NULL,
                    p2_bbox_y REAL NOT NULL,
                    p2_bbox_w REAL NOT NULL,
                    p2_bbox_h REAL NOT NULL,
                    p2_source TEXT NOT NULL,
                    p2_ai_track_id TEXT
                );

                CREATE TABLE IF NOT EXISTS track_person_stats (
                    video_stem TEXT NOT NULL,
                    ai_track_id TEXT NOT NULL,
                    p1_count INTEGER NOT NULL DEFAULT 0,
                    p2_count INTEGER NOT NULL DEFAULT 0,
                    last_updated_at TEXT NOT NULL,
                    PRIMARY KEY (video_stem, ai_track_id)
                );

                CREATE INDEX IF NOT EXISTS idx_annotations_annotator
                ON annotations (annotator_id);
                CREATE INDEX IF NOT EXISTS idx_annotations_frame
                ON annotations (video_stem, frame_index);
                CREATE INDEX IF NOT EXISTS idx_annotations_submitted
                ON annotations (submitted_at);
                """
            )

            if self.reset_storage:
                conn.execute("DELETE FROM assignments")
                conn.execute("DELETE FROM annotations")
                conn.execute("DELETE FROM track_person_stats")
                conn.execute("DELETE FROM frame_counts")
                conn.execute("DELETE FROM frames")

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
                    conn.executescript(
                        """
                        WITH stats AS (
                            SELECT
                                video_stem,
                                p1_ai_track_id AS ai_track_id,
                                SUM(CASE WHEN p1_source != 'absent' AND p1_ai_track_id != '' THEN 1 ELSE 0 END) AS p1_count,
                                0 AS p2_count,
                                MAX(submitted_at) AS last_updated_at
                            FROM annotations
                            WHERE p1_ai_track_id IS NOT NULL
                              AND p1_ai_track_id != ''
                              AND p1_source != 'absent'
                            GROUP BY video_stem, p1_ai_track_id
                            UNION ALL
                            SELECT
                                video_stem,
                                p2_ai_track_id AS ai_track_id,
                                0 AS p1_count,
                                SUM(CASE WHEN p2_source != 'absent' AND p2_ai_track_id != '' THEN 1 ELSE 0 END) AS p2_count,
                                MAX(submitted_at) AS last_updated_at
                            FROM annotations
                            WHERE p2_ai_track_id IS NOT NULL
                              AND p2_ai_track_id != ''
                              AND p2_source != 'absent'
                            GROUP BY video_stem, p2_ai_track_id
                        )
                        INSERT INTO track_person_stats (
                            video_stem,
                            ai_track_id,
                            p1_count,
                            p2_count,
                            last_updated_at
                        )
                        SELECT
                            video_stem,
                            ai_track_id,
                            SUM(p1_count) AS p1_count,
                            SUM(p2_count) AS p2_count,
                            MAX(last_updated_at) AS last_updated_at
                        FROM stats
                        GROUP BY video_stem, ai_track_id
                        """
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _load_manifest_video_paths(self) -> Dict[str, Path]:
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"manifest not found: {self.manifest_path}")
        paths: Dict[str, Path] = {}
        with self.manifest_path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                stem = row.get("video_stem", "").strip()
                if stem not in TARGET_VIDEO_STEMS:
                    continue
                raw_video_path = Path(row.get("video_path", "").strip())
                video_path = (
                    raw_video_path
                    if raw_video_path.is_absolute()
                    else (Path.cwd() / raw_video_path)
                )
                if not video_path.exists():
                    raise FileNotFoundError(f"video path missing for {stem}: {video_path}")
                paths[stem] = video_path
        missing = [stem for stem in TARGET_VIDEO_STEMS if stem not in paths]
        if missing:
            raise ValueError(f"manifest missing target video stems: {missing}")
        return paths

    def _build_frame_pool(self) -> List[FrameRecord]:
        all_records: List[FrameRecord] = []
        for stem in TARGET_VIDEO_STEMS:
            ts_path = (
                Path.cwd()
                / "data"
                / "required"
                / stem
                / "video"
                / f"{stem}_frame_timestamps_retimed.csv"
            )
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
        for stem in TARGET_VIDEO_STEMS:
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

    def _init_review_files(self) -> None:
        for stem in TARGET_VIDEO_STEMS:
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

    def _sync_assignment_log_csv_from_db(self) -> None:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT
                    assignment_id,
                    assigned_at,
                    annotator_id,
                    video_stem,
                    frame_index,
                    timestamp_ms,
                    count_before,
                    reason
                FROM assignments
                ORDER BY assigned_at ASC, assignment_id ASC
                """
            ).fetchall()
        finally:
            conn.close()

        with self.assignment_log_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=ASSIGNMENT_COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "assignment_id": row["assignment_id"],
                        "assigned_at": row["assigned_at"],
                        "annotator_id": row["annotator_id"],
                        "video_stem": row["video_stem"],
                        "frame_index": int(row["frame_index"]),
                        "timestamp_ms": f"{float(row['timestamp_ms']):.3f}",
                        "count_before": int(row["count_before"]),
                        "reason": row["reason"],
                    }
                )

    def _append_assignment_csv_row(self, row: Dict[str, Any]) -> None:
        file_exists = self.assignment_log_path.exists()
        with self.assignment_log_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=ASSIGNMENT_COLUMNS)
            if not file_exists:
                writer.writeheader()
            writer.writerow({k: row.get(k, "") for k in ASSIGNMENT_COLUMNS})

    def _pick_next_frame_row(self, conn: sqlite3.Connection) -> sqlite3.Row:
        lt3_rows = conn.execute(
            """
            SELECT video_stem, frame_index, annotation_count
            FROM frame_counts
            WHERE annotation_count < 3
            """
        ).fetchall()

        if lt3_rows:
            return lt3_rows[self._rng.randrange(len(lt3_rows))]

        min_row = conn.execute("SELECT MIN(annotation_count) AS min_count FROM frame_counts").fetchone()
        if min_row is None or min_row["min_count"] is None:
            raise RuntimeError("frame pool is empty")
        min_count = int(min_row["min_count"])
        min_rows = conn.execute(
            """
            SELECT video_stem, frame_index, annotation_count
            FROM frame_counts
            WHERE annotation_count = ?
            """,
            (min_count,),
        ).fetchall()
        if not min_rows:
            raise RuntimeError("no candidate frame found")
        return min_rows[self._rng.randrange(len(min_rows))]

    def _build_recommendations(
        self,
        conn: sqlite3.Connection,
        video_stem: str,
        ai_boxes: List[Dict[str, float | int]],
    ) -> List[Dict[str, str]]:
        if not ai_boxes:
            return []
        raw_ids = {str(box.get("track_id")) for box in ai_boxes}
        track_ids = [tid for tid in raw_ids if tid and tid != "None"]
        if not track_ids:
            return []
        try:
            track_ids.sort(key=lambda x: int(float(x)))
        except Exception:
            track_ids.sort()

        placeholders = ",".join(["?"] * len(track_ids))
        rows = conn.execute(
            f"""
            SELECT ai_track_id, p1_count, p2_count
            FROM track_person_stats
            WHERE video_stem=? AND ai_track_id IN ({placeholders})
            """,
            [video_stem, *track_ids],
        ).fetchall()
        counts = {
            str(r["ai_track_id"]): (int(r["p1_count"]), int(r["p2_count"]))
            for r in rows
        }

        recommendations: List[Dict[str, str]] = []
        for tid in track_ids:
            if tid not in counts:
                continue
            p1c, p2c = counts[tid]
            if p1c == p2c:
                continue
            recommendations.append(
                {
                    "track_id": tid,
                    "recommended_person": "p1" if p1c > p2c else "p2",
                }
            )
        return recommendations

    def _create_and_insert_assignment(
        self,
        conn: sqlite3.Connection,
        picked_row: sqlite3.Row,
        annotator_id: str,
        reason: str,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        stem = str(picked_row["video_stem"])
        frame_index = int(picked_row["frame_index"])
        count_before = int(picked_row["annotation_count"])
        key = (stem, frame_index)
        if key not in self.frame_lookup:
            raise ValueError("picked frame not found in frame lookup")
        if self.reader is None:
            raise RuntimeError("state not initialized")

        rec = self.frame_lookup[key]
        assignment_id = f"asg_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
        assigned_at = _now_iso()

        conn.execute(
            """
            INSERT INTO assignments (
                assignment_id,
                assigned_at,
                annotator_id,
                video_stem,
                frame_index,
                timestamp_ms,
                count_before,
                reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                assignment_id,
                assigned_at,
                annotator_id,
                stem,
                frame_index,
                rec.timestamp_ms,
                count_before,
                reason,
            ),
        )

        width, height = self.reader.get_dimensions(stem)
        recommendations = self._build_recommendations(
            conn=conn,
            video_stem=stem,
            ai_boxes=self.ai_boxes.get(key, []),
        )
        payload = {
            "assignment_id": assignment_id,
            "video_stem": stem,
            "frame_index": frame_index,
            "timestamp_ms": _safe_float(rec.timestamp_ms),
            "annotation_count": count_before,
            "image_width": width,
            "image_height": height,
            "ai_boxes": self.ai_boxes.get(key, []),
            "recommendations": recommendations,
            "image_url": f"/api/frame_image?video_stem={stem}&frame_index={frame_index}",
        }

        csv_row = {
            "assignment_id": assignment_id,
            "assigned_at": assigned_at,
            "annotator_id": annotator_id,
            "video_stem": stem,
            "frame_index": frame_index,
            "timestamp_ms": f"{rec.timestamp_ms:.3f}",
            "count_before": count_before,
            "reason": reason,
        }
        return payload, csv_row

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
                p1_bbox_x,
                p1_bbox_y,
                p1_bbox_w,
                p1_bbox_h,
                p1_source,
                p1_ai_track_id,
                p2_bbox_x,
                p2_bbox_y,
                p2_bbox_w,
                p2_bbox_h,
                p2_source,
                p2_ai_track_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            tuple(record[k] for k in REVIEWED_COLUMNS),
        )

    def _update_track_person_stats(self, conn: sqlite3.Connection, record: Dict[str, Any]) -> None:
        updates: Dict[str, Dict[str, int]] = {}
        for slot in ("p1", "p2"):
            source = str(record.get(f"{slot}_source", ""))
            track_id = str(record.get(f"{slot}_ai_track_id", "") or "").strip()
            if source == "absent" or not track_id:
                continue
            entry = updates.setdefault(track_id, {"p1": 0, "p2": 0})
            entry[slot] += 1

        if not updates:
            return

        now = _now_iso()
        for track_id, inc in updates.items():
            conn.execute(
                """
                INSERT INTO track_person_stats (
                    video_stem,
                    ai_track_id,
                    p1_count,
                    p2_count,
                    last_updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(video_stem, ai_track_id) DO UPDATE SET
                    p1_count = p1_count + excluded.p1_count,
                    p2_count = p2_count + excluded.p2_count,
                    last_updated_at = excluded.last_updated_at
                """,
                (
                    record["video_stem"],
                    track_id,
                    inc["p1"],
                    inc["p2"],
                    now,
                ),
            )

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

        p1 = self._validate_person_payload(payload.get("p1"), slot="p1")
        p2 = self._validate_person_payload(payload.get("p2"), slot="p2")
        annotation_id = f"ann_{int(time.time() * 1000)}_{uuid.uuid4().hex[:10]}"
        record: Dict[str, Any] = {
            "annotation_id": annotation_id,
            "video_stem": stem,
            "frame_index": frame_index,
            "timestamp_ms": _safe_float(timestamp_ms),
            "annotator_id": annotator_id,
            "submitted_at": _now_iso(),
        }
        record.update(p1)
        record.update(p2)
        return record

    def _validate_person_payload(self, person: Any, slot: str) -> Dict[str, Any]:
        if not isinstance(person, dict):
            raise ValueError(f"{slot} payload is missing")
        source = str(person.get("source", "")).strip()
        if source not in {"ai", "manual_draw", "manual_param", "absent"}:
            raise ValueError(f"{slot} source must be one of ai/manual_draw/manual_param/absent")

        if source == "absent":
            return {
                f"{slot}_bbox_x": 0.0,
                f"{slot}_bbox_y": 0.0,
                f"{slot}_bbox_w": 0.0,
                f"{slot}_bbox_h": 0.0,
                f"{slot}_source": source,
                f"{slot}_ai_track_id": "",
            }

        x = _safe_float(person.get("bbox_x", 0.0))
        y = _safe_float(person.get("bbox_y", 0.0))
        w = _safe_float(person.get("bbox_w", 0.0))
        h = _safe_float(person.get("bbox_h", 0.0))
        if w <= 0 or h <= 0:
            raise ValueError(f"{slot} bbox must have w>0 and h>0")
        ai_track = person.get("ai_track_id", "")
        if ai_track in ("", None):
            ai_track_str = ""
        else:
            ai_track_str = str(int(float(ai_track)))
        return {
            f"{slot}_bbox_x": x,
            f"{slot}_bbox_y": y,
            f"{slot}_bbox_w": w,
            f"{slot}_bbox_h": h,
            f"{slot}_source": source,
            f"{slot}_ai_track_id": ai_track_str,
        }

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
        if path == "/api/next_frame":
            return self._handle_next_frame()
        if path == "/api/submit":
            return self._handle_submit()
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

    def _handle_next_frame(self) -> None:
        payload = self._read_json_payload()
        if payload is None:
            return
        annotator_id = str(payload.get("annotator_id", "")).strip() or "annotator_unknown"
        try:
            assignment = self.state.assign_next_frame(
                annotator_id=annotator_id,
                reason="manual_next",
            )
        except Exception as exc:
            self.state.logger.error(f"next frame failed annotator={annotator_id}: {exc}")
            return self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"ok": False, "error": str(exc)},
            )
        self._send_json(HTTPStatus.OK, {"ok": True, "frame": assignment})

    def _handle_submit(self) -> None:
        payload = self._read_json_payload()
        if payload is None:
            return
        annotator_id = str(payload.get("annotator_id", "")).strip() or "annotator_unknown"
        try:
            result = self.state.submit_and_assign_next(annotator_id=annotator_id, payload=payload)
        except Exception as exc:
            self.state.logger.error(f"submit failed annotator={annotator_id}: {exc}")
            return self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": str(exc)},
            )
        self._send_json(HTTPStatus.OK, {"ok": True, **result})

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
        description="UI dual-person annotation service for review stage"
    )
    parser.add_argument(
        "--batch-dir",
        type=Path,
        required=True,
        help="Batch directory path, e.g. ./batch_20260305_v03",
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
    batch_dir = args.batch_dir.resolve()
    if not batch_dir.exists():
        raise SystemExit(f"batch directory does not exist: {batch_dir}")

    static_dir = (Path(__file__).resolve().parent / "ui_review_web").resolve()
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
