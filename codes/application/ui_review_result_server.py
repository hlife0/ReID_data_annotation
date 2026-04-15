#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import itertools
import json
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

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TARGET_VIDEO_STEMS = [
    "20260211_171423",
    "20260211_171724",
    "20260211_172257",
    "20260211_172522",
]

DECISION_COLUMNS = [
    "decision_id",
    "video_stem",
    "frame_index",
    "timestamp_ms",
    "reviewer_id",
    "reviewed_at",
    "decision_type",
    "accepted_side",
    "left_annotation_id",
    "right_annotation_id",
    "candidate_dice",
    "p1_bbox_x",
    "p1_bbox_y",
    "p1_bbox_w",
    "p1_bbox_h",
    "p1_source",
    "p2_bbox_x",
    "p2_bbox_y",
    "p2_bbox_w",
    "p2_bbox_h",
    "p2_source",
]


def _now_human() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="milliseconds")


def _safe_float(value: Any) -> float:
    return float(f"{float(value):.3f}")


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


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
                raise ValueError(f"failed to decode frame {frame_index_1based} from {video_stem}")
            ok_encode, buf = cv2.imencode(
                ".jpg",
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality],
            )
            if not ok_encode:
                raise ValueError(f"failed to encode frame {frame_index_1based} from {video_stem}")
            return bytes(buf)

    def _ensure_open(self, video_stem: str) -> None:
        if video_stem in self._captures:
            return
        path = self._video_paths[video_stem]
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise ValueError(f"failed to open video: {path}")
        self._captures[video_stem] = cap
        self._locks[video_stem] = threading.Lock()
        self._meta[video_stem] = (
            int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )

    def close(self) -> None:
        for cap in self._captures.values():
            cap.release()
        self._captures.clear()
        self._locks.clear()
        self._meta.clear()


