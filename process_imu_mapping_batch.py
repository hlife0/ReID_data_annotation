#!/usr/bin/env python3
from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

CSV_COLUMNS = [
    "video_stem",
    "frame_index",
    "timestamp_ms",
    "imu_id_a",
    "imu_id_b",
    "static_coef_a",
    "static_coef_b",
    "coef_type",
    "coef_a",
    "coef_b",
    "k_t",
    "m_t",
    "rank_m_desc",
]


@dataclass
class Task:
    video_stem: str
    timestamp_path: Path
    imu_paths: List[Path]
    status: str
    blocked_reason: str = ""


@dataclass
class IMUSeries:
    imu_id: str
    epoch_ms: List[float]
    motion_coef: List[float]
    static_coef: List[float]
    skipped_rows: int
    total_rows: int


class RunLogger:
    def __init__(self, run_log_path: Path, error_log_path: Path) -> None:
        self.run_log_path = run_log_path
        self.error_log_path = error_log_path
        self.run_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.error_log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.run_log_path.exists():
            self.run_log_path.write_text("", encoding="utf-8")
        if not self.error_log_path.exists():
            self.error_log_path.write_text("", encoding="utf-8")

    def info(self, message: str) -> None:
        line = f"[{_now()}] INFO  {message}\n"
        with self.run_log_path.open("a", encoding="utf-8") as f:
            f.write(line)
        print(line, end="")

    def error(self, message: str) -> None:
        line = f"[{_now()}] ERROR {message}\n"
        with self.run_log_path.open("a", encoding="utf-8") as f:
            f.write(line)
        with self.error_log_path.open("a", encoding="utf-8") as f:
            f.write(line)
        print(line, end="")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run C stage: dual-IMU ratio analysis for person-IMU mapping assistance"
    )
    parser.add_argument(
        "--required-root",
        type=Path,
        default=Path("./data/required"),
        help="Input required data root",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("."),
        help="Root directory used to create batch_<YYYYMMDD>_vNN",
    )
    parser.add_argument(
        "--batch-dir",
        type=Path,
        default=None,
        help="Explicit batch directory. If set, skip auto batch naming.",
    )
    parser.add_argument(
        "--batch-date",
        type=str,
        default=datetime.now().strftime("%Y%m%d"),
        help="Batch date in YYYYMMDD, used when --batch-dir is not provided",
    )
    parser.add_argument(
        "--batch-version",
        type=int,
        default=None,
        help="Optional fixed version number NN for batch_<date>_vNN",
    )
    parser.add_argument(
        "--video-stems",
        type=str,
        nargs="*",
        default=None,
        help="Optional explicit video stems. Default: all directories under required-root.",
    )
    parser.add_argument(
        "--coef-type",
        type=str,
        choices=["motion", "static"],
        default="motion",
        help="Coefficient type used for k_t = c_a / c_b",
    )
    parser.add_argument(
        "--smoothing-window",
        type=int,
        default=5,
        help="Centered moving-average window size (samples), >=1",
    )
    parser.add_argument(
        "--gyro-norm-dps",
        type=float,
        default=180.0,
        help="Gyroscope normalization in deg/s for motion coefficient",
    )
    parser.add_argument(
        "--max-align-gap-ms",
        type=float,
        default=250.0,
        help="Max allowed nearest-neighbor alignment gap in ms",
    )
    parser.add_argument(
        "--min-coef",
        type=float,
        default=1e-6,
        help="Positive floor for coef_a/coef_b",
    )
    parser.add_argument(
        "--top-replay-points",
        type=int,
        default=20,
        help="Top-N ranked points included in summary replay suggestions",
    )
    parser.add_argument(
        "--replay-window-ms",
        type=float,
        default=1200.0,
        help="Half-window around key point for replay suggestions",
    )
    return parser.parse_args()


