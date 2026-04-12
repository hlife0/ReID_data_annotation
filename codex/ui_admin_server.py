#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import threading
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent

def _now_human() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def slot_summary_from_json(slots_json: str) -> str:
    try:
        slots = json.loads(slots_json)
    except Exception:
        return ""
    if not isinstance(slots, list):
        return ""
    parts: List[str] = []
    for item in slots:
        if not isinstance(item, dict):
            continue
        slot = str(item.get("slot", "")).strip()
        source = str(item.get("source", "")).strip()
        track = str(item.get("ai_track_id", "") or "").strip()
        if not slot:
            continue
        piece = f"{slot.upper()}:{source}"
        if track:
            piece += f"({track})"
        parts.append(piece)
    return " | ".join(parts)


class RunLogger:
    def __init__(self, run_log_path: Path, error_log_path: Path) -> None:
        self.run_log_path = run_log_path
        self.error_log_path = error_log_path
        self._lock = threading.Lock()
        self.run_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.error_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.run_log_path.touch(exist_ok=True)
        self.error_log_path.touch(exist_ok=True)

    def info(self, message: str) -> None:
        self._write("INFO", message)

    def error(self, message: str) -> None:
        self._write("ERROR", message, also_error=True)

    def _write(self, level: str, message: str, also_error: bool = False) -> None:
        line = f"[{_now_human()}] {level:<5} {message}\n"
        with self._lock:
            with self.run_log_path.open("a", encoding="utf-8") as f:
                f.write(line)
            if also_error:
                with self.error_log_path.open("a", encoding="utf-8") as f:
                    f.write(line)
        print(line, end="")