class ReviewResultState:
    def __init__(
        self,
        batch_dir: Path,
        static_dir: Path,
        frame_cache_max: int,
        frame_cache_quality: int,
    ) -> None:
        self.batch_dir = batch_dir
        self.static_dir = static_dir
        self.logs_dir = self.batch_dir / "logs"
        self.ui_task_dir = self.batch_dir / "ui_tasks"
        self.review_results_dir = self.batch_dir / "review_results"
        self.db_path = self.ui_task_dir / "ui_review.sqlite3"
        self.decisions_csv_path = self.review_results_dir / "review_decisions.csv"
        self.final_csv_path = self.review_results_dir / "final_reviewed.csv"
        self.logger = RunLogger(
            run_log_path=self.logs_dir / "run.log",
            error_log_path=self.logs_dir / "errors.log",
        )
        self._lock = threading.Lock()
        self._frame_cache: OrderedDict[Tuple[str, int], bytes] = OrderedDict()
        self._frame_cache_lock = threading.Lock()
        self._frame_cache_max = int(max(0, frame_cache_max))
        self.frame_cache_quality = frame_cache_quality

        self.reader: VideoFrameReader | None = None
        self.video_paths: Dict[str, Path] = {}
        self.frame_lookup: Dict[Tuple[str, int], FrameRecord] = {}
        self.review_queue: List[Tuple[str, int]] = []
        self.review_pairs: Dict[Tuple[str, int], Dict[str, Any]] = {}

    def initialize(self) -> None:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.review_results_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info("review-result service init start")
        self.video_paths = self._load_video_paths()
        self.frame_lookup = self._load_frame_lookup()
        self.reader = VideoFrameReader(self.video_paths, jpeg_quality=self.frame_cache_quality)
        self._init_database()
        self._build_review_pairs()
        self._export_final_csv()
        self.logger.info(
            f"review-result service init done review_frames={len(self.review_queue)} db={self.db_path}"
        )

    def close(self) -> None:
        if self.reader is not None:
            self.reader.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            str(self.db_path), timeout=30, isolation_level=None, check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _load_video_paths(self) -> Dict[str, Path]:
        manifest_path = self.batch_dir / "manifests" / "annotation_tasks.csv"
        if not manifest_path.exists():
            raise FileNotFoundError(f"manifest not found: {manifest_path}")
        paths: Dict[str, Path] = {}
        with manifest_path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                stem = row.get("video_stem", "").strip()
                if stem not in TARGET_VIDEO_STEMS:
                    continue
                raw = Path(row.get("video_path", "").strip())
                path = raw if raw.is_absolute() else (REPO_ROOT / raw)
                if path.exists():
                    paths[stem] = path
        missing = [stem for stem in TARGET_VIDEO_STEMS if stem not in paths]
        if missing:
            raise ValueError(f"manifest missing target stems: {missing}")
        return paths

    def _load_frame_lookup(self) -> Dict[Tuple[str, int], FrameRecord]:
        lookup: Dict[Tuple[str, int], FrameRecord] = {}
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT video_stem, frame_index, timestamp_ms FROM frames ORDER BY video_stem, frame_index"
            ).fetchall()
        finally:
            conn.close()
        for row in rows:
            rec = FrameRecord(
                video_stem=str(row["video_stem"]),
                frame_index=int(row["frame_index"]),
                timestamp_ms=float(row["timestamp_ms"]),
            )
            lookup[(rec.video_stem, rec.frame_index)] = rec
        return lookup

    def _init_database(self) -> None:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS review_decisions (
                    decision_id TEXT PRIMARY KEY,
                    video_stem TEXT NOT NULL,
                    frame_index INTEGER NOT NULL,
                    timestamp_ms REAL NOT NULL,
                    reviewer_id TEXT NOT NULL,
                    reviewed_at TEXT NOT NULL,
                    decision_type TEXT NOT NULL,
                    accepted_side TEXT NOT NULL,
                    left_annotation_id TEXT NOT NULL,
                    right_annotation_id TEXT NOT NULL,
                    candidate_dice REAL NOT NULL,
                    p1_bbox_x REAL NOT NULL,
                    p1_bbox_y REAL NOT NULL,
                    p1_bbox_w REAL NOT NULL,
                    p1_bbox_h REAL NOT NULL,
                    p1_source TEXT NOT NULL,
                    p2_bbox_x REAL NOT NULL,
                    p2_bbox_y REAL NOT NULL,
                    p2_bbox_w REAL NOT NULL,
                    p2_bbox_h REAL NOT NULL,
                    p2_source TEXT NOT NULL,
                    UNIQUE (video_stem, frame_index)
                );
                CREATE INDEX IF NOT EXISTS idx_review_decisions_reviewer
                ON review_decisions (reviewer_id);
                CREATE INDEX IF NOT EXISTS idx_review_decisions_frame
                ON review_decisions (video_stem, frame_index);
                """
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _load_annotation_rows(self) -> Dict[Tuple[str, int], List[sqlite3.Row]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT *
                FROM annotations
                WHERE video_stem IN ({})
                ORDER BY video_stem ASC, frame_index ASC, submitted_at ASC, annotation_id ASC
                """.format(
                    ",".join("?" * len(TARGET_VIDEO_STEMS))
                ),
                TARGET_VIDEO_STEMS,
            ).fetchall()
        finally:
            conn.close()
        grouped: Dict[Tuple[str, int], List[sqlite3.Row]] = {}
        for row in rows:
            grouped.setdefault((str(row["video_stem"]), int(row["frame_index"])), []).append(row)
        return grouped

    def _pair_slot_dice(self, row_a: sqlite3.Row, row_b: sqlite3.Row, slot: str) -> float:
        sa = str(row_a[f"{slot}_source"])
        sb = str(row_b[f"{slot}_source"])
        if sa == "absent" and sb == "absent":
            return 1.0
        if (sa == "absent") != (sb == "absent"):
            return 0.0
        ax, ay, aw, ah = [float(row_a[f"{slot}_bbox_{k}"]) for k in ("x", "y", "w", "h")]
        bx, by, bw, bh = [float(row_b[f"{slot}_bbox_{k}"]) for k in ("x", "y", "w", "h")]
        if aw <= 0 or ah <= 0 or bw <= 0 or bh <= 0:
            return 0.0
        ax2, ay2 = ax + aw, ay + ah
        bx2, by2 = bx + bw, by + bh
        ix1, iy1 = max(ax, bx), max(ay, by)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
        inter = iw * ih
        denom = aw * ah + bw * bh
        return 0.0 if denom <= 0 else (2.0 * inter / denom)

    def _pair_dice(self, row_a: sqlite3.Row, row_b: sqlite3.Row) -> float:
        return min(
            self._pair_slot_dice(row_a, row_b, "p1"),
            self._pair_slot_dice(row_a, row_b, "p2"),
        )

    def _annotation_payload(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "annotation_id": str(row["annotation_id"]),
            "annotator_id": str(row["annotator_id"]),
            "submitted_at": str(row["submitted_at"]),
            "p1": {
                "bbox_x": _safe_float(row["p1_bbox_x"]),
                "bbox_y": _safe_float(row["p1_bbox_y"]),
                "bbox_w": _safe_float(row["p1_bbox_w"]),
                "bbox_h": _safe_float(row["p1_bbox_h"]),
                "source": str(row["p1_source"]),
            },
            "p2": {
                "bbox_x": _safe_float(row["p2_bbox_x"]),
                "bbox_y": _safe_float(row["p2_bbox_y"]),
                "bbox_w": _safe_float(row["p2_bbox_w"]),
                "bbox_h": _safe_float(row["p2_bbox_h"]),
                "source": str(row["p2_source"]),
            },
        }

    def _build_review_pairs(self) -> None:
        annos_by_frame = self._load_annotation_rows()
        conn = self._connect()
        try:
            reviewed = {
                (str(r["video_stem"]), int(r["frame_index"]))
                for r in conn.execute("SELECT video_stem, frame_index FROM review_decisions").fetchall()
            }
        finally:
            conn.close()
        pairs: Dict[Tuple[str, int], Dict[str, Any]] = {}
        for key, rows in annos_by_frame.items():
            if key in reviewed or len(rows) < 2:
                continue
            best: Tuple[float, sqlite3.Row, sqlite3.Row] | None = None
            for row_a, row_b in itertools.combinations(rows, 2):
                dice = self._pair_dice(row_a, row_b)
                candidate = (
                    dice,
                    row_a,
                    row_b,
                )
                if best is None:
                    best = candidate
                    continue
                best_key = (
                    best[0],
                    str(best[1]["submitted_at"]),
                    str(best[1]["annotation_id"]),
                    str(best[2]["submitted_at"]),
                    str(best[2]["annotation_id"]),
                )
                cand_key = (
                    candidate[0],
                    str(candidate[1]["submitted_at"]),
                    str(candidate[1]["annotation_id"]),
                    str(candidate[2]["submitted_at"]),
                    str(candidate[2]["annotation_id"]),
                )
                if cand_key > best_key:
                    best = candidate
            if best is None:
                continue
            dice, row_a, row_b = best
            rec = self.frame_lookup.get(key)
            if rec is None:
                continue
            left = self._annotation_payload(row_a)
            right = self._annotation_payload(row_b)
            pairs[key] = {
                "video_stem": key[0],
                "frame_index": key[1],
                "timestamp_ms": _safe_float(rec.timestamp_ms),
                "candidate_dice": _safe_float(dice),
                "left": left,
                "right": right,
                "image_url": f"/api/frame_image?video_stem={key[0]}&frame_index={key[1]}",
            }
        self.review_pairs = pairs
        self.review_queue = sorted(
            pairs.keys(),
            key=lambda key: (pairs[key]["candidate_dice"], key[0], key[1]),
        )

    def _validate_person_payload(self, person: Any, slot: str) -> Dict[str, Any]:
        if not isinstance(person, dict):
            raise ValueError(f"{slot} payload missing")
        source = str(person.get("source", "")).strip()
        if source not in {"left_candidate", "right_candidate", "manual_draw", "manual_param", "absent"}:
            raise ValueError(f"{slot} invalid source")
        if source == "absent":
            return {
                f"{slot}_bbox_x": 0.0,
                f"{slot}_bbox_y": 0.0,
                f"{slot}_bbox_w": 0.0,
                f"{slot}_bbox_h": 0.0,
                f"{slot}_source": source,
            }
        x = _safe_float(person.get("bbox_x", 0.0))
        y = _safe_float(person.get("bbox_y", 0.0))
        w = _safe_float(person.get("bbox_w", 0.0))
        h = _safe_float(person.get("bbox_h", 0.0))
        if w <= 0 or h <= 0:
            raise ValueError(f"{slot} bbox must have w>0 and h>0")
        return {
            f"{slot}_bbox_x": x,
            f"{slot}_bbox_y": y,
            f"{slot}_bbox_w": w,
            f"{slot}_bbox_h": h,
            f"{slot}_source": source,
        }

    def _decision_payload_from_row(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "decision_id": str(row["decision_id"]),
            "video_stem": str(row["video_stem"]),
            "frame_index": int(row["frame_index"]),
            "timestamp_ms": _safe_float(row["timestamp_ms"]),
            "reviewer_id": str(row["reviewer_id"]),
            "reviewed_at": str(row["reviewed_at"]),
            "decision_type": str(row["decision_type"]),
            "accepted_side": str(row["accepted_side"]),
            "left_annotation_id": str(row["left_annotation_id"]),
            "right_annotation_id": str(row["right_annotation_id"]),
            "candidate_dice": _safe_float(row["candidate_dice"]),
            "p1": {
                "bbox_x": _safe_float(row["p1_bbox_x"]),
                "bbox_y": _safe_float(row["p1_bbox_y"]),
                "bbox_w": _safe_float(row["p1_bbox_w"]),
                "bbox_h": _safe_float(row["p1_bbox_h"]),
                "source": str(row["p1_source"]),
            },
            "p2": {
                "bbox_x": _safe_float(row["p2_bbox_x"]),
                "bbox_y": _safe_float(row["p2_bbox_y"]),
                "bbox_w": _safe_float(row["p2_bbox_w"]),
                "bbox_h": _safe_float(row["p2_bbox_h"]),
                "source": str(row["p2_source"]),
            },
        }

    def _export_final_csv(self) -> None:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM review_decisions ORDER BY video_stem, frame_index"
            ).fetchall()
        finally:
            conn.close()
        self.review_results_dir.mkdir(parents=True, exist_ok=True)
        with self.final_csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=DECISION_COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row[k] for k in DECISION_COLUMNS})
        with self.decisions_csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=DECISION_COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row[k] for k in DECISION_COLUMNS})

    def frame_image_bytes(self, video_stem: str, frame_index: int) -> bytes:
        if self.reader is None:
            raise RuntimeError("state not initialized")
        key = (video_stem, frame_index)
        with self._frame_cache_lock:
            if key in self._frame_cache:
                data = self._frame_cache.pop(key)
                self._frame_cache[key] = data
                return data
        image = self.reader.read_jpeg(video_stem, frame_index)
        with self._frame_cache_lock:
            self._frame_cache[key] = image
            while len(self._frame_cache) > self._frame_cache_max:
                self._frame_cache.popitem(last=False)
        return image

    def _pending_keys(self, conn: sqlite3.Connection) -> List[Tuple[str, int]]:
        reviewed = {
            (str(r["video_stem"]), int(r["frame_index"]))
            for r in conn.execute("SELECT video_stem, frame_index FROM review_decisions").fetchall()
        }
        return [key for key in self.review_queue if key not in reviewed]

    def status_summary(self) -> Dict[str, Any]:
        conn = self._connect()
        try:
            reviewed = conn.execute("SELECT COUNT(*) AS c FROM review_decisions").fetchone()["c"]
        finally:
            conn.close()
        total = len(self.review_queue)
        pending = max(0, total - int(reviewed or 0))
        return {
            "total_review_frames": total,
            "reviewed_frames": int(reviewed or 0),
            "pending_frames": pending,
            "port": 10088,
        }

    def next_sample(self, reviewer_id: str) -> Dict[str, Any]:
        with self._lock:
            conn = self._connect()
            try:
                pending = self._pending_keys(conn)
            finally:
                conn.close()
            if not pending:
                return {"done": True, "sample": None}
            key = pending[0]
            sample = dict(self.review_pairs[key])
            sample["done"] = False
            sample["reviewer_id"] = reviewer_id
            if self.reader is None:
                raise RuntimeError("state not initialized")
            width, height = self.reader.get_dimensions(sample["video_stem"])
            sample["image_width"] = width
            sample["image_height"] = height
            return {"done": False, "sample": sample}

    def _build_accept_record(self, reviewer_id: str, payload: Dict[str, Any], accepted_side: str) -> Dict[str, Any]:
        stem = str(payload.get("video_stem", "")).strip()
        frame_index = int(payload.get("frame_index", 0))
        key = (stem, frame_index)
        sample = self.review_pairs.get(key)
        if sample is None:
            raise ValueError("sample not found")
        chosen = sample[accepted_side]
        record = {
            "decision_id": f"rev_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}",
            "video_stem": stem,
            "frame_index": frame_index,
            "timestamp_ms": sample["timestamp_ms"],
            "reviewer_id": reviewer_id,
            "reviewed_at": _now_iso(),
            "decision_type": f"accept_{accepted_side}",
            "accepted_side": accepted_side,
            "left_annotation_id": sample["left"]["annotation_id"],
            "right_annotation_id": sample["right"]["annotation_id"],
            "candidate_dice": sample["candidate_dice"],
            "p1_bbox_x": chosen["p1"]["bbox_x"],
            "p1_bbox_y": chosen["p1"]["bbox_y"],
            "p1_bbox_w": chosen["p1"]["bbox_w"],
            "p1_bbox_h": chosen["p1"]["bbox_h"],
            "p1_source": f"{accepted_side}_candidate",
            "p2_bbox_x": chosen["p2"]["bbox_x"],
            "p2_bbox_y": chosen["p2"]["bbox_y"],
            "p2_bbox_w": chosen["p2"]["bbox_w"],
            "p2_bbox_h": chosen["p2"]["bbox_h"],
            "p2_source": f"{accepted_side}_candidate",
        }
        return record

    def accept_side(self, reviewer_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        accepted_side = str(payload.get("accepted_side", "")).strip()
        if accepted_side not in {"left", "right"}:
            raise ValueError("accepted_side must be left/right")
        record = self._build_accept_record(reviewer_id, payload, accepted_side)
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO review_decisions (
                        decision_id, video_stem, frame_index, timestamp_ms, reviewer_id, reviewed_at,
                        decision_type, accepted_side, left_annotation_id, right_annotation_id, candidate_dice,
                        p1_bbox_x, p1_bbox_y, p1_bbox_w, p1_bbox_h, p1_source,
                        p2_bbox_x, p2_bbox_y, p2_bbox_w, p2_bbox_h, p2_source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    tuple(record[col] for col in DECISION_COLUMNS),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
        self._export_final_csv()
        self.logger.info(
            f"review accept ok video={record['video_stem']} frame={record['frame_index']} side={accepted_side} reviewer={reviewer_id}"
        )
        return {"decision": record, **self.next_sample(reviewer_id)}

    def submit_redraw(self, reviewer_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        stem = str(payload.get("video_stem", "")).strip()
        frame_index = int(payload.get("frame_index", 0))
        key = (stem, frame_index)
        sample = self.review_pairs.get(key)
        if sample is None:
            raise ValueError("sample not found")
        p1 = self._validate_person_payload(payload.get("p1"), slot="p1")
        p2 = self._validate_person_payload(payload.get("p2"), slot="p2")
        record = {
            "decision_id": f"rev_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}",
            "video_stem": stem,
            "frame_index": frame_index,
            "timestamp_ms": sample["timestamp_ms"],
            "reviewer_id": reviewer_id,
            "reviewed_at": _now_iso(),
            "decision_type": "redraw",
            "accepted_side": "redraw",
            "left_annotation_id": sample["left"]["annotation_id"],
            "right_annotation_id": sample["right"]["annotation_id"],
            "candidate_dice": sample["candidate_dice"],
        }
        record.update(p1)
        record.update(p2)
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO review_decisions (
                        decision_id, video_stem, frame_index, timestamp_ms, reviewer_id, reviewed_at,
                        decision_type, accepted_side, left_annotation_id, right_annotation_id, candidate_dice,
                        p1_bbox_x, p1_bbox_y, p1_bbox_w, p1_bbox_h, p1_source,
                        p2_bbox_x, p2_bbox_y, p2_bbox_w, p2_bbox_h, p2_source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    tuple(record[col] for col in DECISION_COLUMNS),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
        self._export_final_csv()
        self.logger.info(
            f"review redraw ok video={record['video_stem']} frame={record['frame_index']} reviewer={reviewer_id}"
        )
        return {"decision": record, **self.next_sample(reviewer_id)}


class ReviewResultHandler(BaseHTTPRequestHandler):
    server_version = "UIReviewResultServer/1.0"

    @property
    def state(self) -> ReviewResultState:
        return self.server.state  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: Any) -> None:
        self.state.logger.info(f"review_http {self.address_string()} {fmt % args}")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/status":
            return self._send_json(HTTPStatus.OK, {"ok": True, "status": self.state.status_summary()})
        if path == "/api/frame_image":
            return self._handle_frame_image(parsed.query)
        if path == "/":
            return self._serve_static("index.html", "text/html; charset=utf-8")
        if path == "/styles.css":
            return self._serve_static("styles.css", "text/css; charset=utf-8")
        if path == "/app.js":
            return self._serve_static("app.js", "application/javascript; charset=utf-8")
        self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/review_next":
            return self._handle_review_next()
        if path == "/api/review_accept":
            return self._handle_review_accept()
        if path == "/api/review_redraw":
            return self._handle_review_redraw()
        self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def _read_json_payload(self) -> Dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except Exception:
            length = 0
        if length <= 0:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "request body is required"})
            return None
        body = self.rfile.read(length)
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid json body"})
            return None
        if not isinstance(payload, dict):
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "json body must be object"})
            return None
        return payload

    def _handle_frame_image(self, query: str) -> None:
        q = parse_qs(query)
        stem = str(q.get("video_stem", [""])[0]).strip()
        frame_raw = str(q.get("frame_index", ["0"])[0]).strip()
        try:
            frame_index = int(frame_raw)
            image = self.state.frame_image_bytes(stem, frame_index)
        except Exception as exc:
            return self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(image)))
        self.end_headers()
        self.wfile.write(image)

    def _handle_review_next(self) -> None:
        payload = self._read_json_payload()
        if payload is None:
            return
        reviewer_id = str(payload.get("reviewer_id", "")).strip() or "reviewer_unknown"
        try:
            result = self.state.next_sample(reviewer_id)
        except Exception as exc:
            return self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
        self._send_json(HTTPStatus.OK, {"ok": True, **result})

    def _handle_review_accept(self) -> None:
        payload = self._read_json_payload()
        if payload is None:
            return
        reviewer_id = str(payload.get("reviewer_id", "")).strip() or "reviewer_unknown"
        try:
            result = self.state.accept_side(reviewer_id, payload)
        except Exception as exc:
            return self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
        self._send_json(HTTPStatus.OK, {"ok": True, **result})

    def _handle_review_redraw(self) -> None:
        payload = self._read_json_payload()
        if payload is None:
            return
        reviewer_id = str(payload.get("reviewer_id", "")).strip() or "reviewer_unknown"
        try:
            result = self.state.submit_redraw(reviewer_id, payload)
        except Exception as exc:
            return self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
        self._send_json(HTTPStatus.OK, {"ok": True, **result})

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
    parser = argparse.ArgumentParser(description="Review UI for annotation result adjudication")
    parser.add_argument("--batch-dir", type=Path, required=True, help="Batch directory path, e.g. ./annotation/batch_20260314_v05")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=10088, help="Bind port")
    parser.add_argument("--frame-cache-max", type=int, default=256, help="In-memory frame cache size")
    parser.add_argument("--frame-cache-jpeg-quality", type=int, default=88, help="JPEG quality for served frames")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    batch_dir = resolve_repo_path(args.batch_dir)
    static_dir = (Path(__file__).resolve().parent / "ui_review_result_web").resolve()
    if not batch_dir.exists():
        raise SystemExit(f"batch directory does not exist: {batch_dir}")
    if not static_dir.exists():
        raise SystemExit(f"static directory does not exist: {static_dir}")
    state = ReviewResultState(
        batch_dir=batch_dir,
        static_dir=static_dir,
        frame_cache_max=args.frame_cache_max,
        frame_cache_quality=args.frame_cache_jpeg_quality,
    )
    state.initialize()
    server = ThreadingHTTPServer((args.host, args.port), ReviewResultHandler)
    server.state = state  # type: ignore[attr-defined]
    state.logger.info(f"review result server running at http://localhost:{args.port} batch_dir={batch_dir}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        state.logger.info("review result server interrupted, shutting down")
    finally:
        server.server_close()
        state.close()


if __name__ == "__main__":
    main()