def find_batch_dir(output_root: Path, batch_date: str, fixed_version: int | None) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    if fixed_version is not None:
        return output_root / f"batch_{batch_date}_v{fixed_version:02d}"

    pattern = re.compile(rf"^batch_{re.escape(batch_date)}_v(\d{{2}})$")
    latest = 0
    for child in output_root.iterdir():
        if not child.is_dir():
            continue
        match = pattern.match(child.name)
        if match:
            latest = max(latest, int(match.group(1)))
    return output_root / f"batch_{batch_date}_v{latest + 1:02d}"


def discover_video_stems(required_root: Path, explicit_stems: List[str] | None) -> List[str]:
    if explicit_stems:
        return explicit_stems
    stems = []
    if not required_root.exists():
        return stems
    for child in sorted(required_root.iterdir()):
        if child.is_dir():
            stems.append(child.name)
    return stems


def check_timestamp_csv(path: Path) -> Tuple[bool, str]:
    if not path.exists():
        return False, "missing timestamp csv"
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fields = set(reader.fieldnames or [])
            required = {"frame_index", "timestamp_ms"}
            if not required.issubset(fields):
                return False, f"timestamp csv missing required columns, got={sorted(fields)}"
            next(reader, None)
    except Exception as exc:
        return False, f"timestamp csv read failed: {exc}"
    return True, ""


def step_c0_input_inspection(required_root: Path, video_stems: List[str], logger: RunLogger) -> List[Task]:
    logger.info("Step C0 start: input inspection")
    tasks: List[Task] = []
    for stem in video_stems:
        timestamp_path = required_root / stem / "video" / f"{stem}_frame_timestamps_retimed.csv"
        imu_paths = sorted((required_root / stem / "imu").glob("*.csv"))

        reasons: List[str] = []
        ts_ok, ts_reason = check_timestamp_csv(timestamp_path)
        if not ts_ok:
            reasons.append(ts_reason)
        if len(imu_paths) != 2:
            reasons.append(f"imu csv count is {len(imu_paths)}, expected 2")

        status = "todo" if not reasons else "blocked"
        reason_text = "; ".join(reasons)
        task = Task(
            video_stem=stem,
            timestamp_path=timestamp_path,
            imu_paths=imu_paths,
            status=status,
            blocked_reason=reason_text,
        )
        tasks.append(task)

        logger.info(
            f"C0 {stem}: status={status}, timestamp_exists={timestamp_path.exists()}, imu_count={len(imu_paths)}"
        )
        if status == "blocked":
            logger.error(f"C0 blocked {stem}: {reason_text}")
    return tasks


def parse_float(raw: str) -> float:
    return float(raw.strip())


def find_column_name(fieldnames: List[str], candidates: List[str]) -> str | None:
    if not fieldnames:
        return None
    cleaned = [(name, name.replace("\ufeff", "").strip()) for name in fieldnames]
    for candidate in candidates:
        for original, short in cleaned:
            if short == candidate:
                return original
    for candidate in candidates:
        for original, short in cleaned:
            if candidate in short:
                return original
    return None


def moving_average_centered(values: List[float], window: int) -> List[float]:
    if window <= 1 or len(values) <= 1:
        return values[:]
    radius = window // 2
    output: List[float] = []
    for i in range(len(values)):
        start = max(0, i - radius)
        end = min(len(values), i + radius + 1)
        segment = values[start:end]
        output.append(sum(segment) / len(segment))
    return output


def imu_id_from_path(path: Path) -> str:
    stem = path.stem
    parts = stem.split("_")
    return parts[-1] if parts else stem


