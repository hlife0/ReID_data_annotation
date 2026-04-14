#!/usr/bin/env python3
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple


STATE_SOURCES = {"absent", "occluded", "outside"}


def _safe_float(value: Any) -> float:
    return float(f"{float(value):.3f}")


def empty_slot_record(slot_name: str) -> Dict[str, Any]:
    return {
        "slot": slot_name,
        "bbox_x": 0.0,
        "bbox_y": 0.0,
        "bbox_w": 0.0,
        "bbox_h": 0.0,
        "source": "not_set",
        "ai_track_id": "",
    }


def _normalize_slot(slot_name: str, item: Dict[str, Any]) -> Dict[str, Any]:
    source = str(item.get("source", "not_set")).strip() or "not_set"
    track_id = str(item.get("ai_track_id", "") or "").strip()
    if source in STATE_SOURCES or source == "not_set":
        return empty_slot_record(slot_name) | {
            "slot": slot_name,
            "source": source,
            "ai_track_id": "",
        }
    return {
        "slot": slot_name,
        "bbox_x": _safe_float(item.get("bbox_x", 0.0)),
        "bbox_y": _safe_float(item.get("bbox_y", 0.0)),
        "bbox_w": _safe_float(item.get("bbox_w", 0.0)),
        "bbox_h": _safe_float(item.get("bbox_h", 0.0)),
        "source": source,
        "ai_track_id": track_id,
    }


def _bbox_from_slot(item: Dict[str, Any]) -> Dict[str, float] | None:
    if str(item.get("source", "")).strip() in STATE_SOURCES | {"not_set"}:
        return None
    w = float(item.get("bbox_w", 0.0))
    h = float(item.get("bbox_h", 0.0))
    if w <= 0 or h <= 0:
        return None
    return {
        "x": _safe_float(item.get("bbox_x", 0.0)),
        "y": _safe_float(item.get("bbox_y", 0.0)),
        "w": _safe_float(w),
        "h": _safe_float(h),
    }


def _lookup_ai_box(
    ai_boxes: Dict[Tuple[str, int], List[Dict[str, Any]]],
    video_stem: str,
    frame_index: int,
    track_id: str,
) -> Dict[str, Any] | None:
    if not track_id:
        return None
    for box in ai_boxes.get((video_stem, frame_index), []):
        if str(int(float(box.get("track_id", 0)))) == track_id:
            return {
                "track_id": track_id,
                "bbox_x": _safe_float(box.get("bbox_x", 0.0)),
                "bbox_y": _safe_float(box.get("bbox_y", 0.0)),
                "bbox_w": _safe_float(box.get("bbox_w", 0.0)),
                "bbox_h": _safe_float(box.get("bbox_h", 0.0)),
            }
    return None


def _anchor_correction(
    slot_item: Dict[str, Any],
    ai_box: Dict[str, Any] | None,
) -> Dict[str, float] | None:
    bbox = _bbox_from_slot(slot_item)
    if bbox is None or ai_box is None:
        return None
    return {
        "dx": _safe_float(bbox["x"] - ai_box["bbox_x"]),
        "dy": _safe_float(bbox["y"] - ai_box["bbox_y"]),
        "dw": _safe_float(bbox["w"] - ai_box["bbox_w"]),
        "dh": _safe_float(bbox["h"] - ai_box["bbox_h"]),
    }


def _apply_correction(
    slot_name: str,
    ai_box: Dict[str, Any],
    correction: Dict[str, float],
    source: str,
) -> Dict[str, Any]:
    return {
        "slot": slot_name,
        "bbox_x": _safe_float(ai_box["bbox_x"] + correction["dx"]),
        "bbox_y": _safe_float(ai_box["bbox_y"] + correction["dy"]),
        "bbox_w": _safe_float(ai_box["bbox_w"] + correction["dw"]),
        "bbox_h": _safe_float(ai_box["bbox_h"] + correction["dh"]),
        "source": source,
        "ai_track_id": str(ai_box["track_id"]),
    }


def _copy_slot(slot_name: str, item: Dict[str, Any]) -> Dict[str, Any]:
    return _normalize_slot(slot_name, item)


def _lerp(a: float, b: float, t: float) -> float:
    return _safe_float((1.0 - t) * a + t * b)


def _lerp_bbox(slot_name: str, start_item: Dict[str, Any], end_item: Dict[str, Any], t: float) -> Dict[str, Any]:
    start_bbox = _bbox_from_slot(start_item)
    end_bbox = _bbox_from_slot(end_item)
    if start_bbox is None or end_bbox is None:
        return _copy_slot(slot_name, start_item if t < 0.5 else end_item)
    return {
        "slot": slot_name,
        "bbox_x": _lerp(start_bbox["x"], end_bbox["x"], t),
        "bbox_y": _lerp(start_bbox["y"], end_bbox["y"], t),
        "bbox_w": _lerp(start_bbox["w"], end_bbox["w"], t),
        "bbox_h": _lerp(start_bbox["h"], end_bbox["h"], t),
        "source": "manual_param",
        "ai_track_id": "",
    }


