#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import itertools
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET_VIDEO_STEMS = [
    "20260211_171423",
    "20260211_171724",
    "20260211_172257",
    "20260211_172522",
]
FINAL_COLUMNS = [
    "video_stem",
    "frame_index",
    "timestamp_ms",
    "p1_bbox_x",
    "p1_bbox_y",
    "p1_bbox_w",
    "p1_bbox_h",
    "p1_is_absent",
    "p1_final_source",
    "p1_ref_annotation_ids",
    "p1_ref_annotators",
    "p1_ref_dice",
    "p2_bbox_x",
    "p2_bbox_y",
    "p2_bbox_w",
    "p2_bbox_h",
    "p2_is_absent",
    "p2_final_source",
    "p2_ref_annotation_ids",
    "p2_ref_annotators",
    "p2_ref_dice",
]
HUMAN_SOURCES = {"manual_draw", "manual_param"}
AI_SOURCES = {"ai"}
ABSENT_SOURCE = "absent"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_float(value: Any) -> float:
    return float(f"{float(value):.6f}")


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


class RunLogger:
    def __init__(self, run_log_path: Path, error_log_path: Path) -> None:
        self.run_log_path = run_log_path
        self.error_log_path = error_log_path
        self.run_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.error_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.run_log_path.touch(exist_ok=True)
        self.error_log_path.touch(exist_ok=True)

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build final per-video annotations from annotations + reviews")
    parser.add_argument(
        "--batch-dir",
        type=Path,
        default=None,
        help="Batch directory path, e.g. ./annotation/batch_20260314_v05",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT / "annotation",
        help="Root directory containing annotation/batch_*_vNN",
    )
    return parser.parse_args()


def find_latest_batch(root: Path) -> Path:
    pattern = re.compile(r"^batch_(\d{8})_v(\d{2})$")
    candidates = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        match = pattern.match(child.name)
        if not match:
            continue
        candidates.append((int(match.group(1)), int(match.group(2)), child))
    if not candidates:
        raise FileNotFoundError(f"no batch_*_vNN found under {root}")
    candidates.sort(key=lambda x: (x[0], x[1]))
    return candidates[-1][2]


def connect_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    names = {
        str(row["name"])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('frames','annotations','review_decisions')"
        ).fetchall()
    }
    missing = sorted({"frames", "annotations", "review_decisions"} - names)
    if missing:
        raise RuntimeError(f"required tables missing: {missing}")


