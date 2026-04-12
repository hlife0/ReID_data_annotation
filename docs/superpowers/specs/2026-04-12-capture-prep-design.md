# Capture Prep Design

**Goal:** Bring a new raw capture into this repository as batch-ready `required` inputs without writing outside this repository.

**Scope:** Copy the essential preprocessing logic from `/data/hrli/copy_from_fzliang`, adapt it for the latest `20260410_195433` MP4 plus raw multi-device IMU dump, and emit local staging outputs that can later be consumed by the annotation pipeline via `--required-root`.

**Key Decisions**

- Write only inside this repository.
- Keep generated data under `./staging/`.
- Do not write through the `./data` symlink.
- Reuse the upstream preprocessing ideas, but not the exact assumptions.
- Do not depend on `.bag` files or RealSense per-frame timestamp exports for this capture.

**Output Layout**

```text
./staging/
├── imu_normalized/
│   └── 2026-04-10/
│       ├── by_device/
│       └── reports/
├── required/
│   └── <session_stem>/
│       ├── video/
│       │   ├── <session_stem>.mp4
│       │   ├── <session_stem>_frame_timestamps.csv
│       │   ├── <session_stem>_retimed.mp4
│       │   └── <session_stem>_frame_timestamps_retimed.csv
│       └── imu/
│           ├── <session_stem>_<device_a>.csv
│           └── <session_stem>_<device_b>.csv
└── reports/
    └── capture_prep_summary.json
```

**Pipeline**

1. Read the raw IMU dump recursively and split rows by `设备名称`.
2. Build `epoch_ms` from the capture date plus the `时间` column.
3. Build per-device activity intervals from the normalized rows.
4. Parse the MP4 stem as the video start timestamp and generate approximate frame timestamps from FPS.
5. Pick the best dual-IMU pair by overlap with the video window.
6. Turn overlap intervals into annotation-sized sessions.
7. Export local `required` directories with clipped MP4s, timestamp CSVs, and two IMU CSVs.

**Assumptions**

- The latest capture date is `2026-04-10`.
- The MP4 stem encodes the wall-clock start time.
- The MP4 FPS is constant and usable for approximate timestamps.
- `片上时间()` is not trusted for this capture because sample rows show inconsistent dates.

**Non-Goals**

- Running AI prelabeling.
- Writing to external data roots.
- Producing final annotation batches.
