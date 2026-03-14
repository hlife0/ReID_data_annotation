#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import cv2

TARGET_VIDEO_STEMS = [
    "20260211_171423",
    "20260211_172522",
    "20260211_171724",
    "20260211_172257",
]

OUTPUT_COLUMNS = [
    "video_stem",
    "frame_index",
    "timestamp_ms",
    "track_id",
    "bbox_x",
    "bbox_y",
    "bbox_w",
    "bbox_h",
    "score",
    "class_name",
    "imu_id",
    "source",
    "review_state",
]


@dataclass
class Task:
    video_stem: str
    video_path: Path
    timestamp_path: Path
    imu_paths: List[Path]
    status: str
    priority: int
    blocked_reason: str = ""


@dataclass
class TrackState:
    track_id: int
    bbox: Tuple[float, float, float, float]  # x, y, w, h
    last_frame_index: int


class RunLogger:
    def __init__(self, run_log_path: Path, error_log_path: Path) -> None:
        self.run_log_path = run_log_path
        self.error_log_path = error_log_path
        self.run_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.error_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.run_log_path.write_text("", encoding="utf-8")
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
        description="Run A0/A1/A2 prelabel pipeline for required videos"
    )
    parser.add_argument(
        "--required-root",
        type=Path,
        default=Path("./data/required"),
        help="Input required data root (must be symlink path under current workspace)",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("."),
        help="Batch output root (current directory by default)",
    )
    parser.add_argument(
        "--batch-date",
        type=str,
        default=datetime.now().strftime("%Y%m%d"),
        help="Batch date in YYYYMMDD",
    )
    parser.add_argument(
        "--batch-version",
        type=int,
        default=None,
        help="Optional fixed version number (NN in vNN)",
    )
    parser.add_argument(
        "--backend",
        type=str,
        choices=["ultralytics", "hog", "bytetrack"],
        default="ultralytics",
        help="Prelabel backend",
    )
    parser.add_argument(
        "--frame-stride",
        type=int,
        default=1,
        help="Run inference every N frames (>=1)",
    )
    parser.add_argument(
        "--detect-score-threshold",
        type=float,
        default=0.2,
        help="Detection confidence threshold",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="yolo11x.pt",
        help="Ultralytics model name/path",
    )
    parser.add_argument(
        "--tracker",
        type=str,
        default="botsort.yaml",
        help="Ultralytics tracker config",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cuda:3",
        help="Torch device, e.g. cuda:3, cuda:0, cpu",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=1280,
        help="Ultralytics inference size",
    )
    parser.add_argument(
        "--yolo-config-dir",
        type=Path,
        default=Path("./.yolo_cfg"),
        help="Writable config/cache directory for Ultralytics",
    )
    parser.add_argument(
        "--max-track-age",
        type=int,
        default=8,
        help="HOG fallback only: maximum unmatched frames before dropping a track",
    )
    parser.add_argument(
        "--iou-threshold",
        type=float,
        default=0.3,
        help="HOG fallback only: minimum IoU for association",
    )
    parser.add_argument(
        "--only-task-extraction",
        action="store_true",
        help="Run only Step A0/A1 (input inspection + task manifest), skip A2 and validation",
    )
    parser.add_argument(
        "--bytetrack-root",
        type=Path,
        default=Path("/data/hrli/ByteTrack"),
        help="ByteTrack repo root (contains tools/track_api.py and venv/)",
    )
    parser.add_argument(
        "--bytetrack-python",
        type=Path,
        default=None,
        help="Optional explicit ByteTrack venv python path (default: <bytetrack_root>/venv/bin/python)",
    )
    parser.add_argument(
        "--bytetrack-exp-file",
        type=str,
        default="exps/example/mot/yolox_x_mix_det.py",
        help="ByteTrack exp file (relative to ByteTrack repo if not absolute)",
    )
    parser.add_argument(
        "--bytetrack-ckpt",
        type=str,
        default="pretrained/bytetrack_x_mot17.pth.tar",
        help="ByteTrack checkpoint (relative to ByteTrack repo if not absolute)",
    )
    parser.add_argument(
        "--bytetrack-device",
        type=str,
        choices=["gpu", "cpu"],
        default="gpu",
        help="ByteTrack device",
    )
    parser.add_argument(
        "--bytetrack-gpu-id",
        type=str,
        default=None,
        help="CUDA_VISIBLE_DEVICES for ByteTrack (only when device=gpu)",
    )
    parser.add_argument(
        "--bytetrack-fp16",
        action="store_true",
        help="Enable fp16 for ByteTrack",
    )
    parser.add_argument(
        "--bytetrack-fuse",
        action="store_true",
        help="Enable conv+bn fuse for ByteTrack",
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


def check_timestamp_csv(path: Path) -> Tuple[bool, str]:
    if not path.exists():
        return False, "missing timestamp csv"
    try:
        with path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames or []
            required = {"frame_index", "timestamp_ms"}
            if not required.issubset(set(fields)):
                return False, f"timestamp csv missing required columns, got={fields}"
            next(reader, None)
    except Exception as exc:
        return False, f"timestamp csv read failed: {exc}"
    return True, ""


def step_a0_input_inspection(required_root: Path, logger: RunLogger) -> List[Task]:
    tasks: List[Task] = []
    logger.info("Step A0 start: input inspection")
    for priority, stem in enumerate(TARGET_VIDEO_STEMS, start=1):
        video_path = required_root / stem / "video" / f"{stem}_retimed.mp4"
        timestamp_path = required_root / stem / "video" / f"{stem}_frame_timestamps_retimed.csv"
        imu_paths = sorted((required_root / stem / "imu").glob("*.csv"))

        reasons: List[str] = []
        if not video_path.exists():
            reasons.append("missing retimed video")

        ts_ok, ts_reason = check_timestamp_csv(timestamp_path)
        if not ts_ok:
            reasons.append(ts_reason)

        if len(imu_paths) != 2:
            reasons.append(f"imu csv count is {len(imu_paths)}, expected 2")

        status = "todo" if not reasons else "blocked"
        reason_text = "; ".join(reasons)
        task = Task(
            video_stem=stem,
            video_path=video_path,
            timestamp_path=timestamp_path,
            imu_paths=imu_paths,
            status=status,
            priority=priority,
            blocked_reason=reason_text,
        )
        tasks.append(task)

        logger.info(
            f"A0 {stem}: status={status}, video_exists={video_path.exists()}, "
            f"timestamp_exists={timestamp_path.exists()}, imu_count={len(imu_paths)}"
        )
        if status == "blocked":
            logger.error(f"A0 blocked {stem}: {reason_text}")

    return tasks


def write_manifest(tasks: Iterable[Task], manifest_path: Path, logger: RunLogger) -> None:
    logger.info("Step A1 start: writing manifests/annotation_tasks.csv")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "video_stem",
                "video_path",
                "timestamp_path",
                "imu_paths",
                "status",
                "priority",
            ]
        )
        for task in tasks:
            writer.writerow(
                [
                    task.video_stem,
                    str(task.video_path),
                    str(task.timestamp_path),
                    ";".join(str(p) for p in task.imu_paths),
                    task.status,
                    task.priority,
                ]
            )
    logger.info(f"A1 manifest written: {manifest_path}")


