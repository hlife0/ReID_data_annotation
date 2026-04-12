#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

from prepare_capture_lib import (
    build_device_summaries,
    build_frame_timestamps,
    build_pair_overlap_intervals,
    choose_best_device_pair_from_summaries,
    clip_video_segment,
    filter_device_csv_to_window,
    hardlink_or_copy,
    normalize_imu_directory,
    parse_capture_stem_start_ms,
    probe_video,
    select_frame_range,
    slice_intervals_to_sessions,
    write_frame_timestamps_csv,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_VIDEO = Path("/home/hrli/mid-run/data/video_raw/mp4/20260410_195433.mp4")
DEFAULT_SOURCE_IMU_ROOT = Path(
    "/home/hrli/mid-run/data/imu_raw/inbox_from_fzliang/2026-04-10_from_fzliang_20260412_092814"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare raw capture assets into local required sessions for the annotation pipeline"
    )
    parser.add_argument("--source-video", type=Path, default=DEFAULT_SOURCE_VIDEO)
    parser.add_argument("--source-imu-root", type=Path, default=DEFAULT_SOURCE_IMU_ROOT)
    parser.add_argument("--staging-root", type=Path, default=REPO_ROOT / "staging")
    parser.add_argument("--timezone", type=str, default="Asia/Hong_Kong")
    parser.add_argument("--capture-date", type=str, default="")
    parser.add_argument("--fps", type=float, default=None, help="fallback FPS if ffprobe reports 0/0")
    parser.add_argument("--interval-gap-ms", type=int, default=1000)
    parser.add_argument("--pair-merge-gap-ms", type=int, default=5000)
    parser.add_argument("--session-seconds", type=int, default=60)
    parser.add_argument("--min-session-seconds", type=int, default=45)
    parser.add_argument("--max-sessions", type=int, default=0)
    parser.add_argument("--device-a", type=str, default="")
    parser.add_argument("--device-b", type=str, default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    source_video = args.source_video.resolve()
    source_imu_root = args.source_imu_root.resolve()
    staging_root = args.staging_root.resolve()

    if not source_video.exists():
        raise SystemExit(f"source video missing: {source_video}")
    if not source_imu_root.exists():
        raise SystemExit(f"source imu root missing: {source_imu_root}")

    capture_stem = source_video.stem
    capture_date = args.capture_date or f"{capture_stem[:4]}-{capture_stem[4:6]}-{capture_stem[6:8]}"
    video_start_ms = parse_capture_stem_start_ms(capture_stem, args.timezone)

    probed_video = probe_video(source_video, args.fps)
    video_info = replace(probed_video, start_ms=video_start_ms)
    frame_timestamps_ms = build_frame_timestamps(video_start_ms, video_info.frame_count, video_info.fps)
    video_end_ms = int(round(frame_timestamps_ms[-1]))

    imu_normalized_root = staging_root / "imu_normalized" / capture_date
    reports_root = staging_root / "reports"
    required_root = staging_root / "required"
    reports_root.mkdir(parents=True, exist_ok=True)
    required_root.mkdir(parents=True, exist_ok=True)

    normalized_files = normalize_imu_directory(
        source_root=source_imu_root,
        normalized_root=imu_normalized_root,
        capture_date=capture_date,
        timezone_name=args.timezone,
    )
    summaries = build_device_summaries(
        normalized_by_device_dir=imu_normalized_root / "by_device",
        gap_threshold_ms=args.interval_gap_ms,
    )

    if args.device_a and args.device_b:
        pair = choose_best_device_pair_from_summaries(
            {args.device_a: summaries[args.device_a], args.device_b: summaries[args.device_b]},
            video_start_ms,
            video_end_ms,
        )
    else:
        pair = choose_best_device_pair_from_summaries(summaries, video_start_ms, video_end_ms)

    overlap_intervals = build_pair_overlap_intervals(
        summaries=summaries,
        pair=pair,
        video_start_ms=video_start_ms,
        video_end_ms=video_end_ms,
        merge_gap_ms=args.pair_merge_gap_ms,
    )
    sessions = slice_intervals_to_sessions(
        intervals=overlap_intervals,
        session_length_ms=args.session_seconds * 1000,
        min_session_ms=args.min_session_seconds * 1000,
        timezone_name=args.timezone,
    )
    if args.max_sessions > 0:
        sessions = sessions[: args.max_sessions]
    if not sessions:
        raise SystemExit("no sessions produced from the chosen device pair")

    session_payloads: list[dict[str, object]] = []
    for session in sessions:
        video_dir = required_root / session.stem / "video"
        imu_dir = required_root / session.stem / "imu"
        video_dir.mkdir(parents=True, exist_ok=True)
        imu_dir.mkdir(parents=True, exist_ok=True)

        start_index, end_index = select_frame_range(frame_timestamps_ms, session.start_ms, session.end_ms)

        out_video = video_dir / f"{session.stem}.mp4"
        out_ts = video_dir / f"{session.stem}_frame_timestamps.csv"
        out_video_retimed = video_dir / f"{session.stem}_retimed.mp4"
        out_ts_retimed = video_dir / f"{session.stem}_frame_timestamps_retimed.csv"

        offset_seconds = max(0.0, (session.start_ms - video_start_ms) / 1000.0)
        duration_seconds = max(0.001, (session.end_ms - session.start_ms) / 1000.0)

        clip_video_segment(source_video, out_video, offset_seconds, duration_seconds)
        write_frame_timestamps_csv(out_ts, frame_timestamps_ms, start_index, end_index)
        hardlink_or_copy(out_video, out_video_retimed)
        hardlink_or_copy(out_ts, out_ts_retimed)

        imu_a_out = imu_dir / f"{session.stem}_{pair.device_a}.csv"
        imu_b_out = imu_dir / f"{session.stem}_{pair.device_b}.csv"
        imu_a_rows = filter_device_csv_to_window(
            summaries[pair.device_a].csv_path, imu_a_out, session.start_ms, session.end_ms
        )
        imu_b_rows = filter_device_csv_to_window(
            summaries[pair.device_b].csv_path, imu_b_out, session.start_ms, session.end_ms
        )

        session_payloads.append(
            {
                "session_stem": session.stem,
                "start_ms": session.start_ms,
                "end_ms": session.end_ms,
                "frame_start_index": start_index + 1,
                "frame_end_index": end_index + 1,
                "device_a": pair.device_a,
                "device_b": pair.device_b,
                "imu_a_rows": imu_a_rows,
                "imu_b_rows": imu_b_rows,
                "video_path": str(out_video),
                "timestamp_path": str(out_ts),
            }
        )

    summary_payload = {
        "source_video": str(source_video),
        "source_imu_root": str(source_imu_root),
        "capture_stem": capture_stem,
        "capture_date": capture_date,
        "timezone": args.timezone,
        "video": {
            "path": str(video_info.path),
            "start_ms": video_start_ms,
            "end_ms": video_end_ms,
            "fps": video_info.fps,
            "frame_count": video_info.frame_count,
            "duration_seconds": video_info.duration_seconds,
        },
        "normalized_files": {device_id: str(path) for device_id, path in normalized_files.items()},
        "devices": {
            device_id: {
                "csv_path": str(summary.csv_path),
                "rows": summary.rows,
                "first_ms": summary.first_ms,
                "last_ms": summary.last_ms,
                "intervals": summary.intervals,
            }
            for device_id, summary in summaries.items()
        },
        "chosen_pair": asdict(pair),
        "pair_overlap_intervals": overlap_intervals,
        "sessions": session_payloads,
        "required_root": str(required_root),
    }
    summary_path = reports_root / f"{capture_stem}.capture_prep_summary.json"
    summary_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"summary_path": str(summary_path), "num_sessions": len(session_payloads)}, indent=2))


if __name__ == "__main__":
    main()
