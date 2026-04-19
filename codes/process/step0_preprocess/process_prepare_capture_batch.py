#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import replace
from pathlib import Path

from process.step0_preprocess.prepare_capture_lib import (
    build_segment_session,
    build_device_summaries,
    build_frame_timestamps,
    hardlink_or_copy,
    normalize_segment_directory,
    parse_capture_stem_start_ms,
    probe_video,
    select_frame_range,
    discover_raw_segment_dirs,
    filter_device_csv_to_window,
    write_frame_timestamps_csv,
)


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
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

    segment_dirs = discover_raw_segment_dirs(source_imu_root)
    if args.max_sessions > 0:
        segment_dirs = segment_dirs[: args.max_sessions]

    all_normalized_files: dict[str, dict[str, str]] = {}
    session_payloads: list[dict[str, object]] = []

    for segment_dir in segment_dirs:
        normalized_segment_root = imu_normalized_root / "segments" / segment_dir.name
        normalize_segment_directory(
            segment_root=segment_dir,
            normalized_root=normalized_segment_root,
            capture_date=capture_date,
            timezone_name=args.timezone,
        )
        summaries = build_device_summaries(
            normalized_by_device_dir=normalized_segment_root / "by_device",
            gap_threshold_ms=args.interval_gap_ms,
        )
        all_normalized_files[segment_dir.name] = {device_id: str(summary.csv_path) for device_id, summary in summaries.items()}

        segment_start_ms = min(summary.first_ms for summary in summaries.values())
        segment_end_ms = max(summary.last_ms for summary in summaries.values())
        session = build_segment_session(
            capture_stem=capture_stem,
            raw_segment_name=segment_dir.name,
            segment_start_ms=segment_start_ms,
            segment_end_ms=segment_end_ms,
            video_start_ms=video_start_ms,
            video_end_ms=video_end_ms,
        )
        if session is None:
            continue

        session_root = required_root / session.stem
        if session_root.exists():
            shutil.rmtree(session_root)
        video_dir = session_root / "video"
        imu_dir = session_root / "imu"
        video_dir.mkdir(parents=True, exist_ok=True)
        imu_dir.mkdir(parents=True, exist_ok=True)

        start_index, end_index = select_frame_range(frame_timestamps_ms, session.start_ms, session.end_ms)
        out_video = video_dir / f"{session.stem}.mp4"
        out_ts = video_dir / f"{session.stem}_frame_timestamps.csv"
        out_video_retimed = video_dir / f"{session.stem}_retimed.mp4"
        out_ts_retimed = video_dir / f"{session.stem}_frame_timestamps_retimed.csv"

        offset_seconds = max(0.0, (session.start_ms - video_start_ms) / 1000.0)
        duration_seconds = max(0.001, (session.end_ms - session.start_ms) / 1000.0)
        from process.step0_preprocess.prepare_capture_lib import clip_video_segment  # local import to keep CLI wiring simple
        clip_video_segment(source_video, out_video, offset_seconds, duration_seconds)
        write_frame_timestamps_csv(out_ts, frame_timestamps_ms, start_index, end_index)
        hardlink_or_copy(out_video, out_video_retimed)
        hardlink_or_copy(out_ts, out_ts_retimed)

        imu_rows_by_device: dict[str, int] = {}
        exported_devices: list[str] = []
        for device_id, summary in sorted(summaries.items()):
            imu_out = imu_dir / f"{session.stem}_{device_id}.csv"
            kept = filter_device_csv_to_window(summary.csv_path, imu_out, session.start_ms, session.end_ms)
            if kept <= 0:
                continue
            exported_devices.append(device_id)
            imu_rows_by_device[device_id] = kept

        if not exported_devices:
            shutil.rmtree(session_root)
            continue

        session_payloads.append(
            {
                "raw_segment_name": segment_dir.name,
                "session_stem": session.stem,
                "start_ms": session.start_ms,
                "end_ms": session.end_ms,
                "frame_start_index": start_index + 1,
                "frame_end_index": end_index + 1,
                "active_devices": exported_devices,
                "imu_rows_by_device": imu_rows_by_device,
                "video_path": str(out_video),
                "timestamp_path": str(out_ts),
            }
        )

    if not session_payloads:
        raise SystemExit("no segment-backed sessions overlapped with the video window")

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
        "normalized_segments": all_normalized_files,
        "session_source_intervals": [[payload["start_ms"], payload["end_ms"]] for payload in session_payloads],
        "sessions": session_payloads,
        "required_root": str(required_root),
    }
    summary_path = reports_root / f"{capture_stem}.capture_prep_summary.json"
    summary_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"summary_path": str(summary_path), "num_sessions": len(session_payloads)}, indent=2))


if __name__ == "__main__":
    main()
