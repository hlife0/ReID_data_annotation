#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


LOW_SCORE_THRESHOLD = 0.6
HIGH_OVERLAP_IOU = 0.25
LARGE_JUMP_DISTANCE = 40.0
SEGMENT_EDGE_FRAMES = 15
SPAN_MERGE_GAP = 2
GREEN_QA_SAMPLE_RATE = 0.1

ISSUE_POOL_COLUMNS = [
    "issue_id",
    "video_stem",
    "severity",
    "review_policy",
    "qa_sampled",
    "priority_score",
    "start_frame",
    "end_frame",
    "start_timestamp_ms",
    "end_timestamp_ms",
    "frame_count",
    "primary_track_ids",
    "reason_codes",
    "min_score",
    "max_overlap_iou",
    "max_jump_distance",
    "imu_count",
]


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


def build_track_summary(task: TaskInfo, detections: List[Detection]) -> Dict[str, Any]:
    by_track = group_by_track(detections)
    track_items: List[Dict[str, Any]] = []

    for track_id, items in by_track.items():
        jump_distances: List[float] = []
        max_gap = 0
        for prev, cur in zip(items, items[1:]):
            dx = cur.center_x - prev.center_x
            dy = cur.center_y - prev.center_y
            jump_distances.append(round(math.hypot(dx, dy), 3))
            max_gap = max(max_gap, cur.frame_index - prev.frame_index)
        scores = [item.score for item in items]
        areas = [round(item.bbox_w * item.bbox_h, 3) for item in items]
        track_items.append(
            {
                "track_id": track_id,
                "sample_count": len(items),
                "start_frame": items[0].frame_index,
                "end_frame": items[-1].frame_index,
                "start_timestamp_ms": items[0].timestamp_ms,
                "end_timestamp_ms": items[-1].timestamp_ms,
                "avg_score": round(sum(scores) / len(scores), 3),
                "min_score": round(min(scores), 3),
                "max_score": round(max(scores), 3),
                "avg_bbox_area": round(sum(areas) / len(areas), 3),
                "max_frame_gap": max_gap,
                "max_jump_distance": round(max(jump_distances) if jump_distances else 0.0, 3),
                "jump_event_count": sum(1 for d in jump_distances if d >= LARGE_JUMP_DISTANCE),
                "low_score_count": sum(1 for s in scores if s < LOW_SCORE_THRESHOLD),
            }
        )

    total_frames = len(group_by_frame(detections))
    max_simultaneous_tracks = 0
    for frame_items in group_by_frame(detections).values():
        max_simultaneous_tracks = max(max_simultaneous_tracks, len(frame_items))

    return {
        "video_stem": task.video_stem,
        "video_path": task.video_path,
        "timestamp_path": task.timestamp_path,
        "imu_count": len(task.imu_paths),
        "imu_paths": task.imu_paths,
        "pseudo_label_path": str(task.pseudo_label_path),
        "frame_count": total_frames,
        "track_count": len(track_items),
        "max_simultaneous_tracks": max_simultaneous_tracks,
        "tracks": track_items,
    }


def collect_frame_risk_metrics(detections: List[Detection]) -> Dict[int, Dict[str, Any]]:
    by_frame = group_by_frame(detections)
    by_track = group_by_track(detections)
    metrics: Dict[int, Dict[str, Any]] = {}
    frame_indices = sorted(by_frame)
    if not frame_indices:
        return metrics

    first_frame = frame_indices[0]
    last_frame = frame_indices[-1]

    for frame_index, items in by_frame.items():
        metrics[frame_index] = {
            "frame_index": frame_index,
            "timestamp_ms": items[0].timestamp_ms,
            "reason_codes": set(),
            "track_ids": set(),
            "min_score": min(item.score for item in items),
            "max_overlap_iou": 0.0,
            "max_jump_distance": 0.0,
            "detection_count": len(items),
        }

        if metrics[frame_index]["min_score"] < LOW_SCORE_THRESHOLD:
            metrics[frame_index]["reason_codes"].add("low_score")

        if frame_index - first_frame < SEGMENT_EDGE_FRAMES or last_frame - frame_index < SEGMENT_EDGE_FRAMES:
            metrics[frame_index]["reason_codes"].add("segment_edge")

        for i, det_a in enumerate(items):
            metrics[frame_index]["track_ids"].add(det_a.track_id)
            for det_b in items[i + 1 :]:
                overlap = iou_xywh(det_a, det_b)
                if overlap > metrics[frame_index]["max_overlap_iou"]:
                    metrics[frame_index]["max_overlap_iou"] = round(overlap, 3)
                if overlap >= HIGH_OVERLAP_IOU:
                    metrics[frame_index]["reason_codes"].add("high_overlap")

    prev_count: int | None = None
    for frame_index in frame_indices:
        cur_count = int(metrics[frame_index]["detection_count"])
        if prev_count is not None and cur_count != prev_count:
            metrics[frame_index]["reason_codes"].add("count_change")
        prev_count = cur_count

    for track_id, items in by_track.items():
        metrics[items[0].frame_index]["reason_codes"].add("track_boundary")
        metrics[items[-1].frame_index]["reason_codes"].add("track_boundary")
        metrics[items[0].frame_index]["track_ids"].add(track_id)
        metrics[items[-1].frame_index]["track_ids"].add(track_id)
        for prev, cur in zip(items, items[1:]):
            jump_distance = round(math.hypot(cur.center_x - prev.center_x, cur.center_y - prev.center_y), 3)
            if jump_distance >= LARGE_JUMP_DISTANCE:
                metrics[cur.frame_index]["reason_codes"].add("bbox_jump")
                metrics[cur.frame_index]["track_ids"].add(track_id)
                if jump_distance > metrics[cur.frame_index]["max_jump_distance"]:
                    metrics[cur.frame_index]["max_jump_distance"] = jump_distance
            else:
                metrics[cur.frame_index]["max_jump_distance"] = max(
                    metrics[cur.frame_index]["max_jump_distance"],
                    jump_distance,
                )
    return metrics


