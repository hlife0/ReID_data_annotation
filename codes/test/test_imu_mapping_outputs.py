#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

REQUIRED_COLUMNS = [
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate C-stage imu_mapping outputs"
    )
    parser.add_argument(
        "--batch-dir",
        type=Path,
        default=None,
        help="Batch directory. Default: latest batch_*_vNN under --root.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT / "annotation",
        help="Root directory containing annotation/batch_*_vNN",
    )
    return parser.parse_args()


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def find_latest_batch(root: Path) -> Path:
    pattern = re.compile(r"^batch_(\d{8})_v(\d{2})$")
    candidates = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        m = pattern.match(child.name)
        if m:
            date = int(m.group(1))
            version = int(m.group(2))
            candidates.append((date, version, child))
    if not candidates:
        raise FileNotFoundError(f"no batch_*_vNN found under {root}")
    candidates.sort(key=lambda x: (x[0], x[1]))
    return candidates[-1][2]


def validate_csv(csv_path: Path) -> List[str]:
    errors: List[str] = []
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        if fields != REQUIRED_COLUMNS:
            errors.append(
                f"{csv_path.name}: header mismatch expected={REQUIRED_COLUMNS} got={fields}"
            )
            return errors

        prev_m = None
        prev_ts = None
        for row_idx, row in enumerate(reader, start=1):
            try:
                rank = int(row["rank_m_desc"])
                ts = float(row["timestamp_ms"])
                k_t = float(row["k_t"])
                m_t = float(row["m_t"])
                static_a = float(row["static_coef_a"])
                static_b = float(row["static_coef_b"])
                coef_a = float(row["coef_a"])
                coef_b = float(row["coef_b"])
            except Exception as exc:
                errors.append(f"{csv_path.name}: parse error row={row_idx}: {exc}")
                continue

            if rank != row_idx:
                errors.append(f"{csv_path.name}: rank mismatch row={row_idx}, rank={rank}")
            if k_t <= 0.0 or m_t < 1.0:
                errors.append(f"{csv_path.name}: invalid k_t/m_t row={row_idx}")
            if coef_a <= 0.0 or coef_b <= 0.0:
                errors.append(f"{csv_path.name}: coef_a/coef_b must be >0 row={row_idx}")
            if static_a <= 0.0 or static_b <= 0.0:
                errors.append(f"{csv_path.name}: static coef must be >0 row={row_idx}")
            expected_m = max(k_t, 1.0 / k_t)
            if abs(expected_m - m_t) > 1e-6:
                errors.append(f"{csv_path.name}: m_t formula mismatch row={row_idx}")

            if prev_m is not None:
                if m_t > prev_m + 1e-12:
                    errors.append(f"{csv_path.name}: m_t not descending row={row_idx}")
                if abs(m_t - prev_m) <= 1e-12 and prev_ts is not None and ts < prev_ts:
                    errors.append(
                        f"{csv_path.name}: tie m_t but timestamp not ascending row={row_idx}"
                    )
            prev_m = m_t
            prev_ts = ts
    return errors


def validate_summary(summary_path: Path) -> List[str]:
    errors: List[str] = []
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"{summary_path.name}: invalid json: {exc}"]

    if "video_stem" not in data:
        errors.append(f"{summary_path.name}: missing video_stem")
    status = data.get("status")
    if status not in {"done", "blocked"}:
        errors.append(f"{summary_path.name}: status must be done/blocked")
    if status == "done":
        for key in ["algorithm", "stats", "recommended_replay_points"]:
            if key not in data:
                errors.append(f"{summary_path.name}: missing {key}")
    return errors


def main() -> None:
    args = parse_args()
    if args.batch_dir is not None:
        args.batch_dir = resolve_repo_path(args.batch_dir)
    args.root = resolve_repo_path(args.root)
    batch_dir = args.batch_dir if args.batch_dir is not None else find_latest_batch(args.root)
    imu_mapping_dir = batch_dir / "imu_mapping"
    if not imu_mapping_dir.exists():
        raise SystemExit(f"imu_mapping directory not found: {imu_mapping_dir}")

    csv_files = sorted(imu_mapping_dir.glob("*.imu_ratio_rank.csv"))
    summary_files = sorted(imu_mapping_dir.glob("*.imu_mapping_summary.json"))
    if not csv_files and not summary_files:
        raise SystemExit(f"no imu mapping outputs found in {imu_mapping_dir}")

    all_errors: List[str] = []
    for path in csv_files:
        all_errors.extend(validate_csv(path))
    for path in summary_files:
        all_errors.extend(validate_summary(path))

    if all_errors:
        print(f"Validation FAIL: {len(all_errors)} problem(s)")
        for err in all_errors:
            print(f"- {err}")
        raise SystemExit(1)

    print(
        f"Validation PASS: batch={batch_dir}, "
        f"csv_files={len(csv_files)}, summary_files={len(summary_files)}"
    )


if __name__ == "__main__":
    main()