def _choose_track_box(
    ai_boxes: Dict[Tuple[str, int], List[Dict[str, Any]]],
    video_stem: str,
    frame_index: int,
    start_track_id: str,
    end_track_id: str,
    midpoint: float,
) -> Dict[str, Any] | None:
    start_box = _lookup_ai_box(ai_boxes, video_stem, frame_index, start_track_id)
    end_box = _lookup_ai_box(ai_boxes, video_stem, frame_index, end_track_id)
    if start_track_id == end_track_id:
        return start_box or end_box
    if frame_index <= midpoint:
        return start_box or end_box
    return end_box or start_box


def _propagate_single_anchor(
    slot_name: str,
    video_stem: str,
    frame_indices: Iterable[int],
    ai_boxes: Dict[Tuple[str, int], List[Dict[str, Any]]],
    anchor_frame: int,
    anchor_item: Dict[str, Any],
) -> Dict[int, Dict[str, Any]]:
    anchor = _copy_slot(slot_name, anchor_item)
    source = str(anchor.get("source", "")).strip()
    if source in STATE_SOURCES:
        return {frame_index: _copy_slot(slot_name, anchor) for frame_index in frame_indices}

    track_id = str(anchor.get("ai_track_id", "")).strip()
    anchor_ai_box = _lookup_ai_box(ai_boxes, video_stem, anchor_frame, track_id)
    correction = _anchor_correction(anchor, anchor_ai_box)
    result: Dict[int, Dict[str, Any]] = {}
    for frame_index in frame_indices:
        if frame_index == anchor_frame:
            result[frame_index] = _copy_slot(slot_name, anchor)
            continue
        if correction is not None and track_id:
            target_ai_box = _lookup_ai_box(ai_boxes, video_stem, frame_index, track_id)
            if target_ai_box is not None:
                propagated_source = "ai" if source == "ai" and all(v == 0.0 for v in correction.values()) else "manual_param"
                result[frame_index] = _apply_correction(slot_name, target_ai_box, correction, propagated_source)
                continue
        bbox = _bbox_from_slot(anchor)
        if bbox is None:
            result[frame_index] = _copy_slot(slot_name, anchor)
            continue
        result[frame_index] = {
            "slot": slot_name,
            "bbox_x": bbox["x"],
            "bbox_y": bbox["y"],
            "bbox_w": bbox["w"],
            "bbox_h": bbox["h"],
            "source": "manual_param" if source == "ai" else source,
            "ai_track_id": track_id,
        }
    return result


def _propagate_between_keyframes(
    slot_name: str,
    video_stem: str,
    start_frame: int,
    end_frame: int,
    ai_boxes: Dict[Tuple[str, int], List[Dict[str, Any]]],
    start_item: Dict[str, Any],
    end_item: Dict[str, Any],
) -> Dict[int, Dict[str, Any]]:
    start_slot = _copy_slot(slot_name, start_item)
    end_slot = _copy_slot(slot_name, end_item)
    start_source = str(start_slot.get("source", "")).strip()
    end_source = str(end_slot.get("source", "")).strip()
    if end_frame < start_frame:
        return {}

    if start_source in STATE_SOURCES and end_source in STATE_SOURCES and start_source == end_source:
        return {
            frame_index: _copy_slot(slot_name, start_slot)
            for frame_index in range(start_frame, end_frame + 1)
        }

    result: Dict[int, Dict[str, Any]] = {}
    if start_source in STATE_SOURCES:
        for frame_index in range(start_frame, end_frame):
            result[frame_index] = _copy_slot(slot_name, start_slot)
        result[end_frame] = _copy_slot(slot_name, end_slot)
        return result

    if end_source in STATE_SOURCES:
        head = _propagate_single_anchor(
            slot_name=slot_name,
            video_stem=video_stem,
            frame_indices=range(start_frame, end_frame),
            ai_boxes=ai_boxes,
            anchor_frame=start_frame,
            anchor_item=start_slot,
        )
        result.update(head)
        result[end_frame] = _copy_slot(slot_name, end_slot)
        return result

    start_track_id = str(start_slot.get("ai_track_id", "")).strip()
    end_track_id = str(end_slot.get("ai_track_id", "")).strip()
    start_ai_box = _lookup_ai_box(ai_boxes, video_stem, start_frame, start_track_id)
    end_ai_box = _lookup_ai_box(ai_boxes, video_stem, end_frame, end_track_id)
    start_correction = _anchor_correction(start_slot, start_ai_box)
    end_correction = _anchor_correction(end_slot, end_ai_box)
    midpoint = (start_frame + end_frame) / 2.0
    span = max(1, end_frame - start_frame)

    for frame_index in range(start_frame, end_frame + 1):
        if frame_index == start_frame:
            result[frame_index] = _copy_slot(slot_name, start_slot)
            continue
        if frame_index == end_frame:
            result[frame_index] = _copy_slot(slot_name, end_slot)
            continue

        t = (frame_index - start_frame) / span
        if start_correction is not None and end_correction is not None and (start_track_id or end_track_id):
            chosen_ai_box = _choose_track_box(
                ai_boxes=ai_boxes,
                video_stem=video_stem,
                frame_index=frame_index,
                start_track_id=start_track_id,
                end_track_id=end_track_id,
                midpoint=midpoint,
            )
            if chosen_ai_box is not None:
                correction = {
                    "dx": _lerp(start_correction["dx"], end_correction["dx"], t),
                    "dy": _lerp(start_correction["dy"], end_correction["dy"], t),
                    "dw": _lerp(start_correction["dw"], end_correction["dw"], t),
                    "dh": _lerp(start_correction["dh"], end_correction["dh"], t),
                }
                source = "manual_param"
                if (
                    start_source == "ai"
                    and end_source == "ai"
                    and all(v == 0.0 for v in correction.values())
                ):
                    source = "ai"
                result[frame_index] = _apply_correction(slot_name, chosen_ai_box, correction, source)
                continue

        result[frame_index] = _lerp_bbox(slot_name, start_slot, end_slot, t)
    return result