def load_imu_series(
    path: Path,
    smoothing_window: int,
    gyro_norm_dps: float,
    min_coef: float,
) -> IMUSeries:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        epoch_col = find_column_name(fieldnames, ["epoch_ms"])
        ax_col = find_column_name(fieldnames, ["加速度X", "acc_x", "accel_x"])
        ay_col = find_column_name(fieldnames, ["加速度Y", "acc_y", "accel_y"])
        az_col = find_column_name(fieldnames, ["加速度Z", "acc_z", "accel_z"])
        gx_col = find_column_name(fieldnames, ["角速度X", "gyro_x"])
        gy_col = find_column_name(fieldnames, ["角速度Y", "gyro_y"])
        gz_col = find_column_name(fieldnames, ["角速度Z", "gyro_z"])
        device_col = find_column_name(fieldnames, ["设备名称", "device"])

        required_cols = [epoch_col, ax_col, ay_col, az_col, gx_col, gy_col, gz_col]
        if any(col is None for col in required_cols):
            raise ValueError(
                f"missing required imu columns in {path.name}; "
                f"fieldnames={fieldnames}"
            )

        epoch: List[float] = []
        raw_motion: List[float] = []
        imu_id = imu_id_from_path(path)
        total_rows = 0
        skipped_rows = 0

        for row in reader:
            total_rows += 1
            try:
                ts = parse_float(row[epoch_col])  # type: ignore[index]
                ax = parse_float(row[ax_col])  # type: ignore[index]
                ay = parse_float(row[ay_col])  # type: ignore[index]
                az = parse_float(row[az_col])  # type: ignore[index]
                gx = parse_float(row[gx_col])  # type: ignore[index]
                gy = parse_float(row[gy_col])  # type: ignore[index]
                gz = parse_float(row[gz_col])  # type: ignore[index]
            except Exception:
                skipped_rows += 1
                continue

            if device_col:
                maybe_device = row.get(device_col, "").strip()
                if maybe_device:
                    imu_id = maybe_device

            acc_mag = math.sqrt(ax * ax + ay * ay + az * az)
            gyro_mag = math.sqrt(gx * gx + gy * gy + gz * gz)
            motion_raw = abs(acc_mag - 1.0) + (gyro_mag / gyro_norm_dps)
            epoch.append(ts)
            raw_motion.append(motion_raw)

    if not epoch:
        raise ValueError(f"imu csv has no valid rows: {path}")

    smoothed = moving_average_centered(raw_motion, smoothing_window)
    motion_coef = [max(min_coef, value + min_coef) for value in smoothed]
    static_coef = [1.0 / (1.0 + value) for value in motion_coef]

    ordered = sorted(zip(epoch, motion_coef, static_coef), key=lambda x: x[0])
    return IMUSeries(
        imu_id=imu_id,
        epoch_ms=[x[0] for x in ordered],
        motion_coef=[x[1] for x in ordered],
        static_coef=[x[2] for x in ordered],
        skipped_rows=skipped_rows,
        total_rows=total_rows,
    )


def load_frame_timestamps(path: Path) -> List[Tuple[int, float]]:
    rows: List[Tuple[int, float]] = []
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            frame_index = int(row["frame_index"])
            timestamp_ms = float(row["timestamp_ms"])
            rows.append((frame_index, timestamp_ms))
    rows.sort(key=lambda x: x[0])
    return rows


def nearest_index(times: List[float], target_ms: float, max_gap_ms: float) -> Tuple[int | None, float]:
    if not times:
        return None, math.inf
    pos = bisect.bisect_left(times, target_ms)
    best_idx = None
    best_gap = math.inf
    for cand in (pos - 1, pos):
        if 0 <= cand < len(times):
            gap = abs(times[cand] - target_ms)
            if gap < best_gap:
                best_gap = gap
                best_idx = cand
    if best_idx is None or best_gap > max_gap_ms:
        return None, best_gap
    return best_idx, best_gap


def format_float(value: float) -> str:
    return f"{value:.8f}"


def build_replay_windows(points: List[Dict[str, str]], replay_window_ms: float) -> List[Dict[str, float]]:
    if not points:
        return []
    windows: List[Tuple[float, float]] = []
    for row in points:
        ts = float(row["timestamp_ms"])
        windows.append((ts - replay_window_ms, ts + replay_window_ms))
    windows.sort(key=lambda x: x[0])

    merged: List[Tuple[float, float]] = []
    for start, end in windows:
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))

    return [
        {
            "start_ms": round(start, 3),
            "end_ms": round(end, 3),
            "duration_ms": round(end - start, 3),
        }
        for start, end in merged
    ]