def load_frames(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    return conn.execute(
        "SELECT video_stem, frame_index, timestamp_ms FROM frames WHERE video_stem IN ({}) ORDER BY video_stem, frame_index".format(
            ",".join("?" * len(TARGET_VIDEO_STEMS))
        ),
        TARGET_VIDEO_STEMS,
    ).fetchall()


def load_annotations(conn: sqlite3.Connection) -> Dict[Tuple[str, int], List[sqlite3.Row]]:
    rows = conn.execute(
        "SELECT * FROM annotations WHERE video_stem IN ({}) ORDER BY video_stem, frame_index, submitted_at, annotation_id".format(
            ",".join("?" * len(TARGET_VIDEO_STEMS))
        ),
        TARGET_VIDEO_STEMS,
    ).fetchall()
    grouped: Dict[Tuple[str, int], List[sqlite3.Row]] = {}
    for row in rows:
        grouped.setdefault((str(row["video_stem"]), int(row["frame_index"])), []).append(row)
    return grouped


def load_reviews(conn: sqlite3.Connection) -> Dict[Tuple[str, int], sqlite3.Row]:
    rows = conn.execute(
        "SELECT * FROM review_decisions WHERE video_stem IN ({}) ORDER BY video_stem, frame_index, reviewed_at".format(
            ",".join("?" * len(TARGET_VIDEO_STEMS))
        ),
        TARGET_VIDEO_STEMS,
    ).fetchall()
    return {(str(row["video_stem"]), int(row["frame_index"])): row for row in rows}


def slot_source(row: sqlite3.Row, slot: str) -> str:
    return str(row[f"{slot}_source"])


def slot_bbox(row: sqlite3.Row, slot: str) -> Tuple[float, float, float, float]:
    return (
        float(row[f"{slot}_bbox_x"]),
        float(row[f"{slot}_bbox_y"]),
        float(row[f"{slot}_bbox_w"]),
        float(row[f"{slot}_bbox_h"]),
    )


def slot_is_absent_from_annotation(row: sqlite3.Row, slot: str) -> bool:
    return slot_source(row, slot) == ABSENT_SOURCE


def slot_is_absent_from_review(row: sqlite3.Row, slot: str) -> bool:
    return str(row[f"{slot}_source"]) == ABSENT_SOURCE


def dice_for_slot_rows(row_a: sqlite3.Row, row_b: sqlite3.Row, slot: str) -> float:
    sa = slot_source(row_a, slot)
    sb = slot_source(row_b, slot)
    if sa == ABSENT_SOURCE and sb == ABSENT_SOURCE:
        return 1.0
    if (sa == ABSENT_SOURCE) != (sb == ABSENT_SOURCE):
        return 0.0
    ax, ay, aw, ah = slot_bbox(row_a, slot)
    bx, by, bw, bh = slot_bbox(row_b, slot)
    if aw <= 0 or ah <= 0 or bw <= 0 or bh <= 0:
        return 0.0
    ax2, ay2 = ax + aw, ay + ah
    bx2, by2 = bx + bw, by + bh
    ix1, iy1 = max(ax, bx), max(ay, by)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    denom = aw * ah + bw * bh
    return 0.0 if denom <= 0 else 2.0 * inter / denom


def pick_best_pair(rows: List[sqlite3.Row], slot: str) -> Tuple[sqlite3.Row, sqlite3.Row, float]:
    if len(rows) < 2:
        raise ValueError(f"need at least 2 annotations for {slot}")
    best: Tuple[float, sqlite3.Row, sqlite3.Row] | None = None
    for row_a, row_b in itertools.combinations(rows, 2):
        dice = dice_for_slot_rows(row_a, row_b, slot)
        candidate = (dice, row_a, row_b)
        if best is None:
            best = candidate
            continue
        best_key = (
            best[0],
            str(best[1]["submitted_at"]),
            str(best[1]["annotation_id"]),
            str(best[2]["submitted_at"]),
            str(best[2]["annotation_id"]),
        )
        cand_key = (
            candidate[0],
            str(candidate[1]["submitted_at"]),
            str(candidate[1]["annotation_id"]),
            str(candidate[2]["submitted_at"]),
            str(candidate[2]["annotation_id"]),
        )
        if cand_key > best_key:
            best = candidate
    assert best is not None
    return best[1], best[2], best[0]


def is_human(source: str) -> bool:
    return source in HUMAN_SOURCES


def is_ai(source: str) -> bool:
    return source in AI_SOURCES


def format_dice(dice: float) -> str:
    return f"{dice:.6f}"


def average_bbox(box_a: Tuple[float, float, float, float], box_b: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
    return tuple(_safe_float((a + b) / 2.0) for a, b in zip(box_a, box_b))


def build_slot_from_review(row: sqlite3.Row, slot: str) -> Dict[str, Any]:
    x = _safe_float(row[f"{slot}_bbox_x"])
    y = _safe_float(row[f"{slot}_bbox_y"])
    w = _safe_float(row[f"{slot}_bbox_w"])
    h = _safe_float(row[f"{slot}_bbox_h"])
    is_absent = row[f"{slot}_source"] == ABSENT_SOURCE
    return {
        "bbox": (x, y, w, h),
        "is_absent": is_absent,
        "final_source": "review",
        "ref_annotation_ids": f"{row['left_annotation_id']}|{row['right_annotation_id']}",
        "ref_annotators": str(row["reviewer_id"]),
        "ref_dice": format_dice(float(row["candidate_dice"])),
    }


def build_slot_from_pair(row_a: sqlite3.Row, row_b: sqlite3.Row, slot: str, dice: float) -> Dict[str, Any]:
    source_a = slot_source(row_a, slot)
    source_b = slot_source(row_b, slot)
    box_a = slot_bbox(row_a, slot)
    box_b = slot_bbox(row_b, slot)
    annotator_a = str(row_a["annotator_id"])
    annotator_b = str(row_b["annotator_id"])
    ann_ids = f"{row_a['annotation_id']}|{row_b['annotation_id']}"
    ann_names = f"{annotator_a}|{annotator_b}"
    if abs(dice - 1.0) <= 1e-9:
        is_absent = source_a == ABSENT_SOURCE and source_b == ABSENT_SOURCE
        bbox = (0.0, 0.0, 0.0, 0.0) if is_absent else average_bbox(box_a, box_b)
        return {
            "bbox": bbox,
            "is_absent": is_absent,
            "final_source": "dice=1",
            "ref_annotation_ids": ann_ids,
            "ref_annotators": ann_names,
            "ref_dice": format_dice(dice),
        }
    if (source_a == ABSENT_SOURCE) != (source_b == ABSENT_SOURCE):
        chosen_box = box_b if source_a == ABSENT_SOURCE else box_a
        return {
            "bbox": chosen_box,
            "is_absent": False,
            "final_source": "existance_conflict",
            "ref_annotation_ids": ann_ids,
            "ref_annotators": ann_names,
            "ref_dice": format_dice(dice),
        }
    if (is_human(source_a) and is_ai(source_b)) or (is_ai(source_a) and is_human(source_b)):
        if is_human(source_a):
            chosen_box = box_a
            human_annotator = annotator_a
        else:
            chosen_box = box_b
            human_annotator = annotator_b
        return {
            "bbox": chosen_box,
            "is_absent": False,
            "final_source": f"human_ai_conflict_{human_annotator}-AI",
            "ref_annotation_ids": ann_ids,
            "ref_annotators": ann_names,
            "ref_dice": format_dice(dice),
        }
    if is_human(source_a) and is_human(source_b):
        return {
            "bbox": average_bbox(box_a, box_b),
            "is_absent": False,
            "final_source": f"human_human_conflict_{annotator_a}-{annotator_b}-{format_dice(dice)}",
            "ref_annotation_ids": ann_ids,
            "ref_annotators": ann_names,
            "ref_dice": format_dice(dice),
        }
    if is_ai(source_a) and is_ai(source_b):
        return {
            "bbox": average_bbox(box_a, box_b),
            "is_absent": False,
            "final_source": f"AI_AI_conflict_{format_dice(dice)}",
            "ref_annotation_ids": ann_ids,
            "ref_annotators": ann_names,
            "ref_dice": format_dice(dice),
        }
    raise ValueError(f"unhandled source combination for {slot}: {source_a}, {source_b}")


def finalize_frame(
    frame_row: sqlite3.Row,
    annotations: List[sqlite3.Row],
    review_row: sqlite3.Row | None,
) -> Dict[str, Any]:
    row_out: Dict[str, Any] = {
        "video_stem": str(frame_row["video_stem"]),
        "frame_index": int(frame_row["frame_index"]),
        "timestamp_ms": f"{float(frame_row['timestamp_ms']):.3f}",
    }
    for slot in ("p1", "p2"):
        if review_row is not None:
            final = build_slot_from_review(review_row, slot)
        else:
            ref_a, ref_b, dice = pick_best_pair(annotations, slot)
            final = build_slot_from_pair(ref_a, ref_b, slot, dice)
        x, y, w, h = final["bbox"]
        row_out[f"{slot}_bbox_x"] = f"{_safe_float(x):.6f}"
        row_out[f"{slot}_bbox_y"] = f"{_safe_float(y):.6f}"
        row_out[f"{slot}_bbox_w"] = f"{_safe_float(w):.6f}"
        row_out[f"{slot}_bbox_h"] = f"{_safe_float(h):.6f}"
        row_out[f"{slot}_is_absent"] = "1" if final["is_absent"] else "0"
        row_out[f"{slot}_final_source"] = final["final_source"]
        row_out[f"{slot}_ref_annotation_ids"] = final["ref_annotation_ids"]
        row_out[f"{slot}_ref_annotators"] = final["ref_annotators"]
        row_out[f"{slot}_ref_dice"] = final["ref_dice"]
    return row_out


def write_video_csv(path: Path, rows: Iterable[Dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FINAL_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def main() -> None:
    args = parse_args()
    if args.batch_dir is not None:
        args.batch_dir = resolve_repo_path(args.batch_dir)
    args.root = resolve_repo_path(args.root)
    batch_dir = args.batch_dir if args.batch_dir is not None else find_latest_batch(args.root)
    if not batch_dir.exists():
        raise SystemExit(f"batch directory does not exist: {batch_dir}")

    logs_dir = batch_dir / "logs"
    logger = RunLogger(logs_dir / "run.log", logs_dir / "errors.log")
    logger.info("==============================================")
    logger.info("H-stage final annotation export started")
    logger.info(f"Batch dir: {batch_dir}")

    db_path = batch_dir / "ui_tasks" / "ui_review.sqlite3"
    if not db_path.exists():
        raise SystemExit(f"ui review db not found: {db_path}")

    conn = connect_db(db_path)
    try:
        ensure_schema(conn)
        frames = load_frames(conn)
        annotations_by_frame = load_annotations(conn)
        reviews_by_frame = load_reviews(conn)
    finally:
        conn.close()

    final_dir = batch_dir / "final_annotations"
    final_dir.mkdir(parents=True, exist_ok=True)
    by_video: Dict[str, List[Dict[str, Any]]] = {stem: [] for stem in TARGET_VIDEO_STEMS}
    source_counter: Dict[str, int] = {}

    for frame_row in frames:
        key = (str(frame_row["video_stem"]), int(frame_row["frame_index"]))
        annotations = annotations_by_frame.get(key, [])
        if len(annotations) < 2:
            logger.error(f"skip insufficient annotations video={key[0]} frame={key[1]} count={len(annotations)}")
            continue
        final_row = finalize_frame(frame_row, annotations, reviews_by_frame.get(key))
        by_video[key[0]].append(final_row)
        for slot in ("p1", "p2"):
            src = final_row[f"{slot}_final_source"]
            source_counter[src] = source_counter.get(src, 0) + 1

    exported: Dict[str, int] = {}
    for video_stem, rows in by_video.items():
        out_path = final_dir / f"{video_stem}.final.csv"
        exported[video_stem] = write_video_csv(out_path, rows)
        logger.info(f"H export {video_stem}: rows={exported[video_stem]} output={out_path}")

    summary = {
        "generated_at": _now(),
        "batch_dir": str(batch_dir),
        "videos": exported,
        "source_counts": dict(sorted(source_counter.items())),
    }
    summary_path = final_dir / "final_annotation_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info(f"H-stage finished summary={summary_path}")


if __name__ == "__main__":
    main()
