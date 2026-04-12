#!/usr/bin/env python3
from __future__ import annotations

import unittest

from prepare_capture_lib import (
    active_devices_for_window,
    build_frame_timestamps,
    build_device_intervals,
    build_union_intervals,
    choose_best_device_pair,
    intersect_interval_sets,
    merge_intervals,
    parse_capture_stem_start_ms,
    parse_time_of_day_to_epoch_ms,
    slice_intervals_to_sessions,
)


class ParseCaptureStemStartMsTests(unittest.TestCase):
    def test_parses_capture_stem_in_hong_kong_timezone(self) -> None:
        start_ms = parse_capture_stem_start_ms("20260410_195433", "Asia/Hong_Kong")
        self.assertEqual(start_ms, 1775822073000)


class ParseTimeOfDayToEpochMsTests(unittest.TestCase):
    def test_builds_epoch_from_capture_date_and_time_of_day(self) -> None:
        epoch_ms = parse_time_of_day_to_epoch_ms("2026-04-10", "20:06:24.900", "Asia/Hong_Kong")
        self.assertEqual(epoch_ms, 1775822784900)


class BuildFrameTimestampsTests(unittest.TestCase):
    def test_builds_constant_fps_timestamps(self) -> None:
        ts = build_frame_timestamps(start_ms=1000, frame_count=3, fps=2.0)
        self.assertEqual(ts, [1000.0, 1500.0, 2000.0])


class MergeIntervalsTests(unittest.TestCase):
    def test_merges_small_gaps(self) -> None:
        merged = merge_intervals(
            [(1000, 2000), (2200, 2600), (5000, 5500)],
            gap_tolerance_ms=250,
        )
        self.assertEqual(merged, [(1000, 2600), (5000, 5500)])


class BuildDeviceIntervalsTests(unittest.TestCase):
    def test_splits_epoch_stream_on_large_gaps(self) -> None:
        intervals = build_device_intervals(
            [1000, 1010, 1020, 5000, 5010, 9000],
            gap_threshold_ms=100,
        )
        self.assertEqual(intervals, [(1000, 1020), (5000, 5010), (9000, 9000)])


class IntersectIntervalSetsTests(unittest.TestCase):
    def test_intersects_two_interval_lists(self) -> None:
        intersection = intersect_interval_sets(
            [(1000, 5000), (7000, 9000)],
            [(2000, 8000)],
        )
        self.assertEqual(intersection, [(2000, 5000), (7000, 8000)])


class BuildUnionIntervalsTests(unittest.TestCase):
    def test_builds_union_from_all_devices(self) -> None:
        intervals = build_union_intervals(
            {
                "imu_a": [(1000, 4000)],
                "imu_b": [(3000, 7000)],
                "imu_c": [(9000, 11000)],
            },
            window_start_ms=0,
            window_end_ms=12000,
            merge_gap_ms=0,
        )
        self.assertEqual(intervals, [(1000, 7000), (9000, 11000)])


class ActiveDevicesForWindowTests(unittest.TestCase):
    def test_collects_all_overlapping_devices_for_window(self) -> None:
        devices = active_devices_for_window(
            {
                "imu_a": [(1000, 4000)],
                "imu_b": [(3000, 7000)],
                "imu_c": [(9000, 11000)],
            },
            start_ms=3500,
            end_ms=5000,
        )
        self.assertEqual(devices, ["imu_a", "imu_b"])


class ChooseBestDevicePairTests(unittest.TestCase):
    def test_prefers_pair_with_largest_overlap_inside_video_window(self) -> None:
        device_intervals = {
            "imu_a": [(1000, 8000)],
            "imu_b": [(1500, 8500)],
            "imu_c": [(4000, 5000)],
        }
        best = choose_best_device_pair(device_intervals, video_start_ms=0, video_end_ms=9000)
        self.assertEqual(best.device_a, "imu_a")
        self.assertEqual(best.device_b, "imu_b")
        self.assertEqual(best.overlap_ms, 6500)


class SliceIntervalsToSessionsTests(unittest.TestCase):
    def test_slices_intervals_into_named_sessions(self) -> None:
        sessions = slice_intervals_to_sessions(
            intervals=[(1775822400000, 1775822525000)],
            session_length_ms=60_000,
            min_session_ms=45_000,
            timezone_name="Asia/Hong_Kong",
        )
        self.assertEqual(
            [session.stem for session in sessions],
            ["20260410_200000", "20260410_200100"],
        )
        self.assertEqual(sessions[0].start_ms, 1775822400000)
        self.assertEqual(sessions[0].end_ms, 1775822460000)
        self.assertEqual(sessions[1].start_ms, 1775822460000)
        self.assertEqual(sessions[1].end_ms, 1775822520000)


if __name__ == "__main__":
    unittest.main()