def process_one_video(
    task: Task,
    args: argparse.Namespace,
    out_csv: Path,
    out_summary_json: Path,
    logger: RunLogger,
) -> bool:
    if task.status != "todo":
        summary = {
            "video_stem": task.video_stem,
            "status": "blocked",
            "blocked_reason": task.blocked_reason,
            "generated_at": _now(),
        }
        out_summary_json.parent.mkdir(parents=True, exist_ok=True)
        out_summary_json.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        logger.error(f"C3 blocked {task.video_stem}: {task.blocked_reason}")
        return False

    try:
        imu_a = load_imu_series(
            task.imu_paths[0],
            smoothing_window=args.smoothing_window,
            gyro_norm_dps=args.gyro_norm_dps,
            min_coef=args.min_coef,
        )
        imu_b = load_imu_series(
            task.imu_paths[1],
            smoothing_window=args.smoothing_window,
            gyro_norm_dps=args.gyro_norm_dps,
            min_coef=args.min_coef,
        )
        frames = load_frame_timestamps(task.timestamp_path)
    except Exception as exc:
        logger.error(f"C1 failed {task.video_stem}: {exc}")
        summary = {
            "video_stem": task.video_stem,
            "status": "blocked",
            "blocked_reason": str(exc),
            "generated_at": _now(),
        }
        out_summary_json.parent.mkdir(parents=True, exist_ok=True)
        out_summary_json.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return False

    rows: List[Dict[str, str]] = []
    gap_a_values: List[float] = []
    gap_b_values: List[float] = []
    skipped_align_a = 0
    skipped_align_b = 0
    skipped_align_both = 0

    for frame_index, timestamp_ms in frames:
        idx_a, gap_a = nearest_index(imu_a.epoch_ms, timestamp_ms, args.max_align_gap_ms)
        idx_b, gap_b = nearest_index(imu_b.epoch_ms, timestamp_ms, args.max_align_gap_ms)

        if idx_a is None and idx_b is None:
            skipped_align_both += 1
            continue
        if idx_a is None:
            skipped_align_a += 1
            continue
        if idx_b is None:
            skipped_align_b += 1
            continue

        gap_a_values.append(gap_a)
        gap_b_values.append(gap_b)

        static_a = imu_a.static_coef[idx_a]
        static_b = imu_b.static_coef[idx_b]
        coef_a = imu_a.motion_coef[idx_a] if args.coef_type == "motion" else static_a
        coef_b = imu_b.motion_coef[idx_b] if args.coef_type == "motion" else static_b
        coef_a = max(args.min_coef, coef_a)
        coef_b = max(args.min_coef, coef_b)
        k_t = coef_a / coef_b
        m_t = max(k_t, 1.0 / k_t)

        rows.append(
            {
                "video_stem": task.video_stem,
                "frame_index": str(frame_index),
                "timestamp_ms": format_float(timestamp_ms),
                "imu_id_a": imu_a.imu_id,
                "imu_id_b": imu_b.imu_id,
                "static_coef_a": format_float(static_a),
                "static_coef_b": format_float(static_b),
                "coef_type": args.coef_type,
                "coef_a": format_float(coef_a),
                "coef_b": format_float(coef_b),
                "k_t": format_float(k_t),
                "m_t": format_float(m_t),
                "rank_m_desc": "0",
            }
        )

    rows.sort(key=lambda r: (-float(r["m_t"]), float(r["timestamp_ms"])))
    for idx, row in enumerate(rows, start=1):
        row["rank_m_desc"] = str(idx)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    top_points = rows[: args.top_replay_points]
    replay_windows = build_replay_windows(top_points, args.replay_window_ms)
    skip_total = skipped_align_a + skipped_align_b + skipped_align_both
    summary = {
        "video_stem": task.video_stem,
        "status": "done",
        "generated_at": _now(),
        "inputs": {
            "timestamp_csv": str(task.timestamp_path),
            "imu_csv_a": str(task.imu_paths[0]),
            "imu_csv_b": str(task.imu_paths[1]),
        },
        "imu_ids": {
            "imu_id_a": imu_a.imu_id,
            "imu_id_b": imu_b.imu_id,
        },
        "algorithm": {
            "coef_type": args.coef_type,
            "channels_used": [
                "acceleration xyz",
                "gyroscope xyz",
            ],
            "alignment_strategy": {
                "method": "nearest-neighbor by epoch_ms to frame timestamp_ms",
                "max_align_gap_ms": args.max_align_gap_ms,
            },
            "smoothing": {
                "method": "centered moving average",
                "window_samples": args.smoothing_window,
            },
            "formulas": {
                "motion_raw": "|sqrt(ax^2+ay^2+az^2)-1| + sqrt(gx^2+gy^2+gz^2)/gyro_norm_dps",
                "motion_coef": "max(min_coef, moving_average(motion_raw) + min_coef)",
                "static_coef": "1 / (1 + motion_coef)",
                "k_t": "coef_a / coef_b",
                "m_t": "max(k_t, 1 / k_t)",
            },
            "parameters": {
                "gyro_norm_dps": args.gyro_norm_dps,
                "min_coef": args.min_coef,
            },
            "missing_value_handling": "Rows with missing/invalid required numeric channels are dropped",
            "spike_handling": "Smoothed with centered moving average",
        },
        "stats": {
            "frame_total": len(frames),
            "frame_output": len(rows),
            "frame_skipped": skip_total,
            "frame_skipped_align_a_only": skipped_align_a,
            "frame_skipped_align_b_only": skipped_align_b,
            "frame_skipped_align_both": skipped_align_both,
            "imu_a_total_rows": imu_a.total_rows,
            "imu_b_total_rows": imu_b.total_rows,
            "imu_a_skipped_rows": imu_a.skipped_rows,
            "imu_b_skipped_rows": imu_b.skipped_rows,
            "align_gap_ms": {
                "imu_a_mean": round(sum(gap_a_values) / len(gap_a_values), 6) if gap_a_values else None,
                "imu_b_mean": round(sum(gap_b_values) / len(gap_b_values), 6) if gap_b_values else None,
                "imu_a_max": round(max(gap_a_values), 6) if gap_a_values else None,
                "imu_b_max": round(max(gap_b_values), 6) if gap_b_values else None,
            },
        },
        "recommended_replay_points": [
            {
                "rank_m_desc": int(row["rank_m_desc"]),
                "frame_index": int(row["frame_index"]),
                "timestamp_ms": float(row["timestamp_ms"]),
                "m_t": float(row["m_t"]),
            }
            for row in top_points
        ],
        "recommended_replay_windows_ms": replay_windows,
        "notes": [
            "Higher m_t indicates stronger inter-IMU state contrast and higher replay priority.",
            "If coef_type=motion, static_coef fields are still provided for interpretability.",
        ],
    }
    out_summary_json.parent.mkdir(parents=True, exist_ok=True)
    out_summary_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    logger.info(
        f"C3 done {task.video_stem}: rows={len(rows)}, skipped={skip_total}, output={out_csv.name}"
    )
    if skip_total > 0:
        logger.error(
            f"C3 {task.video_stem}: skipped_frames={skip_total} "
            f"(a_only={skipped_align_a}, b_only={skipped_align_b}, both={skipped_align_both})"
        )
    return True