class AdminState:
    def __init__(self, batch_dir: Path, static_dir: Path) -> None:
        self.batch_dir = batch_dir
        self.static_dir = static_dir
        self.db_path = self.batch_dir / "ui_tasks" / "ui_review.sqlite3"
        self.logs_dir = self.batch_dir / "logs"
        self.video_stems: List[str] = []
        self.logger = RunLogger(
            run_log_path=self.logs_dir / "run.log",
            error_log_path=self.logs_dir / "errors.log",
        )

    def initialize(self) -> None:
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"database not found: {self.db_path}. "
                "Run ui_review_server.py --reset-storage --init-only first."
            )
        if not self.static_dir.exists():
            raise FileNotFoundError(f"admin static dir not found: {self.static_dir}")
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT DISTINCT video_stem FROM frames ORDER BY video_stem ASC"
            ).fetchall()
        finally:
            conn.close()
        self.video_stems = [str(row["video_stem"]) for row in rows]
        self.logger.info(f"admin panel db ready: {self.db_path}")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=30,
            isolation_level=None,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def overview(self) -> Dict[str, Any]:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_frames,
                    SUM(CASE WHEN annotation_count > 0 THEN 1 ELSE 0 END) AS annotated_frames,
                    SUM(CASE WHEN annotation_count = 1 THEN 1 ELSE 0 END) AS bin_1,
                    SUM(CASE WHEN annotation_count = 2 THEN 1 ELSE 0 END) AS bin_2,
                    SUM(CASE WHEN annotation_count = 3 THEN 1 ELSE 0 END) AS bin_3,
                    SUM(CASE WHEN annotation_count >= 4 THEN 1 ELSE 0 END) AS bin_4p
                FROM frame_counts
                """
            ).fetchone()

            total_annotations = conn.execute(
                "SELECT COUNT(*) AS c FROM annotations"
            ).fetchone()["c"]
            unique_annotators = conn.execute(
                "SELECT COUNT(DISTINCT annotator_id) AS c FROM annotations"
            ).fetchone()["c"]

            annotator_rows = conn.execute(
                """
                SELECT annotator_id, COUNT(*) AS annotation_count
                FROM annotations
                GROUP BY annotator_id
                ORDER BY annotation_count DESC, annotator_id ASC
                """
            ).fetchall()
        finally:
            conn.close()

        return {
            "total_frames": int(row["total_frames"] or 0),
            "annotated_frames": int(row["annotated_frames"] or 0),
            "total_annotations": int(total_annotations or 0),
            "unique_annotators": int(unique_annotators or 0),
            "frame_count_bins": [
                {"label": "1", "count": int(row["bin_1"] or 0)},
                {"label": "2", "count": int(row["bin_2"] or 0)},
                {"label": "3", "count": int(row["bin_3"] or 0)},
                {"label": "4+", "count": int(row["bin_4p"] or 0)},
            ],
            "annotator_counts": [
                {
                    "annotator_id": str(r["annotator_id"]),
                    "annotation_count": int(r["annotation_count"]),
                }
                for r in annotator_rows
            ],
        }

    def annotator_stats(self) -> Dict[str, Any]:
        conn = self._connect()
        try:
            annotation_rows = conn.execute(
                """
                SELECT
                    annotator_id,
                    COUNT(*) AS annotation_count,
                    COUNT(DISTINCT video_stem) AS videos_covered,
                    MAX(submitted_at) AS latest_submitted_at
                FROM annotations
                GROUP BY annotator_id
                """
            ).fetchall()

            assignment_rows = conn.execute(
                """
                SELECT annotator_id, COUNT(*) AS assignment_count
                FROM assignments
                GROUP BY annotator_id
                """
            ).fetchall()

            recent_rows = conn.execute(
                """
                SELECT
                    annotation_id,
                    annotator_id,
                    video_stem,
                    frame_index,
                    submitted_at,
                    slots_json
                FROM annotations
                ORDER BY submitted_at DESC, annotation_id DESC
                LIMIT 500
                """
            ).fetchall()
        finally:
            conn.close()

        merged: Dict[str, Dict[str, Any]] = {}
        for row in annotation_rows:
            aid = str(row["annotator_id"])
            merged[aid] = {
                "annotator_id": aid,
                "annotation_count": int(row["annotation_count"] or 0),
                "assignment_count": 0,
                "videos_covered": int(row["videos_covered"] or 0),
                "latest_submitted_at": row["latest_submitted_at"] or "",
            }

        for row in assignment_rows:
            aid = str(row["annotator_id"])
            merged.setdefault(
                aid,
                {
                    "annotator_id": aid,
                    "annotation_count": 0,
                    "assignment_count": 0,
                    "videos_covered": 0,
                    "latest_submitted_at": "",
                },
            )
            merged[aid]["assignment_count"] = int(row["assignment_count"] or 0)

        annotators = sorted(
            merged.values(),
            key=lambda x: (-int(x["annotation_count"]), -int(x["assignment_count"]), x["annotator_id"]),
        )

        recent_annotations = [
            {
                "annotation_id": str(r["annotation_id"]),
                "annotator_id": str(r["annotator_id"]),
                "video_stem": str(r["video_stem"]),
                "frame_index": int(r["frame_index"]),
                "submitted_at": str(r["submitted_at"]),
                "slots_json": str(r["slots_json"]),
                "slots_summary": slot_summary_from_json(str(r["slots_json"])),
            }
            for r in recent_rows
        ]

        return {
            "annotators": annotators,
            "recent_annotations": recent_annotations,
        }

    def frame_detail(self, video_stem: str, frame_index: int) -> Dict[str, Any]:
        if video_stem not in self.video_stems:
            raise ValueError(f"invalid video_stem: {video_stem}")
        if frame_index <= 0:
            raise ValueError("frame_index must be > 0")

        conn = self._connect()
        try:
            frame_row = conn.execute(
                """
                SELECT
                    f.video_stem,
                    f.frame_index,
                    f.timestamp_ms,
                    fc.annotation_count
                FROM frames f
                JOIN frame_counts fc
                  ON fc.video_stem=f.video_stem
                 AND fc.frame_index=f.frame_index
                WHERE f.video_stem=? AND f.frame_index=?
                """,
                (video_stem, frame_index),
            ).fetchone()
            if frame_row is None:
                raise ValueError("frame not found")

            annotation_rows = conn.execute(
                """
                SELECT
                    annotation_id,
                    annotator_id,
                    submitted_at,
                    slots_json
                FROM annotations
                WHERE video_stem=? AND frame_index=?
                ORDER BY submitted_at ASC, annotation_id ASC
                """,
                (video_stem, frame_index),
            ).fetchall()
        finally:
            conn.close()

        return {
            "video_stem": str(frame_row["video_stem"]),
            "frame_index": int(frame_row["frame_index"]),
            "timestamp_ms": float(frame_row["timestamp_ms"]),
            "annotation_count": int(frame_row["annotation_count"]),
            "annotations": [
                {
                    "annotation_id": str(r["annotation_id"]),
                    "annotator_id": str(r["annotator_id"]),
                    "submitted_at": str(r["submitted_at"]),
                    "slots_json": str(r["slots_json"]),
                    "slots_summary": slot_summary_from_json(str(r["slots_json"])),
                }
                for r in annotation_rows
            ],
        }

    def videos(self) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT
                    video_stem,
                    MIN(frame_index) AS min_frame,
                    MAX(frame_index) AS max_frame,
                    COUNT(*) AS total_frames
                FROM frames
                GROUP BY video_stem
                ORDER BY video_stem ASC
                """
            ).fetchall()
        finally:
            conn.close()
        return [
            {
                "video_stem": str(r["video_stem"]),
                "min_frame": int(r["min_frame"]),
                "max_frame": int(r["max_frame"]),
                "total_frames": int(r["total_frames"]),
            }
            for r in rows
        ]