def load_timestamps(path: Path) -> Dict[int, str]:
    mapping: Dict[int, str] = {}
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            frame_index = int(row["frame_index"])
            mapping[frame_index] = row["timestamp_ms"]
    return mapping


def iou_xywh(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    a_x2 = ax + aw
    a_y2 = ay + ah
    b_x2 = bx + bw
    b_y2 = by + bh

    inter_x1 = max(ax, bx)
    inter_y1 = max(ay, by)
    inter_x2 = min(a_x2, b_x2)
    inter_y2 = min(a_y2, b_y2)
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter = inter_w * inter_h
    if inter <= 0.0:
        return 0.0
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def apply_nms(
    boxes: List[Tuple[float, float, float, float]],
    scores: List[float],
    nms_threshold: float = 0.45,
) -> List[int]:
    if not boxes:
        return []
    int_boxes = [[int(x), int(y), int(w), int(h)] for (x, y, w, h) in boxes]
    kept = cv2.dnn.NMSBoxes(int_boxes, scores, score_threshold=0.0, nms_threshold=nms_threshold)
    if len(kept) == 0:
        return []
    return [int(i[0]) if hasattr(i, "__len__") else int(i) for i in kept]


def detect_people_hog(
    frame,
    hog: cv2.HOGDescriptor,
    score_threshold: float,
    infer_width: int = 960,
) -> Tuple[List[Tuple[float, float, float, float]], List[float]]:
    h, w = frame.shape[:2]
    if w > infer_width:
        scale = w / infer_width
        resized = cv2.resize(frame, (infer_width, int(h / scale)))
    else:
        scale = 1.0
        resized = frame

    rects, weights = hog.detectMultiScale(
        resized,
        winStride=(8, 8),
        padding=(8, 8),
        scale=1.05,
    )

    boxes: List[Tuple[float, float, float, float]] = []
    scores: List[float] = []
    for (x, y, bw, bh), wt in zip(rects, weights):
        score = float(wt)
        if score < score_threshold:
            continue
        ox = float(x * scale)
        oy = float(y * scale)
        ow = float(bw * scale)
        oh = float(bh * scale)
        if ow <= 0 or oh <= 0:
            continue
        boxes.append((ox, oy, ow, oh))
        scores.append(score)

    kept = apply_nms(boxes, scores)
    return [boxes[i] for i in kept], [scores[i] for i in kept]


def associate_tracks(
    frame_index: int,
    detections: List[Tuple[float, float, float, float]],
    tracks: Dict[int, TrackState],
    next_track_id: int,
    max_track_age: int,
    iou_threshold: float,
) -> Tuple[List[int], int]:
    active_track_ids = [
        tid for tid, t in tracks.items() if frame_index - t.last_frame_index <= max_track_age
    ]

    assigned_detection_to_track: Dict[int, int] = {}
    used_tracks: set[int] = set()
    used_detections: set[int] = set()

    while True:
        best_iou = iou_threshold
        best_det = -1
        best_track = -1
        for det_idx, det_bbox in enumerate(detections):
            if det_idx in used_detections:
                continue
            for track_id in active_track_ids:
                if track_id in used_tracks:
                    continue
                iou = iou_xywh(det_bbox, tracks[track_id].bbox)
                if iou >= best_iou:
                    best_iou = iou
                    best_det = det_idx
                    best_track = track_id
        if best_det < 0:
            break
        assigned_detection_to_track[best_det] = best_track
        used_detections.add(best_det)
        used_tracks.add(best_track)

    result_track_ids: List[int] = []
    for det_idx, det_bbox in enumerate(detections):
        if det_idx in assigned_detection_to_track:
            tid = assigned_detection_to_track[det_idx]
        else:
            tid = next_track_id
            next_track_id += 1
        tracks[tid] = TrackState(track_id=tid, bbox=det_bbox, last_frame_index=frame_index)
        result_track_ids.append(tid)

    stale_track_ids = [tid for tid, t in tracks.items() if frame_index - t.last_frame_index > max_track_age]
    for tid in stale_track_ids:
        tracks.pop(tid, None)

    return result_track_ids, next_track_id


def run_one_video_hog(
    task: Task,
    output_csv: Path,
    logger: RunLogger,
    frame_stride: int,
    max_track_age: int,
    iou_threshold: float,
    detect_score_threshold: float,
) -> None:
    timestamps = load_timestamps(task.timestamp_path)
    cap = cv2.VideoCapture(str(task.video_path))
    if not cap.isOpened():
        logger.error(f"A2 failed {task.video_stem}: cannot open video {task.video_path}")
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        with output_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(OUTPUT_COLUMNS)
        return

    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(OUTPUT_COLUMNS)

        tracks: Dict[int, TrackState] = {}
        next_track_id = 1
        frame_index = 0
        total_written = 0
        missing_timestamp_count = 0

        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame_index += 1
            if frame_stride > 1 and ((frame_index - 1) % frame_stride != 0):
                continue

            timestamp_ms = timestamps.get(frame_index)
            if timestamp_ms is None:
                missing_timestamp_count += 1
                continue

            detections, scores = detect_people_hog(
                frame=frame,
                hog=hog,
                score_threshold=detect_score_threshold,
            )
            if not detections:
                continue

            track_ids, next_track_id = associate_tracks(
                frame_index=frame_index,
                detections=detections,
                tracks=tracks,
                next_track_id=next_track_id,
                max_track_age=max_track_age,
                iou_threshold=iou_threshold,
            )

            for bbox, score, track_id in zip(detections, scores, track_ids):
                x, y, w, h = bbox
                if w <= 0 or h <= 0:
                    continue
                writer.writerow(
                    [
                        task.video_stem,
                        frame_index,
                        timestamp_ms,
                        track_id,
                        f"{x:.3f}",
                        f"{y:.3f}",
                        f"{w:.3f}",
                        f"{h:.3f}",
                        f"{score:.6f}",
                        "person",
                        "unknown",
                        "auto",
                        "pending",
                    ]
                )
                total_written += 1

    cap.release()
    if missing_timestamp_count > 0:
        logger.error(
            f"A2 {task.video_stem}: {missing_timestamp_count} sampled frames had no timestamp_ms and were skipped"
        )
    if total_written == 0:
        logger.error(f"A2 {task.video_stem}: model output empty")
    logger.info(f"A2 done {task.video_stem}: rows_written={total_written}, output={output_csv}")


def run_one_video_ultralytics(
    task: Task,
    output_csv: Path,
    logger: RunLogger,
    frame_stride: int,
    detect_score_threshold: float,
    model_name: str,
    tracker: str,
    device: str,
    imgsz: int,
    yolo_config_dir: Path,
) -> None:
    yolo_config_dir.mkdir(parents=True, exist_ok=True)
    os.environ["YOLO_CONFIG_DIR"] = str(yolo_config_dir.resolve())
    try:
        from ultralytics import YOLO
    except Exception as exc:  # pragma: no cover
        raise SystemExit(
            "ultralytics is required for backend=ultralytics. "
            "Install with: .venv/bin/python -m pip install ultralytics"
        ) from exc

    timestamps = load_timestamps(task.timestamp_path)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    total_written = 0
    missing_timestamp_count = 0

    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(OUTPUT_COLUMNS)

        model = YOLO(model_name)
        stream = model.track(
            source=str(task.video_path),
            stream=True,
            persist=True,
            conf=detect_score_threshold,
            classes=[0],
            tracker=tracker,
            verbose=False,
            device=device,
            imgsz=imgsz,
            half=device.startswith("cuda"),
        )

        for frame_index, result in enumerate(stream, start=1):
            if frame_stride > 1 and ((frame_index - 1) % frame_stride != 0):
                continue

            timestamp_ms = timestamps.get(frame_index)
            if timestamp_ms is None:
                missing_timestamp_count += 1
                continue

            boxes = result.boxes
            if boxes is None or len(boxes) == 0:
                continue

            xywh = boxes.xywh.cpu().numpy()
            confs = boxes.conf.cpu().numpy() if boxes.conf is not None else None
            ids = boxes.id.cpu().numpy() if boxes.id is not None else None

            for i in range(len(xywh)):
                cx, cy, w, h = [float(v) for v in xywh[i]]
                if w <= 0 or h <= 0:
                    continue
                # Convert Ultralytics center-xywh to COCO top-left-xywh.
                x = cx - w / 2.0
                y = cy - h / 2.0
                score = float(confs[i]) if confs is not None else 0.0
                track_id = int(ids[i]) if ids is not None else i
                writer.writerow(
                    [
                        task.video_stem,
                        frame_index,
                        timestamp_ms,
                        track_id,
                        f"{x:.3f}",
                        f"{y:.3f}",
                        f"{w:.3f}",
                        f"{h:.3f}",
                        f"{score:.6f}",
                        "person",
                        "unknown",
                        "auto",
                        "pending",
                    ]
                )
                total_written += 1

    if missing_timestamp_count > 0:
        logger.error(
            f"A2 {task.video_stem}: {missing_timestamp_count} sampled frames had no timestamp_ms and were skipped"
        )
    if total_written == 0:
        logger.error(f"A2 {task.video_stem}: model output empty")
    logger.info(f"A2 done {task.video_stem}: rows_written={total_written}, output={output_csv}")


def _iter_mot_rows(result_txt: Path):
    with result_txt.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            if len(parts) < 7:
                continue
            try:
                frame0 = int(float(parts[0]))
                track_id = int(float(parts[1]))
                x = float(parts[2])
                y = float(parts[3])
                w = float(parts[4])
                h = float(parts[5])
                score = float(parts[6])
            except Exception:
                continue
            if w <= 0 or h <= 0:
                continue
            yield frame0, track_id, x, y, w, h, score


def run_one_video_bytetrack(
    task: Task,
    output_csv: Path,
    logger: RunLogger,
    frame_stride: int,
    bytetrack_root: Path,
    bytetrack_python: Path | None,
    exp_file: str,
    ckpt: str,
    device: str,
    gpu_id: str | None,
    fp16: bool,
    fuse: bool,
    logs_dir: Path,
) -> None:
    timestamps = load_timestamps(task.timestamp_path)
    track_api = bytetrack_root / "tools" / "track_api.py"
    if not track_api.exists():
        logger.error(f"A2 failed {task.video_stem}: track_api.py not found under {bytetrack_root}")
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        with output_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(OUTPUT_COLUMNS)
        return

    if bytetrack_python is None:
        bytetrack_python = bytetrack_root / "venv" / "bin" / "python"
    if not bytetrack_python.exists():
        logger.error(
            f"A2 failed {task.video_stem}: ByteTrack python not found at {bytetrack_python}"
        )
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        with output_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(OUTPUT_COLUMNS)
        return

    real_video = task.video_path.resolve()
    if real_video != task.video_path:
        logger.info(f"A2 {task.video_stem}: resolved symlink video path to {real_video}")

    logs_dir.mkdir(parents=True, exist_ok=True)
    summary_path = (logs_dir / f"bytetrack_{task.video_stem}.summary.json").resolve()

    cmd = [
        str(bytetrack_python),
        str(track_api),
        "run",
        "--video",
        str(real_video),
        "--exp-file",
        exp_file,
        "--ckpt",
        ckpt,
        "--device",
        device,
        "--json-out",
        str(summary_path),
    ]
    if device == "gpu" and gpu_id:
        cmd += ["--gpu-id", str(gpu_id)]
    if fp16:
        cmd.append("--fp16")
    if fuse:
        cmd.append("--fuse")

    if frame_stride > 1:
        logger.info(
            f"A2 {task.video_stem}: frame_stride={frame_stride} applied after ByteTrack run"
        )

    logger.info(f"A2 ByteTrack start {task.video_stem}: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        cwd=str(bytetrack_root),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "")[-2000:]
        logger.error(f"A2 ByteTrack failed {task.video_stem}: {tail}")
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        with output_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(OUTPUT_COLUMNS)
        return

    if not summary_path.exists():
        logger.error(
            f"A2 ByteTrack failed {task.video_stem}: summary json not found {summary_path}"
        )
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        with output_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(OUTPUT_COLUMNS)
        return

    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        result_txt = Path(summary["output"]["result_txt"])
    except Exception as exc:
        logger.error(f"A2 ByteTrack failed {task.video_stem}: parse summary error {exc}")
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        with output_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(OUTPUT_COLUMNS)
        return

    if not result_txt.exists():
        logger.error(
            f"A2 ByteTrack failed {task.video_stem}: result txt not found {result_txt}"
        )
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        with output_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(OUTPUT_COLUMNS)
        return

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    total_written = 0
    missing_timestamp_count = 0
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(OUTPUT_COLUMNS)
        for frame0, track_id, x, y, w, h, score in _iter_mot_rows(result_txt):
            frame_index = frame0 + 1
            if frame_stride > 1 and ((frame_index - 1) % frame_stride != 0):
                continue
            timestamp_ms = timestamps.get(frame_index)
            if timestamp_ms is None:
                missing_timestamp_count += 1
                continue
            writer.writerow(
                [
                    task.video_stem,
                    frame_index,
                    timestamp_ms,
                    track_id,
                    f"{x:.3f}",
                    f"{y:.3f}",
                    f"{w:.3f}",
                    f"{h:.3f}",
                    f"{score:.6f}",
                    "person",
                    "unknown",
                    "auto",
                    "pending",
                ]
            )
            total_written += 1

    if missing_timestamp_count > 0:
        logger.error(
            f"A2 {task.video_stem}: {missing_timestamp_count} ByteTrack frames had no timestamp_ms"
        )
    if total_written == 0:
        logger.error(f"A2 {task.video_stem}: ByteTrack output empty")
    logger.info(f"A2 done {task.video_stem}: rows_written={total_written}, output={output_csv}")


def run_one_video(
    task: Task,
    output_csv: Path,
    logger: RunLogger,
    args: argparse.Namespace,
    logs_dir: Path,
) -> None:
    if args.backend == "ultralytics":
        run_one_video_ultralytics(
            task=task,
            output_csv=output_csv,
            logger=logger,
            frame_stride=args.frame_stride,
            detect_score_threshold=args.detect_score_threshold,
            model_name=args.model,
            tracker=args.tracker,
            device=args.device,
            imgsz=args.imgsz,
            yolo_config_dir=args.yolo_config_dir,
        )
        return
    if args.backend == "bytetrack":
        run_one_video_bytetrack(
            task=task,
            output_csv=output_csv,
            logger=logger,
            frame_stride=args.frame_stride,
            bytetrack_root=args.bytetrack_root,
            bytetrack_python=args.bytetrack_python,
            exp_file=args.bytetrack_exp_file,
            ckpt=args.bytetrack_ckpt,
            device=args.bytetrack_device,
            gpu_id=args.bytetrack_gpu_id,
            fp16=args.bytetrack_fp16,
            fuse=args.bytetrack_fuse,
            logs_dir=logs_dir,
        )
        return

    run_one_video_hog(
        task=task,
        output_csv=output_csv,
        logger=logger,
        frame_stride=args.frame_stride,
        max_track_age=args.max_track_age,
        iou_threshold=args.iou_threshold,
        detect_score_threshold=args.detect_score_threshold,
    )


def validate_outputs(tasks: Iterable[Task], pseudo_dir: Path, logger: RunLogger) -> bool:
    ok = True
    required_cols = set(OUTPUT_COLUMNS)

    for task in tasks:
        if task.status != "todo":
            continue
        csv_path = pseudo_dir / f"{task.video_stem}.auto.csv"
        if not csv_path.exists():
            logger.error(f"Validation failed: missing output csv for todo video {task.video_stem}")
            ok = False
            continue

        with csv_path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            cols = set(reader.fieldnames or [])
            if cols != required_cols:
                logger.error(
                    f"Validation failed {task.video_stem}: column mismatch. "
                    f"expected={sorted(required_cols)}, got={sorted(cols)}"
                )
                ok = False
                continue

            row_count = 0
            bad_bbox = 0
            for row in reader:
                row_count += 1
                try:
                    bw = float(row["bbox_w"])
                    bh = float(row["bbox_h"])
                except Exception:
                    bad_bbox += 1
                    continue
                if bw <= 0 or bh <= 0:
                    bad_bbox += 1
            if bad_bbox > 0:
                logger.error(f"Validation failed {task.video_stem}: invalid bbox rows={bad_bbox}")
                ok = False
            logger.info(f"Validation {task.video_stem}: rows={row_count}, invalid_bbox={bad_bbox}")

    return ok


def main() -> None:
    args = parse_args()
    if args.frame_stride < 1:
        raise SystemExit("--frame-stride must be >= 1")

    batch_dir = find_batch_dir(args.output_root, args.batch_date, args.batch_version)
    manifests_dir = batch_dir / "manifests"
    pseudo_dir = batch_dir / "pseudo_labels"
    logs_dir = batch_dir / "logs"
    manifest_path = manifests_dir / "annotation_tasks.csv"
    run_log_path = logs_dir / "run.log"
    error_log_path = logs_dir / "errors.log"

    logger = RunLogger(run_log_path=run_log_path, error_log_path=error_log_path)
    logger.info(f"Batch dir: {batch_dir}")
    logger.info(
        f"Config backend={args.backend}, frame_stride={args.frame_stride}, "
        f"conf={args.detect_score_threshold}, device={args.device}"
    )
    if args.backend == "ultralytics":
        logger.info(
            f"Ultralytics config model={args.model}, tracker={args.tracker}, imgsz={args.imgsz}, "
            f"yolo_config_dir={args.yolo_config_dir}"
        )
    if args.backend == "bytetrack":
        logger.info(
            "ByteTrack config "
            f"root={args.bytetrack_root}, exp_file={args.bytetrack_exp_file}, ckpt={args.bytetrack_ckpt}, "
            f"device={args.bytetrack_device}, gpu_id={args.bytetrack_gpu_id}, "
            f"fp16={args.bytetrack_fp16}, fuse={args.bytetrack_fuse}"
        )

    tasks = step_a0_input_inspection(required_root=args.required_root, logger=logger)
    write_manifest(tasks=tasks, manifest_path=manifest_path, logger=logger)

    if args.only_task_extraction:
        logger.info("Only-task-extraction mode enabled: skip Step A2 and validation")
        logger.info("Batch finished: PASS (A0/A1 only)")
        return

    logger.info("Step A2 start: pseudo labeling")
    for task in tasks:
        if task.status != "todo":
            logger.info(f"A2 skip blocked {task.video_stem}: {task.blocked_reason}")
            continue
        out_csv = pseudo_dir / f"{task.video_stem}.auto.csv"
        run_one_video(task=task, output_csv=out_csv, logger=logger, args=args, logs_dir=logs_dir)

    logger.info("Validation start")
    validated = validate_outputs(tasks=tasks, pseudo_dir=pseudo_dir, logger=logger)
    if validated:
        logger.info("Batch finished: PASS")
    else:
        logger.error("Batch finished: FAIL")


if __name__ == "__main__":
    main()