def severity_for_reasons(reason_codes: set[str]) -> str:
    red_reasons = {"low_score", "high_overlap", "bbox_jump"}
    return "red" if reason_codes & red_reasons else "yellow"


def priority_for_reasons(reason_codes: set[str], min_score: float, max_overlap_iou: float, max_jump_distance: float) -> float:
    score = 0.0
    weights = {
        "low_score": 4.0,
        "high_overlap": 4.0,
        "bbox_jump": 4.0,
        "count_change": 2.0,
        "track_boundary": 1.0,
        "segment_edge": 1.0,
    }
    for code in reason_codes:
        score += weights.get(code, 0.5)
    score += round(max(0.0, LOW_SCORE_THRESHOLD - min_score) * 5.0, 3)
    score += round(max_overlap_iou * 3.0, 3)
    score += round(max_jump_distance / 25.0, 3)
    return round(score, 3)


def build_green_spans(task: TaskInfo, detections: List[Detection], metrics: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_frame = group_by_frame(detections)
    green_spans: List[Dict[str, Any]] = []
    current: Dict[str, Any] | None = None
    for frame_index, items in sorted(by_frame.items()):
        item = metrics.get(frame_index)
        if item is None or item["reason_codes"]:
            if current is not None:
                green_spans.append(current)
                current = None
            continue

        track_ids = {det.track_id for det in items}
        if current is None or frame_index != current["end_frame"] + 1:
            if current is not None:
                green_spans.append(current)
            current = {
                "start_frame": frame_index,
                "end_frame": frame_index,
                "start_timestamp_ms": item["timestamp_ms"],
                "end_timestamp_ms": item["timestamp_ms"],
                "reason_codes": {"stable_segment"},
                "track_ids": track_ids,
                "min_score": item["min_score"],
                "max_overlap_iou": item["max_overlap_iou"],
                "max_jump_distance": item["max_jump_distance"],
                "frame_count": 1,
            }
            continue

        current["end_frame"] = frame_index
        current["end_timestamp_ms"] = item["timestamp_ms"]
        current["track_ids"].update(track_ids)
        current["min_score"] = min(current["min_score"], item["min_score"])
        current["max_overlap_iou"] = max(current["max_overlap_iou"], item["max_overlap_iou"])
        current["max_jump_distance"] = max(current["max_jump_distance"], item["max_jump_distance"])
        current["frame_count"] += 1

    if current is not None:
        green_spans.append(current)

    exported: List[Dict[str, Any]] = []
    for span in green_spans:
        exported.append(
            {
                "issue_id": "",
                "video_stem": task.video_stem,
                "severity": "green",
                "review_policy": "auto_pass",
                "qa_sampled": False,
                "priority_score": 0.0,
                "start_frame": int(span["start_frame"]),
                "end_frame": int(span["end_frame"]),
                "start_timestamp_ms": _safe_float(span["start_timestamp_ms"]),
                "end_timestamp_ms": _safe_float(span["end_timestamp_ms"]),
                "frame_count": int(span["frame_count"]),
                "primary_track_ids": sorted(int(v) for v in span["track_ids"]),
                "reason_codes": ["stable_segment"],
                "min_score": _safe_float(span["min_score"]),
                "max_overlap_iou": _safe_float(span["max_overlap_iou"]),
                "max_jump_distance": _safe_float(span["max_jump_distance"]),
                "imu_count": len(task.imu_paths),
            }
        )
    return exported


def sample_green_spans(spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not spans:
        return []
    sample_count = max(1, int(round(len(spans) * GREEN_QA_SAMPLE_RATE)))
    sample_count = min(sample_count, len(spans))
    if sample_count == 1:
        indices = {len(spans) // 2}
    else:
        indices = {
            round(i * (len(spans) - 1) / (sample_count - 1))
            for i in range(sample_count)
        }
    sampled: List[Dict[str, Any]] = []
    for idx, span in enumerate(spans):
        if idx not in indices:
            continue
        copied = dict(span)
        copied["review_policy"] = "qa_sample"
        copied["qa_sampled"] = True
        sampled.append(copied)
    return sampled


def merge_risk_spans(task: TaskInfo, detections: List[Detection]) -> Dict[str, Any]:
    metrics = collect_frame_risk_metrics(detections)
    risk_frames = [
        data for _, data in sorted(metrics.items()) if data["reason_codes"]
    ]
    spans: List[Dict[str, Any]] = []

    current: Dict[str, Any] | None = None
    for item in risk_frames:
        if current is None:
            current = {
                "start_frame": item["frame_index"],
                "end_frame": item["frame_index"],
                "start_timestamp_ms": item["timestamp_ms"],
                "end_timestamp_ms": item["timestamp_ms"],
                "reason_codes": set(item["reason_codes"]),
                "track_ids": set(item["track_ids"]),
                "min_score": item["min_score"],
                "max_overlap_iou": item["max_overlap_iou"],
                "max_jump_distance": item["max_jump_distance"],
                "frame_count": 1,
            }
            continue

        if item["frame_index"] - current["end_frame"] <= SPAN_MERGE_GAP:
            current["end_frame"] = item["frame_index"]
            current["end_timestamp_ms"] = item["timestamp_ms"]
            current["reason_codes"].update(item["reason_codes"])
            current["track_ids"].update(item["track_ids"])
            current["min_score"] = min(current["min_score"], item["min_score"])
            current["max_overlap_iou"] = max(current["max_overlap_iou"], item["max_overlap_iou"])
            current["max_jump_distance"] = max(current["max_jump_distance"], item["max_jump_distance"])
            current["frame_count"] += 1
        else:
            spans.append(current)
            current = {
                "start_frame": item["frame_index"],
                "end_frame": item["frame_index"],
                "start_timestamp_ms": item["timestamp_ms"],
                "end_timestamp_ms": item["timestamp_ms"],
                "reason_codes": set(item["reason_codes"]),
                "track_ids": set(item["track_ids"]),
                "min_score": item["min_score"],
                "max_overlap_iou": item["max_overlap_iou"],
                "max_jump_distance": item["max_jump_distance"],
                "frame_count": 1,
            }
    if current is not None:
        spans.append(current)

    exported_spans: List[Dict[str, Any]] = []
    for idx, span in enumerate(spans, start=1):
        reason_codes = set(span["reason_codes"])
        exported_spans.append(
            {
                "issue_id": "",
                "video_stem": task.video_stem,
                "severity": severity_for_reasons(reason_codes),
                "review_policy": "focus_review",
                "qa_sampled": False,
                "priority_score": priority_for_reasons(
                    reason_codes,
                    float(span["min_score"]),
                    float(span["max_overlap_iou"]),
                    float(span["max_jump_distance"]),
                ),
                "start_frame": int(span["start_frame"]),
                "end_frame": int(span["end_frame"]),
                "start_timestamp_ms": _safe_float(span["start_timestamp_ms"]),
                "end_timestamp_ms": _safe_float(span["end_timestamp_ms"]),
                "frame_count": int(span["frame_count"]),
                "primary_track_ids": sorted(int(v) for v in span["track_ids"]),
                "reason_codes": sorted(reason_codes),
                "min_score": _safe_float(span["min_score"]),
                "max_overlap_iou": _safe_float(span["max_overlap_iou"]),
                "max_jump_distance": _safe_float(span["max_jump_distance"]),
                "imu_count": len(task.imu_paths),
            }
        )

    green_spans = build_green_spans(task, detections, metrics)
    sampled_green_spans = sample_green_spans(green_spans)

    review_issue_pool = list(exported_spans) + sampled_green_spans
    review_issue_pool.sort(key=lambda item: (-float(item["priority_score"]), int(item["start_frame"])))
    for idx, span in enumerate(review_issue_pool, start=1):
        span["issue_id"] = f"{task.video_stem}_issue_{idx:03d}"

    all_spans = list(exported_spans) + green_spans
    all_spans.sort(key=lambda item: (int(item["start_frame"]), int(item["end_frame"])))

    severity_counts: Dict[str, int] = defaultdict(int)
    for span in all_spans:
        severity_counts[str(span["severity"])] += 1

    return {
        "video_stem": task.video_stem,
        "pseudo_label_path": str(task.pseudo_label_path),
        "summary": {
            "risk_span_count": len(all_spans),
            "review_issue_count": len(review_issue_pool),
            "severity_counts": dict(severity_counts),
            "auto_pass_span_count": max(0, len(green_spans) - len(sampled_green_spans)),
            "qa_sample_span_count": len(sampled_green_spans),
            "frame_count": len(group_by_frame(detections)),
            "track_count": len(group_by_track(detections)),
        },
        "risk_spans": all_spans,
        "issue_pool": review_issue_pool,
    }


def write_issue_pool_csv(path: Path, spans: List[Dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ISSUE_POOL_COLUMNS)
        writer.writeheader()
        for span in spans:
            writer.writerow(
                {
                    "issue_id": span["issue_id"],
                    "video_stem": span["video_stem"],
                    "severity": span["severity"],
                    "review_policy": span.get("review_policy", "focus_review"),
                    "qa_sampled": "1" if span.get("qa_sampled") else "0",
                    "priority_score": f"{float(span['priority_score']):.3f}",
                    "start_frame": int(span["start_frame"]),
                    "end_frame": int(span["end_frame"]),
                    "start_timestamp_ms": f"{float(span['start_timestamp_ms']):.3f}",
                    "end_timestamp_ms": f"{float(span['end_timestamp_ms']):.3f}",
                    "frame_count": int(span["frame_count"]),
                    "primary_track_ids": ";".join(str(v) for v in span["primary_track_ids"]),
                    "reason_codes": ";".join(span["reason_codes"]),
                    "min_score": f"{float(span['min_score']):.3f}",
                    "max_overlap_iou": f"{float(span['max_overlap_iou']):.3f}",
                    "max_jump_distance": f"{float(span['max_jump_distance']):.3f}",
                    "imu_count": int(span["imu_count"]),
                }
            )


def run_review_issue_prep(batch_dir: Path) -> Dict[str, Any]:
    batch_dir = batch_dir.resolve()
    review_prep_dir = batch_dir / "review_prep"
    review_prep_dir.mkdir(parents=True, exist_ok=True)

    tasks = load_tasks(batch_dir)
    summary = {
        "batch_dir": str(batch_dir),
        "video_count": 0,
        "issue_count": 0,
        "severity_counts": {},
        "auto_pass_span_count": 0,
        "qa_sample_span_count": 0,
        "videos": [],
    }
    batch_severity_counts: Dict[str, int] = defaultdict(int)

    for task in tasks:
        if not task.pseudo_label_path.exists():
            continue
        detections = load_detections(task.pseudo_label_path)
        track_summary = build_track_summary(task, detections)
        risk_spans = merge_risk_spans(task, detections)

        (review_prep_dir / f"{task.video_stem}.track_summary.json").write_text(
            json.dumps(track_summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (review_prep_dir / f"{task.video_stem}.risk_spans.json").write_text(
            json.dumps(risk_spans, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        write_issue_pool_csv(
            review_prep_dir / f"{task.video_stem}.issue_pool.csv",
            risk_spans["issue_pool"],
        )

        summary["video_count"] += 1
        summary["issue_count"] += len(risk_spans["issue_pool"])
        summary["auto_pass_span_count"] += int(risk_spans["summary"].get("auto_pass_span_count", 0))
        summary["qa_sample_span_count"] += int(risk_spans["summary"].get("qa_sample_span_count", 0))
        for key, value in risk_spans["summary"].get("severity_counts", {}).items():
            batch_severity_counts[str(key)] += int(value or 0)
        summary["videos"].append(
            {
                "video_stem": task.video_stem,
                "track_count": track_summary["track_count"],
                "issue_count": len(risk_spans["issue_pool"]),
                "imu_count": len(task.imu_paths),
                "severity_counts": risk_spans["summary"].get("severity_counts", {}),
                "auto_pass_span_count": int(risk_spans["summary"].get("auto_pass_span_count", 0)),
                "qa_sample_span_count": int(risk_spans["summary"].get("qa_sample_span_count", 0)),
            }
        )

    summary["severity_counts"] = dict(batch_severity_counts)

    (review_prep_dir / "review_prep_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate review issue preparation artifacts")
    parser.add_argument(
        "--batch-dir",
        type=Path,
        required=True,
        help="Batch directory, e.g. ./annotation/batch_20260413_v01",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_review_issue_prep(args.batch_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
