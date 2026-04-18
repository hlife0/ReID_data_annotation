#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

from process import process_segment_review_prep as base_prep
from process import segment_prep_common as common


@dataclass(frozen=True)
class FirstPassConfig:
    key: str
    low_score_threshold: float
    high_overlap_iou: float
    bridge_low_score_gaps: bool
    max_gap_frames: int

    @classmethod
    def default(cls) -> "FirstPassConfig":
        return cls(
            key="fp_default",
            low_score_threshold=base_prep.DEFAULT_LOW_SCORE_THRESHOLD,
            high_overlap_iou=base_prep.DEFAULT_HIGH_OVERLAP_IOU,
            bridge_low_score_gaps=False,
            max_gap_frames=2,
        )


@dataclass(frozen=True)
class SecondPassConfig:
    key: str
    micro_stable_max_frames: int
    max_repair_window_frames: int
    min_non_simple_segments: int

    @classmethod
    def default(cls) -> "SecondPassConfig":
        return cls(
            key="sp_default",
            micro_stable_max_frames=3,
            max_repair_window_frames=10,
            min_non_simple_segments=2,
        )


def default_first_pass_configs() -> List[FirstPassConfig]:
    return [
        FirstPassConfig("FP1", 0.40, 0.25, False, 2),
        FirstPassConfig("FP2", 0.40, 0.25, True, 2),
        FirstPassConfig("FP3", 0.50, 0.25, False, 2),
        FirstPassConfig("FP4", 0.50, 0.25, True, 2),
        FirstPassConfig("FP5", 0.60, 0.25, False, 2),
        FirstPassConfig("FP6", 0.60, 0.25, True, 2),
    ]


def default_second_pass_configs() -> List[SecondPassConfig]:
    return [
        SecondPassConfig("SP1", 1, 6, 2),
        SecondPassConfig("SP2", 2, 8, 2),
        SecondPassConfig("SP3", 3, 10, 2),
        SecondPassConfig("SP4", 4, 12, 2),
    ]


def load_total_frames(timestamp_path: Path) -> int:
    return len(base_prep.load_frame_timestamps(timestamp_path))