def validate_output_csv(path: Path, logger: RunLogger) -> bool:
    if not path.exists():
        logger.error(f"Validation failed: missing csv {path}")
        return False
    ok = True
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        if fields != CSV_COLUMNS:
            logger.error(
                f"Validation failed {path.name}: header mismatch, expected={CSV_COLUMNS}, got={fields}"
            )
            return False

        prev_m: float | None = None
        prev_ts: float | None = None
        row_count = 0
        for row in reader:
            row_count += 1
            rank = int(row["rank_m_desc"])
            k_t = float(row["k_t"])
            m_t = float(row["m_t"])
            ts = float(row["timestamp_ms"])
            static_a = float(row["static_coef_a"])
            static_b = float(row["static_coef_b"])

            if rank != row_count:
                logger.error(f"Validation failed {path.name}: rank mismatch at row {row_count}")
                ok = False
            if k_t <= 0.0 or m_t < 1.0:
                logger.error(f"Validation failed {path.name}: invalid k_t/m_t at row {row_count}")
                ok = False
            if static_a <= 0.0 or static_b <= 0.0:
                logger.error(f"Validation failed {path.name}: static_coef must be >0 at row {row_count}")
                ok = False
            expected_m = max(k_t, 1.0 / k_t)
            if abs(expected_m - m_t) > 1e-6:
                logger.error(f"Validation failed {path.name}: m_t!=max(k_t,1/k_t) at row {row_count}")
                ok = False
            if prev_m is not None:
                if m_t > prev_m + 1e-12:
                    logger.error(f"Validation failed {path.name}: m_t not descending at row {row_count}")
                    ok = False
                if abs(m_t - prev_m) <= 1e-12 and prev_ts is not None and ts < prev_ts:
                    logger.error(
                        f"Validation failed {path.name}: tie m_t but timestamp not ascending at row {row_count}"
                    )
                    ok = False
            prev_m = m_t
            prev_ts = ts
    logger.info(f"Validation {path.name}: rows={row_count}, ok={ok}")
    return ok


