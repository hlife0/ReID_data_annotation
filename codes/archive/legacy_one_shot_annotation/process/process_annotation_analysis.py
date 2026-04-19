#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CSV_COLUMNS = [
    "video_stem",
    "frame_index",
    "timestamp_ms",
    "annotation_count",
    "p1_dice",
    "p2_dice",
    "p1_pair_count",
    "p2_pair_count",
]
VALID_SOURCES = {"ai", "manual_draw", "manual_param", "absent"}


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
    parser = argparse.ArgumentParser(
        description="Analyze multi-annotation agreement and render per-person Dice line charts"
    )
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
    parser.add_argument(
        "--top-frames",
        type=int,
        default=20,
        help="Number of top frames kept in each summary JSON",
    )
    parser.add_argument(
        "--both-absent-value",
        type=float,
        default=1.0,
        help="Dice analysis value when both annotations mark absent",
    )
    parser.add_argument(
        "--absent-mismatch-value",
        type=float,
        default=0.0,
        help="Finite value when one annotation is absent and the other is not",
    )
    parser.add_argument(
        "--plot-ymax",
        type=float,
        default=1.05,
        help="Y-axis max used for the Dice plots",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=140,
        help="Output DPI for PNG plots",
    )
    parser.add_argument(
        "--hist-bins",
        type=int,
        default=40,
        help="Number of bins used for the combined Dice histogram",
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
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('frames', 'annotations')"
        ).fetchall()
    }
    missing = sorted({"frames", "annotations"} - names)
    if missing:
        raise RuntimeError(f"required tables missing: {missing}")


def load_video_stems(conn: sqlite3.Connection) -> List[str]:
    rows = conn.execute(
        "SELECT DISTINCT video_stem FROM frames ORDER BY video_stem ASC"
    ).fetchall()
    return [str(row["video_stem"]) for row in rows]


def load_frames_for_video(conn: sqlite3.Connection, video_stem: str) -> List[sqlite3.Row]:
    return conn.execute(
        """
        SELECT video_stem, frame_index, timestamp_ms
        FROM frames
        WHERE video_stem=?
        ORDER BY frame_index ASC
        """,
        (video_stem,),
    ).fetchall()


def load_annotations_for_video(conn: sqlite3.Connection, video_stem: str) -> Dict[int, List[sqlite3.Row]]:
    rows = conn.execute(
        """
        SELECT *
        FROM annotations
        WHERE video_stem=?
        ORDER BY frame_index ASC, submitted_at ASC, annotation_id ASC
        """,
        (video_stem,),
    ).fetchall()
    grouped: Dict[int, List[sqlite3.Row]] = {}
    for row in rows:
        grouped.setdefault(int(row["frame_index"]), []).append(row)
    return grouped


def bbox_from_row(row: sqlite3.Row, slot: str) -> Tuple[float, float, float, float]:
    x = float(row[f"{slot}_bbox_x"])
    y = float(row[f"{slot}_bbox_y"])
    w = float(row[f"{slot}_bbox_w"])
    h = float(row[f"{slot}_bbox_h"])
    if w <= 0.0 or h <= 0.0:
        annotation_id = str(row["annotation_id"])
        raise ValueError(f"invalid {slot} bbox in annotation {annotation_id}: w={w}, h={h}")
    return x, y, w, h


def dice_xywh(box_a: Tuple[float, float, float, float], box_b: Tuple[float, float, float, float]) -> float:
    ax, ay, aw, ah = box_a
    bx, by, bw, bh = box_b
    ax2 = ax + aw
    ay2 = ay + ah
    bx2 = bx + bw
    by2 = by + bh

    inter_x1 = max(ax, bx)
    inter_y1 = max(ay, by)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    denom = (aw * ah) + (bw * bh)
    if denom <= 0.0:
        return 0.0
    return (2.0 * inter_area) / denom


def pairwise_dice_value(
    row_a: sqlite3.Row,
    row_b: sqlite3.Row,
    slot: str,
    both_absent_value: float,
    absent_mismatch_value: float,
) -> float:
    source_a = str(row_a[f"{slot}_source"])
    source_b = str(row_b[f"{slot}_source"])
    if source_a not in VALID_SOURCES:
        raise ValueError(f"invalid {slot} source in {row_a['annotation_id']}: {source_a}")
    if source_b not in VALID_SOURCES:
        raise ValueError(f"invalid {slot} source in {row_b['annotation_id']}: {source_b}")

    absent_a = source_a == "absent"
    absent_b = source_b == "absent"
    if absent_a and absent_b:
        return float(both_absent_value)
    if absent_a != absent_b:
        return float(absent_mismatch_value)

    box_a = bbox_from_row(row_a, slot)
    box_b = bbox_from_row(row_b, slot)
    return dice_xywh(box_a, box_b)


