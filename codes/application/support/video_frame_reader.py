#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

import cv2


class VideoFrameReader:
    def __init__(self, video_paths: Dict[str, Path], jpeg_quality: int = 88) -> None:
        self._video_paths = video_paths
        self._captures: Dict[str, cv2.VideoCapture] = {}
        self._locks: Dict[str, object] = {}
        self._meta: Dict[str, Tuple[int, int]] = {}
        self._jpeg_quality = int(max(10, min(100, jpeg_quality)))

        import threading

        self._threading = threading

    def get_dimensions(self, video_stem: str) -> Tuple[int, int]:
        self._ensure_open(video_stem)
        return self._meta[video_stem]

    def read_jpeg(self, video_stem: str, frame_index_1based: int) -> bytes:
        self._ensure_open(video_stem)
        cap = self._captures[video_stem]
        lock = self._locks[video_stem]
        with lock:
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_index_1based - 1))
            ok, frame = cap.read()
            if not ok or frame is None:
                raise ValueError(f"failed to decode frame {frame_index_1based} from {video_stem}")
            ok_encode, buf = cv2.imencode(
                ".jpg",
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality],
            )
            if not ok_encode:
                raise ValueError(f"failed to encode frame {frame_index_1based} from {video_stem}")
            return bytes(buf)

    def _ensure_open(self, video_stem: str) -> None:
        if video_stem in self._captures:
            return
        path = self._video_paths[video_stem]
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise ValueError(f"failed to open video: {path}")
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._captures[video_stem] = cap
        self._locks[video_stem] = self._threading.Lock()
        self._meta[video_stem] = (width, height)

    def close(self) -> None:
        for cap in self._captures.values():
            cap.release()
        self._captures.clear()
        self._locks.clear()
        self._meta.clear()
