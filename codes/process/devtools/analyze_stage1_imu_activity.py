#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from process.shared import segment_prep_common as common
from process.step5_stage2_review_prep import process_segment_review_prep as base_prep


IGNORED_IMU_FIELDS = {
    "时间",
    "设备名称",
    "片上时间()",
    "epoch_ms",
    "source_folder",
    "source_file",
}


@dataclass(frozen=True)
class IMUSample:
    epoch_ms: float
    payload: Tuple[Any, ...]


@dataclass(frozen=True)
class IMUSeries:
    imu_id: str
    csv_path: str
    payload_fields: Tuple[str, ...]
    samples: Tuple[IMUSample, ...]


def _normalize_payload_value(value: Any) -> Any:
    text = str(value or "").strip()
    if text == "":
        return ""
    try:
        return round(float(text), 6)
    except Exception:
        return text


def _imu_id_from_path(csv_path: Path) -> str:
    stem = csv_path.stem
    if "_" not in stem:
        return stem
    return stem.rsplit("_", 1)[-1]


def load_imu_series(csv_path: Path) -> IMUSeries:
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = tuple(reader.fieldnames or ())
        payload_fields = tuple(field for field in fieldnames if field not in IGNORED_IMU_FIELDS)
        imu_id = _imu_id_from_path(csv_path)
        payload_by_epoch: Dict[float, Tuple[Any, ...]] = {}
        for row in reader:
            try:
                epoch_ms = round(float(str(row.get("epoch_ms", "")).strip()), 3)
            except Exception:
                continue
            device_name = str(row.get("设备名称", "")).strip()
            if device_name:
                imu_id = device_name
            payload_by_epoch[epoch_ms] = tuple(_normalize_payload_value(row.get(field, "")) for field in payload_fields)

    samples = tuple(
        IMUSample(epoch_ms=epoch_ms, payload=payload)
        for epoch_ms, payload in sorted(payload_by_epoch.items())
    )
    return IMUSeries(
        imu_id=imu_id,
        csv_path=str(csv_path),
        payload_fields=payload_fields,
        samples=samples,
    )


def _build_activity_points(
    frame_timestamps: Dict[int, float],
    imu_series_list: Iterable[IMUSeries],
) -> List[Dict[str, Any]]:
    series_list = list(imu_series_list)
    states = {
        series.imu_id: {
            "samples": series.samples,
            "cursor": 0,
            "current_payload": None,
            "previous_payload": None,
        }
        for series in series_list
    }

    points: List[Dict[str, Any]] = []
    ordered_frames = list(sorted(frame_timestamps.items()))
    for point_index, (frame_index, timestamp_ms) in enumerate(ordered_frames):
        active_imu_ids: List[str] = []
        for series in series_list:
            state = states[series.imu_id]
            current_payload = state["current_payload"]
            samples = state["samples"]
            cursor = int(state["cursor"])
            while cursor < len(samples) and samples[cursor].epoch_ms <= timestamp_ms:
                current_payload = samples[cursor].payload
                cursor += 1
            if point_index > 0 and current_payload != state["previous_payload"]:
                if current_payload is not None or state["previous_payload"] is not None:
                    active_imu_ids.append(series.imu_id)
            state["cursor"] = cursor
            state["current_payload"] = current_payload

        points.append(
            {
                "frame_index": int(frame_index),
                "timestamp_ms": round(float(timestamp_ms), 3),
                "active_imu_count": len(active_imu_ids),
                "active_imu_ids": sorted(active_imu_ids),
            }
        )

        for series in series_list:
            states[series.imu_id]["previous_payload"] = states[series.imu_id]["current_payload"]

    return points


def _analyze_task(task: common.TaskInfo) -> Dict[str, Any]:
    frame_timestamps = base_prep.load_frame_timestamps(Path(task.timestamp_path))
    imu_series_list = [load_imu_series(Path(csv_path)) for csv_path in task.imu_paths]
    points = _build_activity_points(frame_timestamps, imu_series_list)
    payload_fields = list(imu_series_list[0].payload_fields) if imu_series_list else []
    return {
        "video_stem": task.video_stem,
        "time_axis": "frame_timestamp_ms",
        "source_timestamp_path": str(task.timestamp_path),
        "source_imu_paths": [str(path) for path in task.imu_paths],
        "payload_fields": payload_fields,
        "imu_ids": [series.imu_id for series in imu_series_list],
        "point_count": len(points),
        "points": points,
    }


def _write_outputs(output_dir: Path, sessions: List[Dict[str, Any]], batch_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for session in sessions:
        session_path = output_dir / f"{session['video_stem']}.active_imu_timeline.json"
        session_path.write_text(
            json.dumps(session, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    summary = {
        "batch_dir": str(batch_dir),
        "output_dir": str(output_dir),
        "time_axis": "frame_timestamp_ms",
        "session_count": len(sessions),
        "video_stems": [session["video_stem"] for session in sessions],
        "sessions": [
            {
                "video_stem": session["video_stem"],
                "imu_ids": session["imu_ids"],
                "point_count": session["point_count"],
                "output_path": str(output_dir / f"{session['video_stem']}.active_imu_timeline.json"),
            }
            for session in sessions
        ],
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def analyze_batch(
    batch_dir: Path,
    output_dir: Path | None = None,
    video_stems: Iterable[str] | None = None,
) -> Dict[str, Any]:
    batch_dir = batch_dir.resolve()
    selected = {item.strip() for item in (video_stems or []) if str(item).strip()}
    sessions: List[Dict[str, Any]] = []
    for task in common.load_tasks(batch_dir):
        if selected and task.video_stem not in selected:
            continue
        sessions.append(_analyze_task(task))

    result = {
        "batch_dir": str(batch_dir),
        "time_axis": "frame_timestamp_ms",
        "session_count": len(sessions),
        "video_stems": [session["video_stem"] for session in sessions],
        "sessions": sessions,
        "output_dir": str(output_dir.resolve()) if output_dir is not None else None,
    }
    if output_dir is not None:
        _write_outputs(output_dir.resolve(), sessions, batch_dir)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze stage-1 IMU activity on a unified real-time frame axis")
    parser.add_argument("--batch-dir", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: <batch>/analysis/stage1_imu_activity)",
    )
    parser.add_argument(
        "--video-stem",
        action="append",
        default=[],
        help="Optional repeated filter; only analyze matching session stems",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir or (args.batch_dir.resolve() / "analysis" / "stage1_imu_activity")
    result = analyze_batch(
        batch_dir=args.batch_dir,
        output_dir=output_dir,
        video_stems=args.video_stem,
    )
    print(
        json.dumps(
            {
                "batch_dir": result["batch_dir"],
                "time_axis": result["time_axis"],
                "session_count": result["session_count"],
                "video_stems": result["video_stems"],
                "output_dir": result["output_dir"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