def _export_first_pass_segments(
    task: common.TaskInfo,
    detections: List[common.Detection],
    config: FirstPassConfig,
) -> List[Dict[str, Any]]:
    timestamps = base_prep.load_frame_timestamps(Path(task.timestamp_path))
    by_frame = common.group_by_frame(detections)
    frame_states = [
        base_prep.classify_frame(
            frame_index,
            by_frame.get(frame_index, []),
            low_score_threshold=config.low_score_threshold,
            high_overlap_iou=config.high_overlap_iou,
        )
        for frame_index in timestamps
    ]
    simple_flags = base_prep.bridge_simple_flags(
        frame_states,
        bridge_low_score_gaps=config.bridge_low_score_gaps,
        max_gap_frames=config.max_gap_frames,
    )
    first_pass_segments = base_prep._first_pass_segments(task, frame_states, simple_flags)

    exported: List[Dict[str, Any]] = []
    for idx, segment in enumerate(first_pass_segments, start=1):
        exported.append(
            {
                "segment_id": f"{task.video_stem}_{config.key.lower()}_first_pass_{idx:06d}",
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


def _is_fragment(segment: Dict[str, Any], micro_stable_max_frames: int) -> bool:
    return segment["segment_type"] == "non_simple_single_frame" or (
        segment["segment_type"] == "stable_segment" and int(segment["frame_count"]) <= micro_stable_max_frames
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
    config: SecondPassConfig,
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
        non_simple_count = 1
        cursor = idx + 1
        while cursor < len(first_pass_segments):
            candidate = first_pass_segments[cursor]
            span = int(candidate["end_frame"]) - int(first_pass_segments[run_start]["start_frame"]) + 1
            if span > config.max_repair_window_frames or not _is_fragment(
                candidate,
                micro_stable_max_frames=config.micro_stable_max_frames,
            ):
                break
            if candidate["segment_type"] == "non_simple_single_frame":
                last_non_simple = cursor
                non_simple_count += 1
            cursor += 1

        if non_simple_count >= config.min_non_simple_segments:
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


def _ratio(count: int, total_frames: int) -> float:
    if total_frames <= 0:
        return 0.0
    return round(count / total_frames, 8)


def _percent_text(ratio: float) -> str:
    return f"{ratio * 100:.4f}%"


def _first_pass_entry(config: FirstPassConfig, work_unit_count: int, total_frames: int) -> Dict[str, Any]:
    ratio = _ratio(work_unit_count, total_frames)
    return {
        "config": asdict(config),
        "work_unit_count": work_unit_count,
        "ratio": ratio,
        "ratio_pct": _percent_text(ratio),
    }


def _second_pass_entry(config: SecondPassConfig, work_unit_count: int, total_frames: int) -> Dict[str, Any]:
    ratio = _ratio(work_unit_count, total_frames)
    return {
        "config": asdict(config),
        "work_unit_count": work_unit_count,
        "ratio": ratio,
        "ratio_pct": _percent_text(ratio),
    }


def analyze_batch(
    batch_dir: Path,
    first_pass_configs: List[FirstPassConfig] | None = None,
    second_pass_configs: List[SecondPassConfig] | None = None,
    output_dir: Path | None = None,
) -> Dict[str, Any]:
    batch_dir = batch_dir.resolve()
    first_pass_configs = list(first_pass_configs or default_first_pass_configs())
    second_pass_configs = list(second_pass_configs or default_second_pass_configs())

    tasks = [task for task in common.load_tasks(batch_dir) if task.pseudo_label_path.exists()]
    total_frames = sum(load_total_frames(Path(task.timestamp_path)) for task in tasks)

    first_pass_results: Dict[str, Dict[str, Any]] = {}
    second_pass_results: Dict[str, Dict[str, Any]] = {
        config.key: {"config": asdict(config)} for config in second_pass_configs
    }

    counts_by_first_pass: Dict[str, int] = {config.key: 0 for config in first_pass_configs}
    counts_by_second_pass: Dict[str, Dict[str, int]] = {
        second_config.key: {first_config.key: 0 for first_config in first_pass_configs}
        for second_config in second_pass_configs
    }

    for task in tasks:
        detections = common.load_detections(task.pseudo_label_path)
        for first_config in first_pass_configs:
            first_pass_segments = _export_first_pass_segments(task, detections, first_config)
            counts_by_first_pass[first_config.key] += len(first_pass_segments)
            for second_config in second_pass_configs:
                second_pass_segments = _merge_fragment_runs(
                    task.video_stem,
                    first_pass_segments,
                    second_config,
                )
                counts_by_second_pass[second_config.key][first_config.key] += len(second_pass_segments)

    for first_config in first_pass_configs:
        first_pass_results[first_config.key] = _first_pass_entry(
            first_config,
            counts_by_first_pass[first_config.key],
            total_frames,
        )

    for second_config in second_pass_configs:
        for first_config in first_pass_configs:
            second_pass_results[second_config.key][first_config.key] = _second_pass_entry(
                second_config,
                counts_by_second_pass[second_config.key][first_config.key],
                total_frames,
            )

    result: Dict[str, Any] = {
        "batch_dir": str(batch_dir),
        "video_count": len(tasks),
        "total_frames": total_frames,
        "first_pass_order": [config.key for config in first_pass_configs],
        "second_pass_order": [config.key for config in second_pass_configs],
        "first_pass": first_pass_results,
        "second_pass": second_pass_results,
        "output_dir": None,
    }

    if output_dir is not None:
        output_dir = output_dir.resolve()
        write_outputs(result, output_dir)
        result["output_dir"] = str(output_dir)

    return result


def write_outputs(result: Dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.md").write_text(build_summary_markdown(result), encoding="utf-8")
    write_first_pass_csv(result, output_dir / "first_pass_summary.csv")
    write_second_pass_csv(result, output_dir / "second_pass_grid.csv")
    (output_dir / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def write_first_pass_csv(result: Dict[str, Any], csv_path: Path) -> None:
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "first_pass_key",
                "work_unit_count",
                "ratio",
                "ratio_pct",
                "low_score_threshold",
                "high_overlap_iou",
                "bridge_low_score_gaps",
                "max_gap_frames",
            ],
        )
        writer.writeheader()
        for first_key in result["first_pass_order"]:
            entry = result["first_pass"][first_key]
            config = entry["config"]
            writer.writerow(
                {
                    "first_pass_key": first_key,
                    "work_unit_count": entry["work_unit_count"],
                    "ratio": entry["ratio"],
                    "ratio_pct": entry["ratio_pct"],
                    "low_score_threshold": config["low_score_threshold"],
                    "high_overlap_iou": config["high_overlap_iou"],
                    "bridge_low_score_gaps": config["bridge_low_score_gaps"],
                    "max_gap_frames": config["max_gap_frames"],
                }
            )


def write_second_pass_csv(result: Dict[str, Any], csv_path: Path) -> None:
    fieldnames = ["second_pass_key"] + list(result["first_pass_order"])
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for second_key in result["second_pass_order"]:
            row = {"second_pass_key": second_key}
            for first_key in result["first_pass_order"]:
                row[first_key] = result["second_pass"][second_key][first_key]["ratio_pct"]
            writer.writerow(row)


def build_summary_markdown(result: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Human Stage 1 Segmentation Grid Summary")
    lines.append("")
    lines.append(f"- Batch: `{result['batch_dir']}`")
    lines.append(f"- Video Count: {result['video_count']}")
    lines.append(f"- Total Frames: {result['total_frames']}")
    lines.append("")
    lines.append("## First-Pass Work Unit Ratios")
    lines.append("")
    lines.append("| First-Pass | Work Units | Ratio |")
    lines.append("|---|---:|---:|")
    for first_key in result["first_pass_order"]:
        entry = result["first_pass"][first_key]
        lines.append(f"| `{first_key}` | {entry['work_unit_count']} | {entry['ratio_pct']} |")
    lines.append("")
    lines.append("## Second-Pass Work Unit Ratios")
    lines.append("")
    header = "| Second-Pass | " + " | ".join(f"`{first_key}`" for first_key in result["first_pass_order"]) + " |"
    separator = "|---|" + "|".join("---:" for _ in result["first_pass_order"]) + "|"
    lines.append(header)
    lines.append(separator)
    for second_key in result["second_pass_order"]:
        row_values = [
            result["second_pass"][second_key][first_key]["ratio_pct"]
            for first_key in result["first_pass_order"]
        ]
        lines.append("| `{}` | {} |".format(second_key, " | ".join(row_values)))
    lines.append("")
    lines.append("## Configuration Legend")
    lines.append("")
    for first_key in result["first_pass_order"]:
        config = result["first_pass"][first_key]["config"]
        lines.append(
            "- `{}`: low_score={}, overlap_iou={}, bridge_low_score_gaps={}, max_gap_frames={}".format(
                first_key,
                config["low_score_threshold"],
                config["high_overlap_iou"],
                config["bridge_low_score_gaps"],
                config["max_gap_frames"],
            )
        )
    for second_key in result["second_pass_order"]:
        config = result["second_pass"][second_key]["config"]
        lines.append(
            "- `{}`: micro_stable_max_frames={}, max_repair_window_frames={}, min_non_simple_segments={}".format(
                second_key,
                config["micro_stable_max_frames"],
                config["max_repair_window_frames"],
                config["min_non_simple_segments"],
            )
        )
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze human_stage_1 segmentation parameter grids")
    parser.add_argument("--batch-dir", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional output directory. Defaults to <batch>/analysis/human_stage_1_segmentation_grid",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir
    if output_dir is None:
        output_dir = args.batch_dir / "analysis" / "human_stage_1_segmentation_grid"
    result = analyze_batch(
        batch_dir=args.batch_dir,
        output_dir=output_dir,
    )
    print(json.dumps({"output_dir": result["output_dir"], "total_frames": result["total_frames"]}, indent=2))


if __name__ == "__main__":
    main()
