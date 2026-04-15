#!/usr/bin/env python3
from __future__ import annotations

import unittest

import review_propagation as mod


class ReviewPropagationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ai_boxes = {
            ("sample", 1): [
                {
                    "track_id": 11,
                    "bbox_x": 10,
                    "bbox_y": 20,
                    "bbox_w": 30,
                    "bbox_h": 40,
                    "score": 0.95,
                }
            ],
            ("sample", 2): [
                {
                    "track_id": 11,
                    "bbox_x": 30,
                    "bbox_y": 20,
                    "bbox_w": 32,
                    "bbox_h": 40,
                    "score": 0.94,
                }
            ],
            ("sample", 3): [
                {
                    "track_id": 11,
                    "bbox_x": 35,
                    "bbox_y": 20,
                    "bbox_w": 34,
                    "bbox_h": 40,
                    "score": 0.93,
                },
                {
                    "track_id": 21,
                    "bbox_x": 80,
                    "bbox_y": 18,
                    "bbox_w": 33,
                    "bbox_h": 41,
                    "score": 0.92,
                },
            ],
            ("sample", 4): [
                {
                    "track_id": 21,
                    "bbox_x": 96,
                    "bbox_y": 18,
                    "bbox_w": 34,
                    "bbox_h": 42,
                    "score": 0.91,
                }
            ],
        }

    def test_propagate_keyframes_follows_ai_motion_with_interpolated_corrections(self) -> None:
        propagated = mod.propagate_issue_keyframes(
            video_stem="sample",
            start_frame=1,
            end_frame=3,
            slot_names=["p1"],
            ai_boxes=self.ai_boxes,
            keyframes=[
                {
                    "frame_index": 1,
                    "slots": [
                        {
                            "slot": "p1",
                            "bbox_x": 20,
                            "bbox_y": 25,
                            "bbox_w": 35,
                            "bbox_h": 45,
                            "source": "manual_param",
                            "ai_track_id": "11",
                        }
                    ],
                },
                {
                    "frame_index": 3,
                    "slots": [
                        {
                            "slot": "p1",
                            "bbox_x": 38,
                            "bbox_y": 24,
                            "bbox_w": 37,
                            "bbox_h": 45,
                            "source": "manual_param",
                            "ai_track_id": "11",
                        }
                    ],
                },
            ],
        )
        self.assertEqual(propagated[1][0]["bbox_x"], 20.0)
        self.assertAlmostEqual(propagated[2][0]["bbox_x"], 36.5, places=3)
        self.assertEqual(propagated[3][0]["bbox_x"], 38.0)
        self.assertEqual(propagated[2][0]["source"], "manual_param")
        self.assertEqual(propagated[2][0]["ai_track_id"], "11")

    def test_propagate_reappear_keeps_state_until_visible_keyframe(self) -> None:
        propagated = mod.propagate_issue_keyframes(
            video_stem="sample",
            start_frame=1,
            end_frame=3,
            slot_names=["p1"],
            ai_boxes=self.ai_boxes,
            keyframes=[
                {
                    "frame_index": 1,
                    "slots": [
                        {
                            "slot": "p1",
                            "bbox_x": 0,
                            "bbox_y": 0,
                            "bbox_w": 0,
                            "bbox_h": 0,
                            "source": "occluded",
                            "ai_track_id": "",
                        }
                    ],
                },
                {
                    "frame_index": 3,
                    "slots": [
                        {
                            "slot": "p1",
                            "bbox_x": 80,
                            "bbox_y": 18,
                            "bbox_w": 33,
                            "bbox_h": 41,
                            "source": "ai",
                            "ai_track_id": "21",
                        }
                    ],
                },
            ],
        )
        self.assertEqual(propagated[1][0]["source"], "occluded")
        self.assertEqual(propagated[2][0]["source"], "occluded")
        self.assertEqual(propagated[3][0]["source"], "ai")
        self.assertEqual(propagated[3][0]["ai_track_id"], "21")

    def test_propagate_can_switch_ai_tracks_between_keyframes(self) -> None:
        propagated = mod.propagate_issue_keyframes(
            video_stem="sample",
            start_frame=1,
            end_frame=4,
            slot_names=["p1"],
            ai_boxes=self.ai_boxes,
            keyframes=[
                {
                    "frame_index": 1,
                    "slots": [
                        {
                            "slot": "p1",
                            "bbox_x": 10,
                            "bbox_y": 20,
                            "bbox_w": 30,
                            "bbox_h": 40,
                            "source": "ai",
                            "ai_track_id": "11",
                        }
                    ],
                },
                {
                    "frame_index": 4,
                    "slots": [
                        {
                            "slot": "p1",
                            "bbox_x": 96,
                            "bbox_y": 18,
                            "bbox_w": 34,
                            "bbox_h": 42,
                            "source": "ai",
                            "ai_track_id": "21",
                        }
                    ],
                },
            ],
        )
        self.assertEqual(propagated[2][0]["ai_track_id"], "11")
        self.assertEqual(propagated[2][0]["bbox_x"], 30.0)
        self.assertEqual(propagated[3][0]["ai_track_id"], "21")
        self.assertEqual(propagated[3][0]["bbox_x"], 80.0)
        self.assertEqual(propagated[4][0]["ai_track_id"], "21")


if __name__ == "__main__":
    unittest.main()