def compute_slot_frame_value(
    rows: List[sqlite3.Row],
    slot: str,
    both_absent_value: float,
    absent_mismatch_value: float,
) -> Tuple[float, int]:
    if len(rows) < 2:
        raise ValueError("need at least 2 annotations to compute Dice")
    values: List[float] = []
    for row_a, row_b in itertools.combinations(rows, 2):
        values.append(
            pairwise_dice_value(
                row_a=row_a,
                row_b=row_b,
                slot=slot,
                both_absent_value=both_absent_value,
                absent_mismatch_value=absent_mismatch_value,
            )
        )
    return min(values), len(values)


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def plot_slot(
    video_stem: str,
    slot: str,
    series: List[Tuple[int, float]],
    out_path: Path,
    plot_ymax: float,
    absent_mismatch_value: float,
    dpi: int,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 4), dpi=dpi)
    if series:
        xs = [item[0] for item in series]
        ys = [item[1] for item in series]
        color = "#1d9a58" if slot == "p1" else "#54606e"
        ax.plot(xs, ys, color=color, linewidth=1.4)
    else:
        ax.text(
            0.5,
            0.5,
            "No frames with >=2 annotations",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
    ax.axhline(1.0, color="#9b6b00", linestyle="--", linewidth=1.0, label="dice=1.0")
    ax.axhline(
        absent_mismatch_value,
        color="#9f1d23",
        linestyle=":",
        linewidth=1.0,
        label=f"absent mismatch={absent_mismatch_value:.1f}",
    )
    ax.set_ylim(0.0, plot_ymax)
    ax.set_xlabel("frame_index")
    ax.set_ylabel("dice_value")
    ax.set_title(f"{video_stem} {slot.upper()} Dice Analysis")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_overall_histogram(
    values: List[float],
    out_path: Path,
    hist_bins: int,
    dpi: int,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4.8), dpi=dpi)
    if values:
        ax.hist(
            values,
            bins=hist_bins,
            range=(0.0, 1.0),
            color="#2f5c8f",
            edgecolor="#ffffff",
            linewidth=0.6,
        )
    else:
        ax.text(
            0.5,
            0.5,
            "No Dice values available",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
    ax.axvline(0.0, color="#9f1d23", linestyle=":", linewidth=1.0, label="dice=0.0")
    ax.axvline(1.0, color="#9b6b00", linestyle="--", linewidth=1.0, label="dice=1.0")
    ax.set_xlim(0.0, 1.0)
    ax.set_xlabel("dice_value")
    ax.set_ylabel("frequency")
    ax.set_title("All Videos Combined Dice Histogram (P1 + P2)")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(loc="upper center")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_rework_threshold_curve(
    frame_values: List[Tuple[float, float]],
    out_path: Path,
    dpi: int,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4.8), dpi=dpi)

    scores = sorted(min(p1, p2) for p1, p2 in frame_values)
    if not scores:
        ax.text(
            0.5,
            0.5,
            "No frame Dice values available",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
    else:
        thresholds = [0.0]
        counts = [0]
        idx = 0
        total = len(scores)
        while idx < total:
            value = scores[idx]
            end = idx
            while end < total and scores[end] == value:
                end += 1
            thresholds.append(value)
            counts.append(idx)
            if value < 1.0:
                thresholds.append(math.nextafter(value, 1.0))
                counts.append(end)
            idx = end
        if thresholds[-1] < 1.0:
            thresholds.append(1.0)
            counts.append(idx)
        ax.step(thresholds, counts, where="post", color="#7a2f8f", linewidth=1.8)

    ymax = max(counts) if scores else 0
    ax.set_ylim(0.0, max(10.0, ymax + 20.0))
    ax.set_xlim(0.0, 1.0)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=8, integer=True))
    ax.set_xlabel("threshold")
    ax.set_ylabel("rework_frame_count")
    ax.set_title("All Videos Combined Rework Count vs Threshold (Exact Dice Breakpoints)")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def top_frames(series_rows: List[Dict[str, Any]], slot: str, limit: int) -> List[Dict[str, Any]]:
    dice_key = f"{slot}_dice"
    sorted_rows = sorted(
        series_rows,
        key=lambda row: (float(row[dice_key]), int(row["frame_index"])),
    )
    return [
        {
            "frame_index": int(row["frame_index"]),
            "timestamp_ms": float(row["timestamp_ms"]),
            "annotation_count": int(row["annotation_count"]),
            "dice": float(row[dice_key]),
        }
        for row in sorted_rows[:limit]
    ]


