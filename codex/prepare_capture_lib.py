#!/usr/bin/env python3
from __future__ import annotations

import bisect
import csv
import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import combinations
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class DevicePairChoice:
    device_a: str
    device_b: str
    overlap_ms: int


@dataclass(frozen=True)
class SessionWindow:
    stem: str
    start_ms: int
    end_ms: int


@dataclass(frozen=True)
class CaptureVideoInfo:
    stem: str
    path: Path
    start_ms: int
    duration_seconds: float
    fps: float
    frame_count: int


@dataclass(frozen=True)
class DeviceSummary:
    device_id: str
    csv_path: Path
    rows: int
    first_ms: int
    last_ms: int
    intervals: list[tuple[int, int]]


def parse_capture_stem_start_ms(stem: str, timezone_name: str) -> int:
    dt_value = datetime.strptime(stem, "%Y%m%d_%H%M%S").replace(tzinfo=ZoneInfo(timezone_name))
    return int(dt_value.timestamp() * 1000)


def parse_time_of_day_to_epoch_ms(capture_date: str, time_of_day: str, timezone_name: str) -> int:
    dt_value = datetime.strptime(f"{capture_date} {time_of_day}", "%Y-%m-%d %H:%M:%S.%f")
    dt_value = dt_value.replace(tzinfo=ZoneInfo(timezone_name))
    return int(dt_value.timestamp() * 1000)


def build_frame_timestamps(start_ms: int, frame_count: int, fps: float) -> list[float]:
    if frame_count <= 0:
        return []
    if fps <= 0:
        raise ValueError("fps must be positive")
    interval_ms = 1000.0 / fps
    return [start_ms + (index * interval_ms) for index in range(frame_count)]


def merge_intervals(intervals: list[tuple[int, int]], gap_tolerance_ms: int) -> list[tuple[int, int]]:
    if not intervals:
        return []
    ordered = sorted(intervals)
    merged: list[tuple[int, int]] = [ordered[0]]
    for start_ms, end_ms in ordered[1:]:
        last_start, last_end = merged[-1]
        if start_ms <= last_end + gap_tolerance_ms:
            merged[-1] = (last_start, max(last_end, end_ms))
        else:
            merged.append((start_ms, end_ms))
    return merged


def build_device_intervals(epochs_ms: list[int], gap_threshold_ms: int) -> list[tuple[int, int]]:
    if not epochs_ms:
        return []
    ordered = sorted(epochs_ms)
    intervals: list[tuple[int, int]] = []
    start_ms = ordered[0]
    end_ms = ordered[0]
    for ts in ordered[1:]:
        if ts - end_ms > gap_threshold_ms:
            intervals.append((start_ms, end_ms))
            start_ms = ts
        end_ms = ts
    intervals.append((start_ms, end_ms))
    return intervals


def _interval_overlap_ms(a: tuple[int, int], b: tuple[int, int]) -> int:
    start_ms = max(a[0], b[0])
    end_ms = min(a[1], b[1])
    return max(0, end_ms - start_ms)


