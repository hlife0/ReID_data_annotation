#!/usr/bin/env python3
from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List


@dataclass(frozen=True)
class TaskInfo:
    video_stem: str
    video_path: str
    timestamp_path: str
    imu_paths: List[str]
    status: str
    priority: int
    pseudo_label_path: Path


@dataclass(frozen=True)
class Detection:
    video_stem: str
    frame_index: int
    timestamp_ms: float
    track_id: int
    bbox_x: float
    bbox_y: float
    bbox_w: float
    bbox_h: float
    score: float

    @property
    def center_x(self) -> float:
        return self.bbox_x + self.bbox_w / 2.0

    @property
    def center_y(self) -> float:
        return self.bbox_y + self.bbox_h / 2.0


def _safe_float(value: Any) -> float:
    return round(float(value), 3)


def _safe_int(value: Any) -> int:
    return int(float(value))


def load_tasks(batch_dir: Path) -> List[TaskInfo]:
    manifest_path = batch_dir / "manifests" / "annotation_tasks.csv"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")

    tasks: List[TaskInfo] = []
    with manifest_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stem = str(row["video_stem"]).strip()
            pseudo_label_path = batch_dir / "pseudo_labels" / f"{stem}.auto.csv"
            tasks.append(
                TaskInfo(
                    video_stem=stem,
                    video_path=str(row.get("video_path", "")).strip(),
                    timestamp_path=str(row.get("timestamp_path", "")).strip(),
                    imu_paths=[p for p in str(row.get("imu_paths", "")).split(";") if p],
                    status=str(row.get("status", "")).strip(),
                    priority=_safe_int(row.get("priority", 0) or 0),
                    pseudo_label_path=pseudo_label_path,
                )
            )
    return tasks


def load_detections(csv_path: Path) -> List[Detection]:
    detections: List[Detection] = []
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                bbox_w = float(row["bbox_w"])
                bbox_h = float(row["bbox_h"])
                if bbox_w <= 0 or bbox_h <= 0:
                    continue
                detections.append(
                    Detection(
                        video_stem=str(row["video_stem"]),
                        frame_index=_safe_int(row["frame_index"]),
                        timestamp_ms=_safe_float(row["timestamp_ms"]),
                        track_id=_safe_int(row["track_id"]),
                        bbox_x=_safe_float(row["bbox_x"]),
                        bbox_y=_safe_float(row["bbox_y"]),
                        bbox_w=_safe_float(bbox_w),
                        bbox_h=_safe_float(bbox_h),
                        score=_safe_float(row.get("score", 0.0)),
                    )
                )
            except Exception:
                continue
    detections.sort(key=lambda item: (item.frame_index, item.track_id))
    return detections


def iou_xywh(a: Detection, b: Detection) -> float:
    ax1, ay1 = a.bbox_x, a.bbox_y
    ax2, ay2 = a.bbox_x + a.bbox_w, a.bbox_y + a.bbox_h
    bx1, by1 = b.bbox_x, b.bbox_y
    bx2, by2 = b.bbox_x + b.bbox_w, b.bbox_y + b.bbox_h
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter = inter_w * inter_h
    if inter <= 0:
        return 0.0
    union = a.bbox_w * a.bbox_h + b.bbox_w * b.bbox_h - inter
    return inter / union if union > 0 else 0.0


def group_by_track(detections: Iterable[Detection]) -> Dict[int, List[Detection]]:
    by_track: Dict[int, List[Detection]] = defaultdict(list)
    for det in detections:
        by_track[det.track_id].append(det)
    for items in by_track.values():
        items.sort(key=lambda item: item.frame_index)
    return dict(sorted(by_track.items()))


def group_by_frame(detections: Iterable[Detection]) -> Dict[int, List[Detection]]:
    by_frame: Dict[int, List[Detection]] = defaultdict(list)
    for det in detections:
        by_frame[det.frame_index].append(det)
    for items in by_frame.values():
        items.sort(key=lambda item: item.track_id)
    return dict(sorted(by_frame.items()))