def process_video(
    conn: sqlite3.Connection,
    batch_dir: Path,
    video_stem: str,
    args: argparse.Namespace,
    logger: RunLogger,
) -> Tuple[Dict[str, Any], List[float]]:
    frames = load_frames_for_video(conn, video_stem)
    annotations_by_frame = load_annotations_for_video(conn, video_stem)
    analysis_dir = batch_dir / "annotation_analysis"
    out_csv = analysis_dir / f"{video_stem}.dice_timeseries.csv"
    out_p1 = analysis_dir / f"{video_stem}.p1.dice.png"
    out_p2 = analysis_dir / f"{video_stem}.p2.dice.png"
    out_summary = analysis_dir / f"{video_stem}.dice_summary.json"

    output_rows: List[Dict[str, Any]] = []
    p1_series: List[Tuple[int, float]] = []
    p2_series: List[Tuple[int, float]] = []
    combined_values: List[float] = []
    frame_values: List[Tuple[float, float]] = []
    skipped_lt2 = 0
    failed_invalid = 0

    for frame_row in frames:
        frame_index = int(frame_row["frame_index"])
        timestamp_ms = float(frame_row["timestamp_ms"])
        frame_annotations = annotations_by_frame.get(frame_index, [])
        annotation_count = len(frame_annotations)
        if annotation_count < 2:
            skipped_lt2 += 1
            continue
        try:
            p1_dice, p1_pair_count = compute_slot_frame_value(
                rows=frame_annotations,
                slot="p1",
                both_absent_value=args.both_absent_value,
                absent_mismatch_value=args.absent_mismatch_value,
            )
            p2_dice, p2_pair_count = compute_slot_frame_value(
                rows=frame_annotations,
                slot="p2",
                both_absent_value=args.both_absent_value,
                absent_mismatch_value=args.absent_mismatch_value,
            )
        except Exception as exc:
            failed_invalid += 1
            logger.error(
                f"F2 invalid frame video={video_stem} frame_index={frame_index}: {exc}"
            )
            continue

        row = {
            "video_stem": video_stem,
            "frame_index": frame_index,
            "timestamp_ms": f"{timestamp_ms:.3f}",
            "annotation_count": annotation_count,
            "p1_dice": f"{_safe_float(p1_dice):.6f}",
            "p2_dice": f"{_safe_float(p2_dice):.6f}",
            "p1_pair_count": p1_pair_count,
            "p2_pair_count": p2_pair_count,
        }
        output_rows.append(row)
        p1_value = float(row["p1_dice"])
        p2_value = float(row["p2_dice"])
        p1_series.append((frame_index, p1_value))
        p2_series.append((frame_index, p2_value))
        combined_values.extend([p1_value, p2_value])
        frame_values.append((p1_value, p2_value))

    write_csv(out_csv, output_rows)
    plot_slot(
        video_stem=video_stem,
        slot="p1",
        series=p1_series,
        out_path=out_p1,
        plot_ymax=args.plot_ymax,
        absent_mismatch_value=args.absent_mismatch_value,
        dpi=args.dpi,
    )
    plot_slot(
        video_stem=video_stem,
        slot="p2",
        series=p2_series,
        out_path=out_p2,
        plot_ymax=args.plot_ymax,
        absent_mismatch_value=args.absent_mismatch_value,
        dpi=args.dpi,
    )

    summary = {
        "video_stem": video_stem,
        "status": "done",
        "generated_at": _now(),
        "input_db": str(batch_dir / "ui_tasks" / "ui_review.sqlite3"),
        "outputs": {
            "csv": str(out_csv),
            "p1_plot": str(out_p1),
            "p2_plot": str(out_p2),
        },
        "dice_rules": {
            "both_absent_value": args.both_absent_value,
            "absent_mismatch_value": args.absent_mismatch_value,
            "three_or_more_rule": "min(pairwise_values)",
            "regular_bbox_formula": "2 * intersection_area / (area_a + area_b)",
        },
        "stats": {
            "frame_total": len(frames),
            "frame_output": len(output_rows),
            "frame_skipped_lt2_annotations": skipped_lt2,
            "frame_failed_invalid_data": failed_invalid,
            "p1_min_dice": min((value for _, value in p1_series), default=None),
            "p1_max_dice": max((value for _, value in p1_series), default=None),
            "p2_min_dice": min((value for _, value in p2_series), default=None),
            "p2_max_dice": max((value for _, value in p2_series), default=None),
        },
        "top_frames": {
            "p1_top_frames": top_frames(output_rows, "p1", args.top_frames),
            "p2_top_frames": top_frames(output_rows, "p2", args.top_frames),
        },
    }
    out_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info(
        f"F5 done video={video_stem} rows={len(output_rows)} skipped_lt2={skipped_lt2} failed_invalid={failed_invalid}"
    )
    return summary, combined_values, frame_values