def main() -> None:
    args = parse_args()
    if args.smoothing_window < 1:
        raise SystemExit("--smoothing-window must be >= 1")
    if args.gyro_norm_dps <= 0:
        raise SystemExit("--gyro-norm-dps must be > 0")
    if args.max_align_gap_ms <= 0:
        raise SystemExit("--max-align-gap-ms must be > 0")
    if args.min_coef <= 0:
        raise SystemExit("--min-coef must be > 0")

    batch_dir = (
        args.batch_dir
        if args.batch_dir is not None
        else find_batch_dir(args.output_root, args.batch_date, args.batch_version)
    )
    imu_mapping_dir = batch_dir / "imu_mapping"
    logs_dir = batch_dir / "logs"
    run_log_path = logs_dir / "run.log"
    error_log_path = logs_dir / "errors.log"
    logger = RunLogger(run_log_path=run_log_path, error_log_path=error_log_path)

    logger.info("==============================================")
    logger.info("C-stage dual IMU mapping batch run started")
    logger.info(f"Batch dir: {batch_dir}")
    logger.info(
        f"Config coef_type={args.coef_type}, smoothing_window={args.smoothing_window}, "
        f"gyro_norm_dps={args.gyro_norm_dps}, max_align_gap_ms={args.max_align_gap_ms}"
    )

    stems = discover_video_stems(args.required_root, args.video_stems)
    if not stems:
        logger.error(f"No video stems found under required root: {args.required_root}")
        raise SystemExit(1)
    logger.info(f"Video stems count={len(stems)}")

    tasks = step_c0_input_inspection(args.required_root, stems, logger)

    success = 0
    blocked = 0
    failed = 0
    for task in tasks:
        out_csv = imu_mapping_dir / f"{task.video_stem}.imu_ratio_rank.csv"
        out_summary = imu_mapping_dir / f"{task.video_stem}.imu_mapping_summary.json"
        ok = process_one_video(task, args, out_csv, out_summary, logger)
        if task.status != "todo":
            blocked += 1
            continue
        if not ok:
            failed += 1
            continue
        csv_ok = validate_output_csv(out_csv, logger)
        if csv_ok:
            success += 1
        else:
            failed += 1
            logger.error(f"C3 validation failed {task.video_stem}")

    logger.info(
        f"C-stage finished: success_videos={success}, blocked_videos={blocked}, failed_videos={failed}, "
        f"total_videos={len(tasks)}"
    )
    if failed > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