class AdminHandler(BaseHTTPRequestHandler):
    server_version = "UIAdminPanel/1.0"

    @property
    def state(self) -> AdminState:
        return self.server.state  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: Any) -> None:
        msg = fmt % args
        self.state.logger.info(f"admin_http {self.address_string()} {msg}")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/overview":
            return self._handle_overview()
        if path == "/api/annotators":
            return self._handle_annotators()
        if path == "/api/videos":
            return self._handle_videos()
        if path == "/api/frame_detail":
            return self._handle_frame_detail(parsed.query)

        if path == "/":
            return self._serve_static("index.html", "text/html; charset=utf-8")
        if path == "/styles.css":
            return self._serve_static("styles.css", "text/css; charset=utf-8")
        if path == "/app.js":
            return self._serve_static("app.js", "application/javascript; charset=utf-8")

        self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def _handle_overview(self) -> None:
        try:
            data = self.state.overview()
        except Exception as exc:
            self.state.logger.error(f"overview failed: {exc}")
            return self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
        self._send_json(HTTPStatus.OK, {"ok": True, "overview": data})

    def _handle_annotators(self) -> None:
        try:
            data = self.state.annotator_stats()
        except Exception as exc:
            self.state.logger.error(f"annotators failed: {exc}")
            return self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
        self._send_json(HTTPStatus.OK, {"ok": True, **data})

    def _handle_videos(self) -> None:
        try:
            videos = self.state.videos()
        except Exception as exc:
            self.state.logger.error(f"videos failed: {exc}")
            return self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
        self._send_json(HTTPStatus.OK, {"ok": True, "videos": videos})

    def _handle_frame_detail(self, query: str) -> None:
        q = parse_qs(query)
        stem = str(q.get("video_stem", [""])[0]).strip()
        frame_raw = str(q.get("frame_index", ["0"])[0]).strip()
        try:
            frame_index = int(frame_raw)
            data = self.state.frame_detail(stem, frame_index)
        except Exception as exc:
            self.state.logger.error(f"frame_detail failed stem={stem} frame={frame_raw}: {exc}")
            return self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
        self._send_json(HTTPStatus.OK, {"ok": True, "frame": data})

    def _serve_static(self, filename: str, content_type: str) -> None:
        path = self.state.static_dir / filename
        if not path.exists():
            return self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": f"missing static: {filename}"})
        content = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, status: HTTPStatus, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Admin panel server for UI review database")
    parser.add_argument("--batch-dir", type=Path, required=True, help="Batch directory path, e.g. ./annotation/batch_20260305_v03")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=10087, help="Bind port")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    batch_dir = resolve_repo_path(args.batch_dir)
    if not batch_dir.exists():
        raise SystemExit(f"batch directory does not exist: {batch_dir}")

    static_dir = (Path(__file__).resolve().parent / "ui_admin_web").resolve()
    state = AdminState(batch_dir=batch_dir, static_dir=static_dir)
    state.initialize()

    server = ThreadingHTTPServer((args.host, args.port), AdminHandler)
    server.state = state  # type: ignore[attr-defined]
    state.logger.info(
        f"admin panel server running at http://localhost:{args.port} batch_dir={batch_dir}"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        state.logger.info("admin panel interrupted, shutting down")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