def main() -> None:
    args = parse_args()
    if args.top_frames < 1:
        raise SystemExit("--top-frames must be >= 1")
    if args.hist_bins < 1:
        raise SystemExit("--hist-bins must be >= 1")
    if args.plot_ymax <= 0:
        raise SystemExit("--plot-ymax must be > 0")
    if args.both_absent_value < args.absent_mismatch_value:
        raise SystemExit("--both-absent-value must be >= --absent-mismatch-value")
    if args.plot_ymax <= max(args.both_absent_value, args.absent_mismatch_value, 1.0):
        raise SystemExit("--plot-ymax must be greater than all plotted reference values")

    if args.batch_dir is not None:
        args.batch_dir = resolve_repo_path(args.batch_dir)
    args.root = resolve_repo_path(args.root)
    batch_dir = args.batch_dir if args.batch_dir is not None else find_latest_batch(args.root)
    if not batch_dir.exists():
        raise SystemExit(f"batch directory does not exist: {batch_dir}")

    db_path = batch_dir / "ui_tasks" / "ui_review.sqlite3"
    if not db_path.exists():
        raise SystemExit(f"ui review database not found: {db_path}")

    logs_dir = batch_dir / "logs"
    logger = RunLogger(
        run_log_path=logs_dir / "run.log",
        error_log_path=logs_dir / "errors.log",
    )
    logger.info("==============================================")
    logger.info("F-stage annotation analysis run started")
    logger.info(f"Batch dir: {batch_dir}")
    logger.info(
        f"Config top_frames={args.top_frames}, both_absent_value={args.both_absent_value}, "
        f"absent_mismatch_value={args.absent_mismatch_value}, plot_ymax={args.plot_ymax}, dpi={args.dpi}, hist_bins={args.hist_bins}"
    )

    conn = connect_db(db_path)
    try:
        ensure_schema(conn)
        video_stems = load_video_stems(conn)
        if not video_stems:
            raise SystemExit("no videos found in frames table")
        logger.info(f"Video stems count={len(video_stems)}")

        summaries = []
        all_dice_values: List[float] = []
        all_frame_values: List[Tuple[float, float]] = []
        for video_stem in video_stems:
            summary, dice_values, frame_values = process_video(conn, batch_dir, video_stem, args, logger)
            summaries.append(summary)
            all_dice_values.extend(dice_values)
            all_frame_values.extend(frame_values)
    finally:
        conn.close()

    hist_path = batch_dir / "annotation_analysis" / "all_videos.dice_hist.png"
    plot_overall_histogram(all_dice_values, hist_path, args.hist_bins, args.dpi)
    logger.info(f"F5 combined histogram written: {hist_path}")
    threshold_path = batch_dir / "annotation_analysis" / "all_videos.rework_threshold.png"
    plot_rework_threshold_curve(all_frame_values, threshold_path, args.dpi)
    logger.info(f"F5 rework-threshold curve written: {threshold_path}")
    logger.info(
        "F-stage finished: "
        + ", ".join(f"{item['video_stem']}={item['stats']['frame_output']} rows" for item in summaries)
    )


if __name__ == "__main__":
    main()
