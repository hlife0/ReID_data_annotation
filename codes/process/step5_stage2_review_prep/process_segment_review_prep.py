#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from process.shared import segment_prep_common as common


DEFAULT_LOW_SCORE_THRESHOLD = 0.6
DEFAULT_HIGH_OVERLAP_IOU = 0.25
DEFAULT_MAX_REPAIR_WINDOW_FRAMES = 10
DEFAULT_MIN_REPAIRABILITY_SCORE = 0.70
DEFAULT_MIN_FRAGMENTATION_SCORE = 6


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


@dataclass(frozen=True)
class FrameClassification:
    frame_index: int
    track_ids: tuple[int, ...]
    raw_simple: bool
    bad_reason: str


@dataclass(frozen=True)
class RepairWindowCandidate:
    start_segment_index: int
    end_segment_index: int
    start_frame: int
    end_frame: int
    frame_count: int
    track_ids: List[int]
    anchor_candidates: List[int]
    repairability_score: float
    fragmentation_score: int
    expected_gain: int
    trigger_reason: str

    @property
    def priority_score(self) -> float:
        return round(self.repairability_score * float(self.expected_gain), 6)


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


def _track_jaccard(left: tuple[int, ...], right: tuple[int, ...]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set and not right_set:
        return 1.0
    union = left_set | right_set
    if not union:
        return 1.0
    return len(left_set & right_set) / len(union)


def _frame_track_lookup(by_frame: Dict[int, List[common.Detection]]) -> Dict[int, Dict[int, common.Detection]]:
    lookup: Dict[int, Dict[int, common.Detection]] = {}
    for frame_index, detections in by_frame.items():
        lookup[frame_index] = {det.track_id: det for det in detections}
    return lookup


def _mean_same_track_iou(
    frame_states: List[FrameClassification],
    frame_track_lookup: Dict[int, Dict[int, common.Detection]],
) -> float:
    overlaps: List[float] = []
    for idx in range(len(frame_states) - 1):
        left = frame_states[idx]
        right = frame_states[idx + 1]
        left_tracks = frame_track_lookup.get(left.frame_index, {})
        right_tracks = frame_track_lookup.get(right.frame_index, {})
        common_tracks = sorted(set(left_tracks) & set(right_tracks))
        for track_id in common_tracks:
            overlaps.append(common.iou_xywh(left_tracks[track_id], right_tracks[track_id]))
    if not overlaps:
        return 0.0
    return round(sum(overlaps) / len(overlaps), 6)


def _has_hard_break(frame_states: List[FrameClassification]) -> bool:
    both_run = 0
    overlap_run = 0
    for idx, frame in enumerate(frame_states):
        if frame.bad_reason == "both":
            both_run += 1
        else:
            both_run = 0
        if frame.bad_reason == "overlap_only":
            overlap_run += 1
        else:
            overlap_run = 0
        if both_run >= 2 or overlap_run >= 3:
            return True
        if idx == 0:
            continue
        prev = frame_states[idx - 1]
        prev_tracks = set(prev.track_ids)
        cur_tracks = set(frame.track_ids)
        disappeared = prev_tracks - cur_tracks
        appeared = cur_tracks - prev_tracks
        if len(disappeared) > 1 or len(appeared) > 1:
            return True
        if abs(len(prev_tracks) - len(cur_tracks)) > 1:
            return True
    return False


def _fragmentation_score(segments: List[SegmentRecord]) -> int:
    non_simple_count = sum(1 for segment in segments if segment.segment_type == "non_simple_single_frame")
    micro_stable_count = sum(
        1 for segment in segments if segment.segment_type == "stable_segment" and segment.frame_count <= 3
    )
    boundary_count = max(0, len(segments) - 1)
    return 2 * non_simple_count + micro_stable_count + boundary_count


def _select_anchor_candidates(frame_states: List[FrameClassification]) -> List[int]:
    start_frame = frame_states[0].frame_index
    end_frame = frame_states[-1].frame_index
    frame_count = end_frame - start_frame + 1
    if frame_count <= 4:
        return sorted({start_frame, end_frame})

    midpoint = (start_frame + end_frame) / 2.0
    severity_rank = {"both": 3, "overlap_only": 2, "low_only": 1, "simple": 0}
    worst_frame = max(
        frame_states,
        key=lambda frame: (severity_rank.get(frame.bad_reason, 0), -abs(frame.frame_index - midpoint)),
    )
    if severity_rank.get(worst_frame.bad_reason, 0) == 0:
        worst_index = representative_frame(start_frame, end_frame)
    else:
        worst_index = worst_frame.frame_index
    return sorted({start_frame, worst_index, end_frame})


def _evaluate_repair_window_candidate(
    segments: List[SegmentRecord],
    frame_states: List[FrameClassification],
    simple_flags: Dict[int, bool],
    frame_track_lookup: Dict[int, Dict[int, common.Detection]],
) -> RepairWindowCandidate | None:
    if len(segments) < 3:
        return None
    start_frame = segments[0].start_frame
    end_frame = segments[-1].end_frame
    frame_count = end_frame - start_frame + 1
    if frame_count > DEFAULT_MAX_REPAIR_WINDOW_FRAMES:
        return None

    window_states = [frame for frame in frame_states if start_frame <= frame.frame_index <= end_frame]
    if len(window_states) < 2:
        return None
    if _has_hard_break(window_states):
        return None

    endpoint_track_jaccard = _track_jaccard(window_states[0].track_ids, window_states[-1].track_ids)
    adjacent_jaccards = [
        _track_jaccard(window_states[idx].track_ids, window_states[idx + 1].track_ids)
        for idx in range(len(window_states) - 1)
    ]
    if not adjacent_jaccards:
        return None
    adjacent_good_ratio = sum(1 for value in adjacent_jaccards if value >= 0.6) / len(adjacent_jaccards)
    mean_adjacent_track_jaccard = sum(adjacent_jaccards) / len(adjacent_jaccards)
    mean_same_track_iou = _mean_same_track_iou(window_states, frame_track_lookup)
    clean_frame_ratio = sum(1 for frame in window_states if simple_flags.get(frame.frame_index, False)) / len(window_states)

    if endpoint_track_jaccard < 0.6:
        return None
    if adjacent_good_ratio < 0.7:
        return None
    if mean_same_track_iou < 0.35:
        return None

    fragmentation_score = _fragmentation_score(segments)
    if fragmentation_score < DEFAULT_MIN_FRAGMENTATION_SCORE:
        return None

    repairability_score = round(
        0.35 * endpoint_track_jaccard
        + 0.35 * mean_adjacent_track_jaccard
        + 0.20 * mean_same_track_iou
        + 0.10 * clean_frame_ratio,
        6,
    )
    if repairability_score < DEFAULT_MIN_REPAIRABILITY_SCORE:
        return None

    anchor_candidates = _select_anchor_candidates(window_states)
    expected_gain = len(segments) - len(anchor_candidates)
    if expected_gain < 2:
        return None

    return RepairWindowCandidate(
        start_segment_index=-1,
        end_segment_index=-1,
        start_frame=start_frame,
        end_frame=end_frame,
        frame_count=frame_count,
        track_ids=list(window_states[0].track_ids),
        anchor_candidates=anchor_candidates,
        repairability_score=repairability_score,
        fragmentation_score=fragmentation_score,
        expected_gain=expected_gain,
        trigger_reason="fragment_cluster",
    )


def _is_small_fragment(segment: SegmentRecord) -> bool:
    return segment.segment_type == "non_simple_single_frame" or (
        segment.segment_type == "stable_segment" and segment.frame_count <= 3
    )


def _select_repair_windows(
    segments: List[SegmentRecord],
    frame_states: List[FrameClassification],
    simple_flags: Dict[int, bool],
    frame_track_lookup: Dict[int, Dict[int, common.Detection]],
) -> List[RepairWindowCandidate]:
    candidates: List[RepairWindowCandidate] = []
    for start_idx in range(len(segments)):
        if not _is_small_fragment(segments[start_idx]):
            continue
        for end_idx in range(start_idx + 2, len(segments)):
            window_segments = segments[start_idx : end_idx + 1]
            if not all(_is_small_fragment(item) for item in window_segments):
                break
            window_frame_count = window_segments[-1].end_frame - window_segments[0].start_frame + 1
            if window_frame_count > DEFAULT_MAX_REPAIR_WINDOW_FRAMES:
                break
            candidate = _evaluate_repair_window_candidate(
                window_segments,
                frame_states,
                simple_flags,
                frame_track_lookup,
            )
            if candidate is None:
                continue
            candidates.append(
                RepairWindowCandidate(
                    start_segment_index=start_idx,
                    end_segment_index=end_idx,
                    start_frame=candidate.start_frame,
                    end_frame=candidate.end_frame,
                    frame_count=candidate.frame_count,
                    track_ids=candidate.track_ids,
                    anchor_candidates=candidate.anchor_candidates,
                    repairability_score=candidate.repairability_score,
                    fragmentation_score=candidate.fragmentation_score,
                    expected_gain=candidate.expected_gain,
                    trigger_reason=candidate.trigger_reason,
                )
            )

    selected: List[RepairWindowCandidate] = []
    occupied_frames: set[int] = set()
    for candidate in sorted(
        candidates,
        key=lambda item: (-item.priority_score, item.start_frame, item.end_frame),
    ):
        frame_span = set(range(candidate.start_frame, candidate.end_frame + 1))
        if occupied_frames & frame_span:
            continue
        selected.append(candidate)
        occupied_frames.update(frame_span)
    return sorted(selected, key=lambda item: (item.start_frame, item.end_frame))


def _first_pass_segments(
    task: common.TaskInfo,
    frame_states: List[FrameClassification],
    simple_flags: Dict[int, bool],
) -> List[SegmentRecord]:
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

    flush_current(frame_states[-1].frame_index if frame_states else None)
    return sorted(segments, key=lambda item: (item.start_frame, item.end_frame, item.segment_type))


def _merge_repair_windows(
    task: common.TaskInfo,
    segments: List[SegmentRecord],
    selected_candidates: List[RepairWindowCandidate],
) -> List[SegmentRecord]:
    if not selected_candidates:
        return segments

    final_segments: List[SegmentRecord] = []
    idx = 0
    for candidate in selected_candidates:
        while idx < candidate.start_segment_index:
            final_segments.append(segments[idx])
            idx += 1
        final_segments.append(
            SegmentRecord(
                segment_id="",
                video_stem=task.video_stem,
                segment_type="repair_window",
                start_frame=candidate.start_frame,
                end_frame=candidate.end_frame,
                representative_frame=candidate.anchor_candidates[0],
                track_ids=candidate.track_ids,
                frame_count=candidate.frame_count,
                anchor_candidates=candidate.anchor_candidates,
                repairability_score=candidate.repairability_score,
                fragmentation_score=candidate.fragmentation_score,
                expected_gain=candidate.expected_gain,
                trigger_reason=candidate.trigger_reason,
            )
        )
        idx = candidate.end_segment_index + 1
    while idx < len(segments):
        final_segments.append(segments[idx])
        idx += 1
    return sorted(final_segments, key=lambda item: (item.start_frame, item.end_frame, item.segment_type))


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

    first_pass_segments = _first_pass_segments(task, frame_states, simple_flags)
    frame_track_lookup = _frame_track_lookup(by_frame)
    repair_candidates = _select_repair_windows(
        first_pass_segments,
        frame_states,
        simple_flags,
        frame_track_lookup,
    )
    ordered = _merge_repair_windows(task, first_pass_segments, repair_candidates)

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
        if segment.segment_type == "repair_window":
            exported.update(
                {
                    "anchor_candidates": segment.anchor_candidates,
                    "repairability_score": segment.repairability_score,
                    "fragmentation_score": segment.fragmentation_score,
                    "expected_gain": segment.expected_gain,
                    "trigger_reason": segment.trigger_reason,
                }
            )
        exported_segments.append(exported)
        for frame_index in range(segment.start_frame, segment.end_frame + 1):
            frame_to_segment[str(frame_index)] = segment_id

    stable_lengths = [item["frame_count"] for item in exported_segments if item["segment_type"] == "stable_segment"]
    repair_window_count = sum(1 for item in exported_segments if item["segment_type"] == "repair_window")
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
            "repair_window_count": repair_window_count,
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
        "repair_window_count": 0,
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
        summary["repair_window_count"] += int(payload["summary"].get("repair_window_count", 0))
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
