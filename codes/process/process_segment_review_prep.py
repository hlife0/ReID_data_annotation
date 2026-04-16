#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from process import segment_prep_common as common


DEFAULT_LOW_SCORE_THRESHOLD = 0.6
DEFAULT_HIGH_OVERLAP_IOU = 0.25


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


@dataclass(frozen=True)
class FrameClassification:
    frame_index: int
    track_ids: tuple[int, ...]
    raw_simple: bool
    bad_reason: str


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


def is_simple_frame(
    items: List[common.Detection],
    low_score_threshold: float,
    high_overlap_iou: float,
) -> bool:
    if any(item.score < low_score_threshold for item in items):
        return False
    for idx, det_a in enumerate(items):
        for det_b in items[idx + 1 :]:
            if common.iou_xywh(det_a, det_b) > high_overlap_iou:
                return False
    return True


def classify_frame(
    frame_index: int,
    items: List[common.Detection],
    low_score_threshold: float,
    high_overlap_iou: float,
) -> FrameClassification:
    track_ids = tuple(sorted(item.track_id for item in items))
    low_score = any(item.score < low_score_threshold for item in items)
    high_overlap = False
    for idx, det_a in enumerate(items):
        for det_b in items[idx + 1 :]:
            if common.iou_xywh(det_a, det_b) > high_overlap_iou:
                high_overlap = True
                break
        if high_overlap:
            break

    if low_score and high_overlap:
        bad_reason = "both"
    elif low_score:
        bad_reason = "low_only"
    elif high_overlap:
        bad_reason = "overlap_only"
    else:
        bad_reason = "simple"

    return FrameClassification(
        frame_index=frame_index,
        track_ids=track_ids,
        raw_simple=(bad_reason == "simple"),
        bad_reason=bad_reason,
    )


def bridge_simple_flags(
    frames: List[FrameClassification],
    bridge_low_score_gaps: bool,
    max_gap_frames: int,
) -> Dict[int, bool]:
    simple_flags = {frame.frame_index: frame.raw_simple for frame in frames}
    if not bridge_low_score_gaps or max_gap_frames < 1:
        return simple_flags

    idx = 0
    while idx < len(frames):
        if frames[idx].raw_simple:
            idx += 1
            continue
        run_start = idx
        while idx + 1 < len(frames) and not frames[idx + 1].raw_simple:
            idx += 1
        run_end = idx
        run = frames[run_start : run_end + 1]

        if len(run) <= max_gap_frames and run_start > 0 and run_end + 1 < len(frames):
            left = frames[run_start - 1]
            right = frames[run_end + 1]
            if (
                left.raw_simple
                and right.raw_simple
                and left.track_ids == right.track_ids
                and all(frame.track_ids == left.track_ids for frame in run)
                and all(frame.bad_reason == "low_only" for frame in run)
            ):
                for frame in run:
                    simple_flags[frame.frame_index] = True

        idx += 1

    return simple_flags


def representative_frame(start_frame: int, end_frame: int) -> int:
    return (start_frame + end_frame) // 2


def build_segments(
    task: common.TaskInfo,
    detections: List[common.Detection],
    low_score_threshold: float,
    high_overlap_iou: float,
    bridge_low_score_gaps: bool,
    max_gap_frames: int,
) -> Dict[str, Any]:
    timestamps = load_frame_timestamps(Path(task.timestamp_path))
    by_frame = common.group_by_frame(detections)
    frame_indices = list(timestamps)
    segments: List[SegmentRecord] = []
    frame_states = [
        classify_frame(
            frame_index,
            by_frame.get(frame_index, []),
            low_score_threshold=low_score_threshold,
            high_overlap_iou=high_overlap_iou,
        )
        for frame_index in frame_indices
    ]
    simple_flags = bridge_simple_flags(
        frame_states,
        bridge_low_score_gaps=bridge_low_score_gaps,
        max_gap_frames=max_gap_frames,
    )

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

    for frame in frame_states:
        frame_index = frame.frame_index
        track_ids = list(frame.track_ids)
        simple = simple_flags.get(frame_index, frame.raw_simple)
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


def run_segment_review_prep(
    batch_dir: Path,
    low_score_threshold: float = DEFAULT_LOW_SCORE_THRESHOLD,
    high_overlap_iou: float = DEFAULT_HIGH_OVERLAP_IOU,
    bridge_low_score_gaps: bool = False,
    max_gap_frames: int = 2,
) -> Dict[str, Any]:
    batch_dir = batch_dir.resolve()
    segment_prep_dir = batch_dir / "segment_prep"
    segment_prep_dir.mkdir(parents=True, exist_ok=True)

    tasks = common.load_tasks(batch_dir)
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
        detections = common.load_detections(task.pseudo_label_path)
        payload = build_segments(
            task,
            detections,
            low_score_threshold=low_score_threshold,
            high_overlap_iou=high_overlap_iou,
            bridge_low_score_gaps=bridge_low_score_gaps,
            max_gap_frames=max_gap_frames,
        )

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
    parser.add_argument(
        "--low-score-threshold",
        type=float,
        default=DEFAULT_LOW_SCORE_THRESHOLD,
        help=f"Frames with any box score below this are non-simple (default: {DEFAULT_LOW_SCORE_THRESHOLD})",
    )
    parser.add_argument(
        "--high-overlap-iou",
        type=float,
        default=DEFAULT_HIGH_OVERLAP_IOU,
        help=f"Frames with any pair IoU above this are non-simple (default: {DEFAULT_HIGH_OVERLAP_IOU})",
    )
    parser.add_argument(
        "--bridge-low-score-gaps",
        action="store_true",
        help="Bridge short low-score-only bad runs when both sides stay simple with the same track set",
    )
    parser.add_argument(
        "--max-gap-frames",
        type=int,
        default=2,
        help="Maximum consecutive bad frames eligible for low-score gap bridging (default: 2)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_segment_review_prep(
        args.batch_dir,
        low_score_threshold=args.low_score_threshold,
        high_overlap_iou=args.high_overlap_iou,
        bridge_low_score_gaps=args.bridge_low_score_gaps,
        max_gap_frames=args.max_gap_frames,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