def propagate_issue_keyframes(
    video_stem: str,
    start_frame: int,
    end_frame: int,
    slot_names: List[str],
    ai_boxes: Dict[Tuple[str, int], List[Dict[str, Any]]],
    keyframes: List[Dict[str, Any]],
) -> Dict[int, List[Dict[str, Any]]]:
    if end_frame < start_frame:
        raise ValueError("end_frame must be >= start_frame")

    dedup: Dict[int, Dict[str, Dict[str, Any]]] = {}
    for raw in keyframes:
        frame_index = int(raw.get("frame_index", 0))
        if frame_index < start_frame or frame_index > end_frame:
            continue
        slot_map = {
            slot_name: _normalize_slot(slot_name, item)
            for item in raw.get("slots", [])
            if isinstance(item, dict)
            for slot_name in [str(item.get("slot", "")).strip().lower()]
            if slot_name in slot_names
        }
        dedup[frame_index] = slot_map
    normalized_keyframes = [(frame_index, dedup[frame_index]) for frame_index in sorted(dedup)]
    if not normalized_keyframes:
        raise ValueError("at least one keyframe is required")

    propagated: Dict[int, Dict[str, Dict[str, Any]]] = {
        frame_index: {}
        for frame_index in range(start_frame, end_frame + 1)
    }

    for slot_name in slot_names:
        anchors = [
            (frame_index, slot_map[slot_name])
            for frame_index, slot_map in normalized_keyframes
            if slot_name in slot_map
        ]
        if not anchors:
            for frame_index in range(start_frame, end_frame + 1):
                propagated[frame_index][slot_name] = empty_slot_record(slot_name)
            continue

        if len(anchors) == 1:
            fill = _propagate_single_anchor(
                slot_name=slot_name,
                video_stem=video_stem,
                frame_indices=range(start_frame, end_frame + 1),
                ai_boxes=ai_boxes,
                anchor_frame=anchors[0][0],
                anchor_item=anchors[0][1],
            )
            for frame_index, slot in fill.items():
                propagated[frame_index][slot_name] = slot
            continue

        first_frame, first_item = anchors[0]
        prefix = _propagate_single_anchor(
            slot_name=slot_name,
            video_stem=video_stem,
            frame_indices=range(start_frame, first_frame + 1),
            ai_boxes=ai_boxes,
            anchor_frame=first_frame,
            anchor_item=first_item,
        )
        for frame_index, slot in prefix.items():
            propagated[frame_index][slot_name] = slot

        for (left_frame, left_item), (right_frame, right_item) in zip(anchors, anchors[1:]):
            middle = _propagate_between_keyframes(
                slot_name=slot_name,
                video_stem=video_stem,
                start_frame=left_frame,
                end_frame=right_frame,
                ai_boxes=ai_boxes,
                start_item=left_item,
                end_item=right_item,
            )
            for frame_index, slot in middle.items():
                propagated[frame_index][slot_name] = slot

        last_frame, last_item = anchors[-1]
        suffix = _propagate_single_anchor(
            slot_name=slot_name,
            video_stem=video_stem,
            frame_indices=range(last_frame, end_frame + 1),
            ai_boxes=ai_boxes,
            anchor_frame=last_frame,
            anchor_item=last_item,
        )
        for frame_index, slot in suffix.items():
            propagated[frame_index][slot_name] = slot

    return {
        frame_index: [
            propagated[frame_index].get(slot_name, empty_slot_record(slot_name))
            for slot_name in slot_names
        ]
        for frame_index in range(start_frame, end_frame + 1)
    }
