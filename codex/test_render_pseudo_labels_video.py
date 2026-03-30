#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import cv2

REPO_ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Temporary helper: render pseudo labels onto video for one video_stem."
    )
    parser.add_argument(
        "--batch-dir",
        type=Path,
        required=True,
        help="Path to batch_<YYYYMMDD>_vNN directory",
    )
    parser.add_argument(
        "--video-stem",
        type=str,
        required=True,
        help="Target video_stem to render",
    )
    parser.add_argument(
        "--bbox-format",
        type=str,
        choices=["center_xywh", "coco_xywh"],
        default="coco_xywh",
        help="How bbox_x,bbox_y,bbox_w,bbox_h should be interpreted",
    )
    return parser.parse_args()


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def color_for_track(track_id: int) -> Tuple[int, int, int]:
    # Deterministic color from track id.
    b = (37 * track_id + 17) % 255
    g = (67 * track_id + 29) % 255
    r = (97 * track_id + 53) % 255
    return int(b), int(g), int(r)


def load_manifest_video_path(manifest_path: Path, video_stem: str, workspace: Path) -> Path:
    with manifest_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("video_stem") != video_stem:
                continue
            video_path = Path(row["video_path"])
            if not video_path.is_absolute():
                video_path = workspace / video_path
            return video_path
    raise SystemExit(f"video_stem not found in manifest: {video_stem}")


def load_boxes_by_frame(csv_path: Path) -> Dict[int, List[dict]]:
    boxes_by_frame: Dict[int, List[dict]] = defaultdict(list)
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                frame_index = int(row["frame_index"])
                row["bbox_x"] = float(row["bbox_x"])
                row["bbox_y"] = float(row["bbox_y"])
                row["bbox_w"] = float(row["bbox_w"])
                row["bbox_h"] = float(row["bbox_h"])
                row["score"] = float(row["score"])
                row["track_id"] = int(float(row["track_id"]))
            except Exception:
                continue
            boxes_by_frame[frame_index].append(row)
    return boxes_by_frame


def to_xyxy(
    x: float, y: float, w: float, h: float, fmt: str, frame_w: int, frame_h: int
) -> Tuple[int, int, int, int] | None:
    if fmt == "center_xywh":
        x1 = x - w / 2.0
        y1 = y - h / 2.0
        x2 = x + w / 2.0
        y2 = y + h / 2.0
    else:
        x1 = x
        y1 = y
        x2 = x + w
        y2 = y + h

    x1 = max(0, min(frame_w - 1, int(round(x1))))
    y1 = max(0, min(frame_h - 1, int(round(y1))))
    x2 = max(0, min(frame_w - 1, int(round(x2))))
    y2 = max(0, min(frame_h - 1, int(round(y2))))
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def main() -> None:
    args = parse_args()
    workspace = REPO_ROOT
    batch_dir = resolve_repo_path(args.batch_dir)

    manifest_path = batch_dir / "manifests" / "annotation_tasks.csv"
    pseudo_csv_path = batch_dir / "pseudo_labels" / f"{args.video_stem}.auto.csv"
    output_dir = batch_dir / "pseudo_labels" / "videos"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{args.video_stem}.boxed.mp4"
    tmp_output_path = output_dir / f"{args.video_stem}.boxed.tmp.mp4"

    if not manifest_path.exists():
        raise SystemExit(f"manifest not found: {manifest_path}")
    if not pseudo_csv_path.exists():
        raise SystemExit(f"pseudo label csv not found: {pseudo_csv_path}")

    video_path = load_manifest_video_path(manifest_path, args.video_stem, workspace)
    if not video_path.exists():
        raise SystemExit(f"source video not found: {video_path}")

    boxes_by_frame = load_boxes_by_frame(pseudo_csv_path)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise SystemExit(f"failed to open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    writer = cv2.VideoWriter(
        str(tmp_output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (frame_w, frame_h),
    )
    if not writer.isOpened():
        cap.release()
        raise SystemExit(f"failed to create temp output video: {tmp_output_path}")

    frame_idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame_idx += 1

        for row in boxes_by_frame.get(frame_idx, []):
            xyxy = to_xyxy(
                x=row["bbox_x"],
                y=row["bbox_y"],
                w=row["bbox_w"],
                h=row["bbox_h"],
                fmt=args.bbox_format,
                frame_w=frame_w,
                frame_h=frame_h,
            )
            if xyxy is None:
                continue
            x1, y1, x2, y2 = xyxy
            tid = row["track_id"]
            score = row["score"]
            color = color_for_track(tid)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            label = f"id:{tid} {score:.2f}"
            cv2.putText(
                frame,
                label,
                (x1, max(15, y1 - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
                cv2.LINE_AA,
            )

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
            print(f"progress {frame_idx}/{total_frames}")

    cap.release()
    writer.release()
    # Re-encode to H.264 for broad player compatibility.
    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(tmp_output_path),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(
            "ffmpeg h264 transcode failed:\n"
            f"{result.stderr[-2000:]}"
        )
    tmp_output_path.unlink(missing_ok=True)
    print(f"rendered_video={output_path}")


if __name__ == "__main__":
    main()
