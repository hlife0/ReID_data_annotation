#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from process import process_segment_review_prep as base_prep
from process import segment_prep_common as common


MICRO_STABLE_MAX_FRAMES = 3


def _export_first_pass_segments(
    task: common.TaskInfo,
    detections: List[common.Detection],
) -> List[Dict[str, Any]]:
    timestamps = base_prep.load_frame_timestamps(Path(task.timestamp_path))
    by_frame = common.group_by_frame(detections)
    frame_states = [
        base_prep.classify_frame(
            frame_index,
            by_frame.get(frame_index, []),
            low_score_threshold=base_prep.DEFAULT_LOW_SCORE_THRESHOLD,
            high_overlap_iou=base_prep.DEFAULT_HIGH_OVERLAP_IOU,
        )
        for frame_index in timestamps
    ]
    simple_flags = base_prep.bridge_simple_flags(
        frame_states,
        bridge_low_score_gaps=False,
        max_gap_frames=2,
    )
    first_pass_segments = base_prep._first_pass_segments(task, frame_states, simple_flags)

    exported: List[Dict[str, Any]] = []
    for idx, segment in enumerate(first_pass_segments, start=1):
        exported.append(
            {
                "segment_id": f"{task.video_stem}_first_pass_{idx:06d}",
                "video_stem": task.video_stem,
                "segment_type": segment.segment_type,
                "start_frame": segment.start_frame,
                "end_frame": segment.end_frame,
                "representative_frame": segment.representative_frame,
                "track_ids": segment.track_ids,
                "frame_count": segment.frame_count,
            }
        )
    return exported


def _is_fragment(segment: Dict[str, Any]) -> bool:
    return segment["segment_type"] == "non_simple_single_frame" or (
        segment["segment_type"] == "stable_segment" and int(segment["frame_count"]) <= MICRO_STABLE_MAX_FRAMES
    )


def _clone_stage_1_segment(
    video_stem: str,
    index: int,
    source_segment: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "segment_id": f"{video_stem}_stage1_seg_{index:06d}",
        "video_stem": video_stem,
        "segment_type": source_segment["segment_type"],
        "start_frame": source_segment["start_frame"],
        "end_frame": source_segment["end_frame"],
        "representative_frame": source_segment["representative_frame"],
        "track_ids": source_segment["track_ids"],
        "frame_count": source_segment["frame_count"],
        "source_segment_ids": [source_segment["segment_id"]],
        "source_segment_types": [source_segment["segment_type"]],
    }


def _merge_fragment_runs(
    video_stem: str,
    first_pass_segments: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    idx = 0
    while idx < len(first_pass_segments):
        current = first_pass_segments[idx]
        if current["segment_type"] != "non_simple_single_frame":
            merged.append(_clone_stage_1_segment(video_stem, len(merged) + 1, current))
            idx += 1
            continue

        run_start = idx
        last_non_simple = idx
        cursor = idx + 1
        while cursor < len(first_pass_segments):
            candidate = first_pass_segments[cursor]
            span = int(candidate["end_frame"]) - int(first_pass_segments[run_start]["start_frame"]) + 1
            if span > base_prep.DEFAULT_MAX_REPAIR_WINDOW_FRAMES or not _is_fragment(candidate):
                break
            if candidate["segment_type"] == "non_simple_single_frame":
                last_non_simple = cursor
            cursor += 1

        if last_non_simple > run_start:
            source_segments = first_pass_segments[run_start : last_non_simple + 1]
            start_frame = int(source_segments[0]["start_frame"])
            end_frame = int(source_segments[-1]["end_frame"])
            merged.append(
                {
                    "segment_id": f"{video_stem}_stage1_seg_{len(merged) + 1:06d}",
                    "video_stem": video_stem,
                    "segment_type": "repair_window",
                    "start_frame": start_frame,
                    "end_frame": end_frame,
                    "representative_frame": base_prep.representative_frame(start_frame, end_frame),
                    "track_ids": sorted(
                        {
                            int(track_id)
                            for segment in source_segments
                            for track_id in segment["track_ids"]
                        }
                    ),
                    "frame_count": end_frame - start_frame + 1,
                    "source_segment_ids": [segment["segment_id"] for segment in source_segments],
                    "source_segment_types": [segment["segment_type"] for segment in source_segments],
                }
            )
            idx = last_non_simple + 1
            continue

        merged.append(_clone_stage_1_segment(video_stem, len(merged) + 1, current))
        idx += 1

    return merged


def _build_frame_map(
    video_stem: str,
    segments: List[Dict[str, Any]],
) -> Dict[str, Any]:
    frame_to_segment: Dict[str, str] = {}
    for segment in segments:
        for frame_index in range(int(segment["start_frame"]), int(segment["end_frame"]) + 1):
            frame_to_segment[str(frame_index)] = str(segment["segment_id"])
    return {
        "video_stem": video_stem,
        "frame_to_segment": frame_to_segment,
    }


def run_human_stage_1_prep(batch_dir: Path) -> Dict[str, Any]:
    batch_dir = batch_dir.resolve()
    output_dir = batch_dir / "human_stage_1_prep"
    output_dir.mkdir(parents=True, exist_ok=True)

    tasks = common.load_tasks(batch_dir)
    summary: Dict[str, Any] = {
        "batch_dir": str(batch_dir),
        "video_count": 0,
        "segment_count": 0,
        "stable_segment_count": 0,
        "non_simple_single_frame_count": 0,
        "repair_window_count": 0,
        "videos": [],
    }

    for task in tasks:
        if not task.pseudo_label_path.exists():
            continue
        detections = common.load_detections(task.pseudo_label_path)
        first_pass_segments = _export_first_pass_segments(task, detections)
        stage_1_segments = _merge_fragment_runs(task.video_stem, first_pass_segments)
        frame_map = _build_frame_map(task.video_stem, stage_1_segments)
        video_summary = {
            "video_stem": task.video_stem,
            "first_pass_segment_count": len(first_pass_segments),
            "segment_count": len(stage_1_segments),
            "stable_segment_count": sum(1 for item in stage_1_segments if item["segment_type"] == "stable_segment"),
            "non_simple_single_frame_count": sum(
                1 for item in stage_1_segments if item["segment_type"] == "non_simple_single_frame"
            ),
            "repair_window_count": sum(1 for item in stage_1_segments if item["segment_type"] == "repair_window"),
        }

        (output_dir / f"{task.video_stem}.segments.json").write_text(
            json.dumps(
                {
                    "video_stem": task.video_stem,
                    "first_pass_segments": first_pass_segments,
                    "segments": stage_1_segments,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (output_dir / f"{task.video_stem}.segment_frames.json").write_text(
            json.dumps(frame_map, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        summary["video_count"] += 1
        summary["segment_count"] += int(video_summary["segment_count"])
        summary["stable_segment_count"] += int(video_summary["stable_segment_count"])
        summary["non_simple_single_frame_count"] += int(video_summary["non_simple_single_frame_count"])
        summary["repair_window_count"] += int(video_summary["repair_window_count"])
        summary["videos"].append(video_summary)

    (output_dir / "human_stage_1_prep_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare human_stage_1 artifacts")
    parser.add_argument("--batch-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_human_stage_1_prep(args.batch_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
