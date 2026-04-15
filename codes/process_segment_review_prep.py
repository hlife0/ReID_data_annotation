#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import process_review_issue_prep as issue_prep


LOW_SCORE_THRESHOLD = issue_prep.LOW_SCORE_THRESHOLD
HIGH_OVERLAP_IOU = issue_prep.HIGH_OVERLAP_IOU


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


def load_frame_timestamps(csv_path: Path) -> Dict[int, float]:
    rows: Dict[int, float] = {}
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                frame_index = int(row["frame_index"])
                rows[frame_index] = round(float(row["timestamp_ms"]), 3)
            except Exception:
                continue
    return dict(sorted(rows.items()))


def is_simple_frame(items: List[issue_prep.Detection]) -> bool:
    if any(item.score < LOW_SCORE_THRESHOLD for item in items):
        return False
    for idx, det_a in enumerate(items):
        for det_b in items[idx + 1 :]:
            if issue_prep.iou_xywh(det_a, det_b) > HIGH_OVERLAP_IOU:
                return False
    return True


def representative_frame(start_frame: int, end_frame: int) -> int:
    return (start_frame + end_frame) // 2


def build_segments(task: issue_prep.TaskInfo, detections: List[issue_prep.Detection]) -> Dict[str, Any]:
    timestamps = load_frame_timestamps(Path(task.timestamp_path))
    by_frame = issue_prep.group_by_frame(detections)
    frame_indices = list(timestamps)
    segments: List[SegmentRecord] = []

    current_start: int | None = None
    current_track_ids: List[int] | None = None

    def flush_current(end_frame: int | None = None) -> None:
        nonlocal current_start, current_track_ids
        if current_start is None or current_track_ids is None or end_frame is None:
            current_start = None
            current_track_ids = None
            return
        start = current_start
        end = end_frame
        segments.append(
            SegmentRecord(
                segment_id="",
                video_stem=task.video_stem,
                segment_type="stable_segment",
                start_frame=start,
                end_frame=end,
                representative_frame=representative_frame(start, end),
                track_ids=list(current_track_ids),
                frame_count=end - start + 1,
            )
        )
        current_start = None
        current_track_ids = None

    for frame_index in frame_indices:
        items = by_frame.get(frame_index, [])
        track_ids = sorted(item.track_id for item in items)
        simple = is_simple_frame(items)
        if simple:
            if current_start is None:
                current_start = frame_index
                current_track_ids = track_ids
                continue
            if track_ids == current_track_ids:
                continue
            flush_current(frame_index - 1)
            current_start = frame_index
            current_track_ids = track_ids
            continue

        flush_current(frame_index - 1 if current_start is not None else None)
        segments.append(
            SegmentRecord(
                segment_id="",
                video_stem=task.video_stem,
                segment_type="non_simple_single_frame",
                start_frame=frame_index,
                end_frame=frame_index,
                representative_frame=frame_index,
                track_ids=track_ids,
                frame_count=1,
            )
        )

    flush_current(frame_indices[-1] if frame_indices else None)

    ordered = sorted(segments, key=lambda item: (item.start_frame, item.end_frame, item.segment_type))
    exported_segments: List[Dict[str, Any]] = []
    frame_to_segment: Dict[str, str] = {}
    for idx, segment in enumerate(ordered, start=1):
        segment_id = f"{task.video_stem}_seg_{idx:06d}"
        exported = {
            "segment_id": segment_id,
            "video_stem": segment.video_stem,
            "segment_type": segment.segment_type,
            "start_frame": segment.start_frame,
            "end_frame": segment.end_frame,
            "representative_frame": segment.representative_frame,
            "track_ids": segment.track_ids,
            "frame_count": segment.frame_count,
        }
        exported_segments.append(exported)
        for frame_index in range(segment.start_frame, segment.end_frame + 1):
            frame_to_segment[str(frame_index)] = segment_id

    stable_lengths = [item["frame_count"] for item in exported_segments if item["segment_type"] == "stable_segment"]
    return {
        "video_stem": task.video_stem,
        "segments": exported_segments,
        "segment_frames": {
            "video_stem": task.video_stem,
            "frame_to_segment": frame_to_segment,
        },
        "summary": {
            "segment_count": len(exported_segments),
            "stable_segment_count": sum(1 for item in exported_segments if item["segment_type"] == "stable_segment"),
            "non_simple_single_frame_count": sum(
                1 for item in exported_segments if item["segment_type"] == "non_simple_single_frame"
            ),
            "avg_stable_segment_length": round(sum(stable_lengths) / len(stable_lengths), 3) if stable_lengths else 0.0,
            "max_stable_segment_length": max(stable_lengths) if stable_lengths else 0,
        },
    }


def run_segment_review_prep(batch_dir: Path) -> Dict[str, Any]:
    batch_dir = batch_dir.resolve()
    segment_prep_dir = batch_dir / "segment_prep"
    segment_prep_dir.mkdir(parents=True, exist_ok=True)

    tasks = issue_prep.load_tasks(batch_dir)
    summary: Dict[str, Any] = {
        "batch_dir": str(batch_dir),
        "video_count": 0,
        "segment_count": 0,
        "stable_segment_count": 0,
        "non_simple_single_frame_count": 0,
        "avg_stable_segment_length": 0.0,
        "max_stable_segment_length": 0,
        "videos": [],
    }
    all_stable_lengths: List[int] = []

    for task in tasks:
        if not task.pseudo_label_path.exists():
            continue
        detections = issue_prep.load_detections(task.pseudo_label_path)
        payload = build_segments(task, detections)

        (segment_prep_dir / f"{task.video_stem}.segments.json").write_text(
            json.dumps(
                {
                    "video_stem": task.video_stem,
                    "segments": payload["segments"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (segment_prep_dir / f"{task.video_stem}.segment_frames.json").write_text(
            json.dumps(payload["segment_frames"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        summary["video_count"] += 1
        summary["segment_count"] += int(payload["summary"]["segment_count"])
        summary["stable_segment_count"] += int(payload["summary"]["stable_segment_count"])
        summary["non_simple_single_frame_count"] += int(payload["summary"]["non_simple_single_frame_count"])
        summary["max_stable_segment_length"] = max(
            int(summary["max_stable_segment_length"]),
            int(payload["summary"]["max_stable_segment_length"]),
        )
        for segment in payload["segments"]:
            if segment["segment_type"] == "stable_segment":
                all_stable_lengths.append(int(segment["frame_count"]))
        summary["videos"].append(
            {
                "video_stem": task.video_stem,
                **payload["summary"],
            }
        )

    summary["avg_stable_segment_length"] = (
        round(sum(all_stable_lengths) / len(all_stable_lengths), 3) if all_stable_lengths else 0.0
    )

    (segment_prep_dir / "segment_prep_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate segment-based review preparation artifacts")
    parser.add_argument(
        "--batch-dir",
        type=Path,
        required=True,
        help="Batch directory, e.g. ./annotation/batch_20260413_v01",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_segment_review_prep(args.batch_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