def intersect_interval_sets(
    left: list[tuple[int, int]],
    right: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    intersections: list[tuple[int, int]] = []
    for interval_left in left:
        for interval_right in right:
            start_ms = max(interval_left[0], interval_right[0])
            end_ms = min(interval_left[1], interval_right[1])
            if end_ms > start_ms:
                intersections.append((start_ms, end_ms))
    return intersections


def _total_pair_overlap_ms(
    intervals_a: list[tuple[int, int]],
    intervals_b: list[tuple[int, int]],
    video_window: tuple[int, int],
) -> int:
    clipped_a = intersect_interval_sets(intervals_a, [video_window])
    clipped_b = intersect_interval_sets(intervals_b, [video_window])
    intersections = intersect_interval_sets(clipped_a, clipped_b)
    return sum(end_ms - start_ms for start_ms, end_ms in intersections)


def choose_best_device_pair(
    device_intervals: dict[str, list[tuple[int, int]]],
    video_start_ms: int,
    video_end_ms: int,
) -> DevicePairChoice:
    if len(device_intervals) < 2:
        raise ValueError("need at least two devices")

    best_choice: DevicePairChoice | None = None
    for device_a, device_b in combinations(sorted(device_intervals), 2):
        overlap_ms = _total_pair_overlap_ms(
            device_intervals[device_a],
            device_intervals[device_b],
            (video_start_ms, video_end_ms),
        )
        choice = DevicePairChoice(device_a=device_a, device_b=device_b, overlap_ms=overlap_ms)
        if best_choice is None or (choice.overlap_ms, choice.device_a, choice.device_b) > (
            best_choice.overlap_ms,
            best_choice.device_a,
            best_choice.device_b,
        ):
            best_choice = choice

    assert best_choice is not None
    return best_choice


def slice_intervals_to_sessions(
    intervals: list[tuple[int, int]],
    session_length_ms: int,
    min_session_ms: int,
    timezone_name: str,
) -> list[SessionWindow]:
    if session_length_ms <= 0:
        raise ValueError("session_length_ms must be positive")
    if min_session_ms <= 0:
        raise ValueError("min_session_ms must be positive")

    sessions: list[SessionWindow] = []
    tz = ZoneInfo(timezone_name)
    for interval_start_ms, interval_end_ms in intervals:
        cursor = interval_start_ms
        while cursor + min_session_ms <= interval_end_ms:
            end_ms = min(cursor + session_length_ms, interval_end_ms)
            if end_ms - cursor < min_session_ms:
                break
            stem = datetime.fromtimestamp(cursor / 1000, tz=tz).strftime("%Y%m%d_%H%M%S")
            sessions.append(SessionWindow(stem=stem, start_ms=cursor, end_ms=end_ms))
            cursor = end_ms
    return sessions


def iter_raw_imu_csvs(source_root: Path) -> list[Path]:
    return sorted(path for path in source_root.rglob("data_*.csv") if path.is_file())


def normalize_imu_directory(
    source_root: Path,
    normalized_root: Path,
    capture_date: str,
    timezone_name: str,
) -> dict[str, Path]:
    csv_paths = iter_raw_imu_csvs(source_root)
    if not csv_paths:
        raise FileNotFoundError(f"no raw IMU csv files found under {source_root}")

    normalized_root.mkdir(parents=True, exist_ok=True)
    by_device_dir = normalized_root / "by_device"
    by_device_dir.mkdir(parents=True, exist_ok=True)

    writers: dict[str, csv.writer] = {}
    file_handles: dict[str, object] = {}
    output_paths: dict[str, Path] = {}

    try:
        for csv_path in csv_paths:
            with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                fieldnames = list(reader.fieldnames or [])
                if not fieldnames:
                    continue
                output_header = fieldnames + ["epoch_ms", "source_folder", "source_file"]

                for row in reader:
                    device_id = (row.get("设备名称", "") or "").strip()
                    time_of_day = (row.get("时间", "") or "").strip()
                    if not device_id or not time_of_day:
                        continue

                    if device_id not in writers:
                        output_path = by_device_dir / f"{device_id}.csv"
                        fh = output_path.open("w", encoding="utf-8", newline="")
                        writer = csv.writer(fh)
                        writer.writerow(output_header)
                        writers[device_id] = writer
                        file_handles[device_id] = fh
                        output_paths[device_id] = output_path

                    epoch_ms = parse_time_of_day_to_epoch_ms(capture_date, time_of_day, timezone_name)
                    writers[device_id].writerow(
                        [row.get(column, "") for column in fieldnames]
                        + [f"{epoch_ms:.3f}", csv_path.parent.name, csv_path.name]
                    )
    finally:
        for handle in file_handles.values():
            handle.close()

    return output_paths


def build_device_summaries(
    normalized_by_device_dir: Path,
    gap_threshold_ms: int,
) -> dict[str, DeviceSummary]:
    summaries: dict[str, DeviceSummary] = {}
    for csv_path in sorted(normalized_by_device_dir.glob("*.csv")):
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            first_ms: int | None = None
            last_ms: int | None = None
            current_start: int | None = None
            prev_ms: int | None = None
            row_count = 0
            intervals: list[tuple[int, int]] = []

            for row in reader:
                raw_ts = (row.get("epoch_ms", "") or "").strip()
                if not raw_ts:
                    continue
                ts = int(round(float(raw_ts)))
                row_count += 1
                if first_ms is None:
                    first_ms = ts
                    current_start = ts
                if prev_ms is not None and ts - prev_ms > gap_threshold_ms:
                    assert current_start is not None
                    intervals.append((current_start, prev_ms))
                    current_start = ts
                prev_ms = ts
                last_ms = ts

            if row_count == 0 or first_ms is None or last_ms is None or current_start is None or prev_ms is None:
                continue
            intervals.append((current_start, prev_ms))

        summaries[csv_path.stem] = DeviceSummary(
            device_id=csv_path.stem,
            csv_path=csv_path,
            rows=row_count,
            first_ms=first_ms,
            last_ms=last_ms,
            intervals=intervals,
        )
    if not summaries:
        raise FileNotFoundError(f"no normalized device CSVs found under {normalized_by_device_dir}")
    return summaries


def clip_intervals_to_window(
    intervals: Iterable[tuple[int, int]],
    window_start_ms: int,
    window_end_ms: int,
) -> list[tuple[int, int]]:
    clipped: list[tuple[int, int]] = []
    for start_ms, end_ms in intervals:
        overlap_start = max(start_ms, window_start_ms)
        overlap_end = min(end_ms, window_end_ms)
        if overlap_end > overlap_start:
            clipped.append((overlap_start, overlap_end))
    return clipped


def choose_best_device_pair_from_summaries(
    summaries: dict[str, DeviceSummary],
    video_start_ms: int,
    video_end_ms: int,
) -> DevicePairChoice:
    interval_map = {device_id: summary.intervals for device_id, summary in summaries.items()}
    return choose_best_device_pair(interval_map, video_start_ms, video_end_ms)


def build_pair_overlap_intervals(
    summaries: dict[str, DeviceSummary],
    pair: DevicePairChoice,
    video_start_ms: int,
    video_end_ms: int,
    merge_gap_ms: int,
) -> list[tuple[int, int]]:
    left = clip_intervals_to_window(summaries[pair.device_a].intervals, video_start_ms, video_end_ms)
    right = clip_intervals_to_window(summaries[pair.device_b].intervals, video_start_ms, video_end_ms)
    return merge_intervals(intersect_interval_sets(left, right), merge_gap_ms)


def build_union_intervals(
    device_intervals: dict[str, list[tuple[int, int]]],
    window_start_ms: int,
    window_end_ms: int,
    merge_gap_ms: int,
) -> list[tuple[int, int]]:
    collected: list[tuple[int, int]] = []
    for intervals in device_intervals.values():
        collected.extend(clip_intervals_to_window(intervals, window_start_ms, window_end_ms))
    return merge_intervals(collected, merge_gap_ms)


def active_devices_for_window(
    device_intervals: dict[str, list[tuple[int, int]]],
    start_ms: int,
    end_ms: int,
) -> list[str]:
    active: list[str] = []
    for device_id in sorted(device_intervals):
        for interval_start_ms, interval_end_ms in device_intervals[device_id]:
            if min(interval_end_ms, end_ms) > max(interval_start_ms, start_ms):
                active.append(device_id)
                break
    return active


def probe_video(video_path: Path, fallback_fps: float | None = None) -> CaptureVideoInfo:
    if not shutil.which("ffprobe"):
        raise RuntimeError("ffprobe is required")

    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=avg_frame_rate:format=duration",
        "-of",
        "json",
        str(video_path),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    stream = (payload.get("streams") or [{}])[0]
    format_info = payload.get("format") or {}

    duration_seconds = float(format_info.get("duration") or 0.0)
    raw_rate = str(stream.get("avg_frame_rate") or "")
    if raw_rate and raw_rate != "0/0":
        numerator, denominator = raw_rate.split("/")
        fps = float(numerator) / float(denominator)
    elif fallback_fps is not None:
        fps = float(fallback_fps)
    else:
        raise ValueError(f"could not determine fps for {video_path}")

    frame_count = int(round(duration_seconds * fps))
    return CaptureVideoInfo(
        stem=video_path.stem,
        path=video_path,
        start_ms=0,
        duration_seconds=duration_seconds,
        fps=fps,
        frame_count=frame_count,
    )


def select_frame_range(
    frame_timestamps_ms: list[float],
    start_ms: int,
    end_ms: int,
) -> tuple[int, int]:
    start_index = bisect.bisect_left(frame_timestamps_ms, float(start_ms))
    end_index = bisect.bisect_right(frame_timestamps_ms, float(end_ms)) - 1
    if start_index >= len(frame_timestamps_ms):
        raise ValueError("session starts after video ends")
    end_index = max(start_index, min(end_index, len(frame_timestamps_ms) - 1))
    return start_index, end_index


def write_frame_timestamps_csv(
    output_path: Path,
    frame_timestamps_ms: list[float],
    start_index: int,
    end_index: int,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["frame_index", "timestamp_ms"])
        for frame_index in range(start_index, end_index + 1):
            writer.writerow([frame_index - start_index + 1, f"{frame_timestamps_ms[frame_index]:.3f}"])


def filter_device_csv_to_window(
    source_csv: Path,
    output_csv: Path,
    start_ms: int,
    end_ms: int,
) -> int:
    kept = 0
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with source_csv.open("r", encoding="utf-8-sig", newline="") as src, output_csv.open(
        "w", encoding="utf-8", newline=""
    ) as dst:
        reader = csv.DictReader(src)
        fieldnames = list(reader.fieldnames or [])
        if not fieldnames:
            raise ValueError(f"empty csv: {source_csv}")
        writer = csv.DictWriter(dst, fieldnames=fieldnames)
        writer.writeheader()
        for row in reader:
            raw_ts = (row.get("epoch_ms", "") or "").strip()
            if not raw_ts:
                continue
            ts = int(round(float(raw_ts)))
            if start_ms <= ts <= end_ms:
                writer.writerow(row)
                kept += 1
    return kept


def hardlink_or_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        if dst.exists():
            dst.unlink()
        dst.hardlink_to(src)
    except OSError:
        shutil.copy2(src, dst)


def clip_video_segment(
    input_video: Path,
    output_video: Path,
    offset_seconds: float,
    duration_seconds: float,
) -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required")
    output_video.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{offset_seconds:.3f}",
        "-i",
        str(input_video),
        "-t",
        f"{duration_seconds:.3f}",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(output_video),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
