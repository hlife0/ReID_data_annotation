#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import cv2

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render final merged annotations onto source video")
    parser.add_argument("--batch-dir", type=Path, required=True, help="Batch directory path")
    parser.add_argument("--video-stem", type=str, default=None, help="Optional single video stem")
    return parser.parse_args()


def load_manifest_video_path(manifest_path: Path, video_stem: str) -> Path:
    with manifest_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("video_stem") != video_stem:
                continue
            video_path = Path(row["video_path"])
            if not video_path.is_absolute():
                video_path = REPO_ROOT / video_path
            return video_path
    raise SystemExit(f"video_stem not found in manifest: {video_stem}")


def color_for_slot(slot: str) -> Tuple[int, int, int]:
    return (44, 154, 88) if slot == "p1" else (84, 96, 110)


def load_rows_by_frame(csv_path: Path) -> Dict[int, dict]:
    rows: Dict[int, dict] = {}
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                frame_index = int(row["frame_index"])
            except Exception:
                continue
            rows[frame_index] = row
    return rows


def to_xyxy(x: float, y: float, w: float, h: float, frame_w: int, frame_h: int) -> Tuple[int, int, int, int] | None:
    x1 = max(0, min(frame_w - 1, int(round(x))))
    y1 = max(0, min(frame_h - 1, int(round(y))))
    x2 = max(0, min(frame_w - 1, int(round(x + w))))
    y2 = max(0, min(frame_h - 1, int(round(y + h))))
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def draw_slot(frame, row: dict, slot: str, frame_w: int, frame_h: int) -> None:
    is_absent = row[f"{slot}_is_absent"] == "1"
    label = f"{slot.upper()} {row[f'{slot}_final_source']}"
    color = color_for_slot(slot)
    if is_absent:
        cv2.putText(
            frame,
            f"{slot.upper()}: absent | {row[f'{slot}_final_source']}",
            (10, 54 if slot == "p1" else 82),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
            cv2.LINE_AA,
        )
        return
    try:
        x = float(row[f"{slot}_bbox_x"])
        y = float(row[f"{slot}_bbox_y"])
        w = float(row[f"{slot}_bbox_w"])
        h = float(row[f"{slot}_bbox_h"])
    except Exception:
        return
    xyxy = to_xyxy(x, y, w, h, frame_w, frame_h)
    if xyxy is None:
        return
    x1, y1, x2, y2 = xyxy
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    cv2.putText(
        frame,
        label,
        (x1, max(18, y1 - 6)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        color,
        2,
        cv2.LINE_AA,
    )


def render_one_video(batch_dir: Path, video_stem: str) -> Path:
    manifest_path = batch_dir / "manifests" / "annotation_tasks.csv"
    final_csv_path = batch_dir / "final_annotations" / f"{video_stem}.final.csv"
    output_dir = batch_dir / "final_annotations" / "videos"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{video_stem}.final.boxed.mp4"
    tmp_output_path = output_dir / f"{video_stem}.final.boxed.tmp.mp4"

    if not manifest_path.exists():
        raise SystemExit(f"manifest not found: {manifest_path}")
    if not final_csv_path.exists():
        raise SystemExit(f"final annotation csv not found: {final_csv_path}")

    video_path = load_manifest_video_path(manifest_path, video_stem)
    if not video_path.exists():
        raise SystemExit(f"source video not found: {video_path}")

    rows_by_frame = load_rows_by_frame(final_csv_path)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise SystemExit(f"failed to open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    writer = cv2.VideoWriter(str(tmp_output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (frame_w, frame_h))
    if not writer.isOpened():
        cap.release()
        raise SystemExit(f"failed to create temp output video: {tmp_output_path}")

    frame_idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame_idx += 1
        row = rows_by_frame.get(frame_idx)
        if row is not None:
            draw_slot(frame, row, "p1", frame_w, frame_h)
            draw_slot(frame, row, "p2", frame_w, frame_h)
        cv2.putText(
            frame,
            f"frame:{frame_idx}",
            (10, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )
        writer.write(frame)
        if frame_idx % 300 == 0:
            print(f"{video_stem} progress {frame_idx}/{total_frames}")

    cap.release()
    writer.release()
    ffmpeg_cmd = [
        "ffmpeg", "-y", "-i", str(tmp_output_path),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output_path),
    ]
    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit("ffmpeg h264 transcode failed:\n" + result.stderr[-2000:])
    tmp_output_path.unlink(missing_ok=True)
    return output_path


def main() -> None:
    args = parse_args()
    batch_dir = resolve_repo_path(args.batch_dir)
    if not batch_dir.exists():
        raise SystemExit(f"batch directory does not exist: {batch_dir}")
    stems = [args.video_stem] if args.video_stem else [
        "20260211_171423", "20260211_171724", "20260211_172257", "20260211_172522"
    ]
    for stem in stems:
        out_path = render_one_video(batch_dir, stem)
        print(f"rendered_video={out_path}")


if __name__ == "__main__":
    main()
