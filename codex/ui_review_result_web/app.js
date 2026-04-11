const SLOT_META = {
  p1: { label: "P1", color: "#1d9a58" },
  p2: { label: "P2", color: "#54606e" },
};
const HANDLE_SIZE = 8;
const MIN_BOX_SIZE = 2;
const DEFAULT_REVIEWER_ID = "reviewer_demo";

const state = {
  sample: null,
  image: null,
  imageRequestId: 0,
  lang: "zh",
  redrawMode: false,
  drawSlot: null,
  action: null,
  syncingInputs: false,
  slots: {
    p1: { bbox: null, source: "not_set" },
    p2: { bbox: null, source: "not_set" },
  },
  activeSlot: "p1",
};

const refs = {
  reviewerId: document.getElementById("reviewerId"),
  nextSampleBtn: document.getElementById("nextSampleBtn"),
  redrawModeBtn: document.getElementById("redrawModeBtn"),
  videoStem: document.getElementById("videoStem"),
  frameIndex: document.getElementById("frameIndex"),
  timestampMs: document.getElementById("timestampMs"),
  candidateDice: document.getElementById("candidateDice"),
  pendingCount: document.getElementById("pendingCount"),
  acceptLeftBtn: document.getElementById("acceptLeftBtn"),
  acceptRightBtn: document.getElementById("acceptRightBtn"),
  leftCanvas: document.getElementById("leftCanvas"),
  rightCanvas: document.getElementById("rightCanvas"),
  leftAnnotator: document.getElementById("leftAnnotator"),
  rightAnnotator: document.getElementById("rightAnnotator"),
  leftSubmitted: document.getElementById("leftSubmitted"),
  rightSubmitted: document.getElementById("rightSubmitted"),
  leftP1Source: document.getElementById("leftP1Source"),
  leftP2Source: document.getElementById("leftP2Source"),
  rightP1Source: document.getElementById("rightP1Source"),
  rightP2Source: document.getElementById("rightP2Source"),
  compareView: document.getElementById("compareView"),
  redrawView: document.getElementById("redrawView"),
  canvas: document.getElementById("frameCanvas"),
  canvasHint: document.getElementById("canvasHint"),
  p1Source: document.getElementById("p1Source"),
  p2Source: document.getElementById("p2Source"),
  p1UseLeftBtn: document.getElementById("p1UseLeftBtn"),
  p1UseRightBtn: document.getElementById("p1UseRightBtn"),
  p2UseLeftBtn: document.getElementById("p2UseLeftBtn"),
  p2UseRightBtn: document.getElementById("p2UseRightBtn"),
  p1DrawBtn: document.getElementById("p1DrawBtn"),
  p1AbsentBtn: document.getElementById("p1AbsentBtn"),
  p2DrawBtn: document.getElementById("p2DrawBtn"),
  p2AbsentBtn: document.getElementById("p2AbsentBtn"),
  p1X: document.getElementById("p1X"),
  p1Y: document.getElementById("p1Y"),
  p1W: document.getElementById("p1W"),
  p1H: document.getElementById("p1H"),
  p2X: document.getElementById("p2X"),
  p2Y: document.getElementById("p2Y"),
  p2W: document.getElementById("p2W"),
  p2H: document.getElementById("p2H"),
  cancelRedrawBtn: document.getElementById("cancelRedrawBtn"),
  submitRedrawBtn: document.getElementById("submitRedrawBtn"),
  toast: document.getElementById("toast"),
};
const ctx = refs.canvas.getContext("2d");
const leftCtx = refs.leftCanvas.getContext("2d");
const rightCtx = refs.rightCanvas.getContext("2d");

function reviewerId() {
  return refs.reviewerId.value.trim() || "reviewer_unknown";
}

function showToast(text, isError = false) {
  refs.toast.textContent = text;
  refs.toast.style.background = isError ? "rgba(140,29,25,0.92)" : "rgba(20,35,48,0.92)";
  refs.toast.classList.add("show");
  setTimeout(() => refs.toast.classList.remove("show"), 1800);
}

async function postJson(url, data) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok || !payload.ok) {
    throw new Error(payload.error || `Request failed (${res.status})`);
  }
  return payload;
}

function sourceLabel(source) {
  if (source === "left_candidate") return "left";
  if (source === "right_candidate") return "right";
  return source || "not_set";
}

function bboxValid(b) {
  return !!b && b.w > 0 && b.h > 0;
}

function cloneBbox(b) {
  return b ? { x: b.x, y: b.y, w: b.w, h: b.h } : null;
}

function clampBbox(bbox) {
  if (!state.image) return bbox;
  const maxW = state.image.width;
  const maxH = state.image.height;
  const x = Math.max(0, Math.min(maxW - MIN_BOX_SIZE, bbox.x));
  const y = Math.max(0, Math.min(maxH - MIN_BOX_SIZE, bbox.y));
  let w = Math.max(MIN_BOX_SIZE, bbox.w);
  let h = Math.max(MIN_BOX_SIZE, bbox.h);
  if (x + w > maxW) w = maxW - x;
  if (y + h > maxH) h = maxH - y;
  return { x: round3(x), y: round3(y), w: round3(w), h: round3(h) };
}

function round3(num) {
  return Math.round(num * 1000) / 1000;
}

function setSlotBbox(slot, bbox, source) {
  state.slots[slot].bbox = bbox ? clampBbox(bbox) : null;
  state.slots[slot].source = source;
  syncSlotUI(slot);
  drawCanvas();
}

function syncSlotUI(slot) {
  const s = state.slots[slot];
  const inputs = slot === "p1"
    ? [refs.p1X, refs.p1Y, refs.p1W, refs.p1H]
    : [refs.p2X, refs.p2Y, refs.p2W, refs.p2H];
  const sourceEl = slot === "p1" ? refs.p1Source : refs.p2Source;
  state.syncingInputs = true;
  if (s.source === "absent") {
    inputs.forEach((el) => { el.value = "0"; el.disabled = true; });
  } else if (bboxValid(s.bbox)) {
    inputs[0].value = s.bbox.x;
    inputs[1].value = s.bbox.y;
    inputs[2].value = s.bbox.w;
    inputs[3].value = s.bbox.h;
    inputs.forEach((el) => { el.disabled = false; });
  } else {
    inputs.forEach((el) => { el.value = ""; el.disabled = false; });
  }
  state.syncingInputs = false;
  sourceEl.textContent = sourceLabel(s.source);
}

function handlePoints(bbox) {
  const x1 = bbox.x;
  const y1 = bbox.y;
  const x2 = bbox.x + bbox.w;
  const y2 = bbox.y + bbox.h;
  const xm = (x1 + x2) / 2;
  const ym = (y1 + y2) / 2;
  return {
    nw: { x: x1, y: y1 }, n: { x: xm, y: y1 }, ne: { x: x2, y: y1 },
    e: { x: x2, y: ym }, se: { x: x2, y: y2 }, s: { x: xm, y: y2 },
    sw: { x: x1, y: y2 }, w: { x: x1, y: ym },
  };
}


function drawCandidateCanvas(canvas, canvasCtx, candidate) {
  if (!state.image || !candidate) return;
  canvas.width = state.image.width;
  canvas.height = state.image.height;
  canvasCtx.clearRect(0, 0, canvas.width, canvas.height);
  canvasCtx.drawImage(state.image, 0, 0, canvas.width, canvas.height);
  for (const slot of ["p1", "p2"]) {
    const person = candidate[slot];
    if (!person || person.source === "absent") continue;
    const color = SLOT_META[slot].color;
    canvasCtx.save();
    canvasCtx.strokeStyle = color;
    canvasCtx.lineWidth = 3;
    canvasCtx.strokeRect(person.bbox_x, person.bbox_y, person.bbox_w, person.bbox_h);
    drawLabelOnCtx(canvasCtx, SLOT_META[slot].label, person.bbox_x + 2, person.bbox_y + 2, color);
    canvasCtx.restore();
  }
}

function drawLabelOnCtx(targetCtx, text, x, y, color) {
  targetCtx.font = "bold 14px 'Trebuchet MS', sans-serif";
  const w = targetCtx.measureText(text).width + 10;
  targetCtx.fillStyle = color;
  targetCtx.fillRect(x, Math.max(0, y - 18), w, 18);
  targetCtx.fillStyle = "#fff";
  targetCtx.fillText(text, x + 5, Math.max(12, y - 4));
}

function drawLabel(text, x, y, color) {
  ctx.font = "bold 14px 'Trebuchet MS', sans-serif";
  const w = ctx.measureText(text).width + 10;
  ctx.fillStyle = color;
  ctx.fillRect(x, Math.max(0, y - 18), w, 18);
  ctx.fillStyle = "#fff";
  ctx.fillText(text, x + 5, Math.max(12, y - 4));
}

function drawHandles(bbox, color) {
  for (const p of Object.values(handlePoints(bbox))) {
    ctx.fillStyle = color;
    ctx.fillRect(p.x - HANDLE_SIZE / 2, p.y - HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE);
  }
}

function drawCanvas() {
  if (!state.image) {
    ctx.clearRect(0, 0, refs.canvas.width, refs.canvas.height);
    return;
  }
  ctx.clearRect(0, 0, refs.canvas.width, refs.canvas.height);
  ctx.drawImage(state.image, 0, 0, refs.canvas.width, refs.canvas.height);
  for (const slot of ["p1", "p2"]) {
    const s = state.slots[slot];
    if (!bboxValid(s.bbox)) continue;
    const b = s.bbox;
    const color = SLOT_META[slot].color;
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = slot === state.activeSlot ? 3 : 2;
    ctx.strokeRect(b.x, b.y, b.w, b.h);
    drawLabel(`${SLOT_META[slot].label}`, b.x + 2, b.y + 2, color);
    drawHandles(b, color);
    ctx.restore();
  }
}

function renderSample(sample) {
  state.sample = sample;
  refs.videoStem.textContent = sample.video_stem;
  refs.frameIndex.textContent = sample.frame_index;
  refs.timestampMs.textContent = sample.timestamp_ms;
  refs.candidateDice.textContent = sample.candidate_dice;
  refs.pendingCount.textContent = sample.done ? 0 : "...";
  refs.leftAnnotator.textContent = sample.left.annotator_id;
  refs.rightAnnotator.textContent = sample.right.annotator_id;
  refs.leftSubmitted.textContent = sample.left.submitted_at.replace("T", " ").slice(0, 19);
  refs.rightSubmitted.textContent = sample.right.submitted_at.replace("T", " ").slice(0, 19);
  refs.leftP1Source.textContent = sample.left.p1.source;
  refs.leftP2Source.textContent = sample.left.p2.source;
  refs.rightP1Source.textContent = sample.right.p1.source;
  refs.rightP2Source.textContent = sample.right.p2.source;
  const imgSrc = `${sample.image_url}&_ts=${Date.now()}`;
  const img = new Image();
  const requestId = ++state.imageRequestId;
  img.onload = () => {
    if (requestId !== state.imageRequestId) return;
    state.image = img;
    refs.canvas.width = img.width;
    refs.canvas.height = img.height;
    drawCanvas();
    drawCandidateCanvas(refs.leftCanvas, leftCtx, sample.left);
    drawCandidateCanvas(refs.rightCanvas, rightCtx, sample.right);
  };
  img.src = imgSrc;
}

function resetRedrawSlots() {
  state.slots.p1 = { bbox: null, source: "not_set" };
  state.slots.p2 = { bbox: null, source: "not_set" };
  syncSlotUI("p1");
  syncSlotUI("p2");
  drawCanvas();
}

function useCandidate(slot, side) {
  if (!state.sample) return;
  const candidate = state.sample[side][slot];
  if (candidate.source === "absent") {
    setSlotBbox(slot, null, "absent");
    return;
  }
  setSlotBbox(slot, {
    x: Number(candidate.bbox_x),
    y: Number(candidate.bbox_y),
    w: Number(candidate.bbox_w),
    h: Number(candidate.bbox_h),
  }, `${side}_candidate`);
}

function markAbsent(slot) {
  setSlotBbox(slot, null, "absent");
}

function startDraw(slot) {
  state.drawSlot = slot;
  state.activeSlot = slot;
  refs.canvas.style.cursor = "crosshair";
}

function canvasPoint(evt) {
  const rect = refs.canvas.getBoundingClientRect();
  const scaleX = refs.canvas.width / rect.width;
  const scaleY = refs.canvas.height / rect.height;
  return { x: (evt.clientX - rect.left) * scaleX, y: (evt.clientY - rect.top) * scaleY };
}

function pointInBbox(point, bbox) {
  return point.x >= bbox.x && point.x <= bbox.x + bbox.w && point.y >= bbox.y && point.y <= bbox.y + bbox.h;
}

function hitTest(point) {
  for (const slot of ["p1", "p2"]) {
    const b = state.slots[slot].bbox;
    if (!bboxValid(b)) continue;
    const handles = handlePoints(b);
    for (const [name, h] of Object.entries(handles)) {
      if (Math.abs(point.x - h.x) <= HANDLE_SIZE && Math.abs(point.y - h.y) <= HANDLE_SIZE) {
        return { slot, type: "resize", handle: name };
      }
    }
    if (pointInBbox(point, b)) return { slot, type: "move" };
  }
  return null;
}

function resizeFromHandle(orig, handle, point) {
  let x1 = orig.x, y1 = orig.y, x2 = orig.x + orig.w, y2 = orig.y + orig.h;
  if (handle.includes("n")) y1 = point.y;
  if (handle.includes("s")) y2 = point.y;
  if (handle.includes("w")) x1 = point.x;
  if (handle.includes("e")) x2 = point.x;
  if (x2 - x1 < MIN_BOX_SIZE) { if (handle.includes("w")) x1 = x2 - MIN_BOX_SIZE; else x2 = x1 + MIN_BOX_SIZE; }
  if (y2 - y1 < MIN_BOX_SIZE) { if (handle.includes("n")) y1 = y2 - MIN_BOX_SIZE; else y2 = y1 + MIN_BOX_SIZE; }
  return clampBbox({ x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1), h: Math.abs(y2 - y1) });
}

function onCanvasDown(evt) {
  if (!state.redrawMode || !state.image) return;
  const point = canvasPoint(evt);
  if (state.drawSlot) {
    const slot = state.drawSlot;
    state.action = { type: "drawing", slot, start: point };
    setSlotBbox(slot, { x: point.x, y: point.y, w: MIN_BOX_SIZE, h: MIN_BOX_SIZE }, "manual_draw");
    return;
  }
  const hit = hitTest(point);
  if (!hit) return;
  state.activeSlot = hit.slot;
  state.action = { ...hit, start: point, orig: cloneBbox(state.slots[hit.slot].bbox) };
}

function onCanvasMove(evt) {
  if (!state.redrawMode || !state.image || !state.action) return;
  const point = canvasPoint(evt);
  const action = state.action;
  if (action.type === "drawing") {
    const x = Math.min(action.start.x, point.x);
    const y = Math.min(action.start.y, point.y);
    const w = Math.max(MIN_BOX_SIZE, Math.abs(point.x - action.start.x));
    const h = Math.max(MIN_BOX_SIZE, Math.abs(point.y - action.start.y));
    setSlotBbox(action.slot, { x, y, w, h }, "manual_draw");
    return;
  }
  if (action.type === "move") {
    const b = action.orig;
    setSlotBbox(action.slot, { x: b.x + (point.x - action.start.x), y: b.y + (point.y - action.start.y), w: b.w, h: b.h }, "manual_draw");
    return;
  }
  if (action.type === "resize") {
    setSlotBbox(action.slot, resizeFromHandle(action.orig, action.handle, point), "manual_draw");
  }
}

function onCanvasUp() {
  if (state.action && state.action.type === "drawing") state.drawSlot = null;
  state.action = null;
  refs.canvas.style.cursor = "default";
}

function bindNumericInputs(slot) {
  const fields = slot === "p1"
    ? { x: refs.p1X, y: refs.p1Y, w: refs.p1W, h: refs.p1H }
    : { x: refs.p2X, y: refs.p2Y, w: refs.p2W, h: refs.p2H };
  const onInput = () => {
    if (state.syncingInputs) return;
    const values = { x: Number(fields.x.value), y: Number(fields.y.value), w: Number(fields.w.value), h: Number(fields.h.value) };
    if (Object.values(values).some((v) => Number.isNaN(v))) return;
    setSlotBbox(slot, values, "manual_param");
  };
  fields.x.addEventListener("input", onInput);
  fields.y.addEventListener("input", onInput);
  fields.w.addEventListener("input", onInput);
  fields.h.addEventListener("input", onInput);
}

function enterRedrawMode() {
  state.redrawMode = true;
  refs.compareView.hidden = true;
  refs.redrawView.hidden = false;
  resetRedrawSlots();
}

function exitRedrawMode() {
  state.redrawMode = false;
  refs.compareView.hidden = false;
  refs.redrawView.hidden = true;
  state.drawSlot = null;
  state.action = null;
}

function buildRedrawPayload() {
  const personPayload = (slot) => {
    const person = state.slots[slot];
    if (person.source === "absent") {
      return { bbox_x: 0, bbox_y: 0, bbox_w: 0, bbox_h: 0, source: "absent" };
    }
    if (!bboxValid(person.bbox)) throw new Error(`${slot.toUpperCase()} 框未设置`);
    return {
      bbox_x: round3(person.bbox.x), bbox_y: round3(person.bbox.y), bbox_w: round3(person.bbox.w), bbox_h: round3(person.bbox.h), source: person.source,
    };
  };
  return {
    reviewer_id: reviewerId(),
    video_stem: state.sample.video_stem,
    frame_index: state.sample.frame_index,
    p1: personPayload("p1"),
    p2: personPayload("p2"),
  };
}

async function loadNextSample() {
  const payload = await postJson("/api/review_next", { reviewer_id: reviewerId() });
  if (payload.done || !payload.sample) {
    refs.videoStem.textContent = "done";
    refs.frameIndex.textContent = "-";
    refs.timestampMs.textContent = "-";
    refs.candidateDice.textContent = "-";
    refs.pendingCount.textContent = "0";
    state.sample = null;
    showToast("没有待复审样本了");
    return;
  }
  renderSample(payload.sample);
  exitRedrawMode();
}

async function acceptSide(side) {
  if (!state.sample) return;
  const result = await postJson("/api/review_accept", {
    reviewer_id: reviewerId(),
    video_stem: state.sample.video_stem,
    frame_index: state.sample.frame_index,
    accepted_side: side,
  });
  showToast(`已接受${side === "left" ? "左边" : "右边"}`);
  if (result.done || !result.sample) {
    state.sample = null;
    refs.pendingCount.textContent = "0";
    refs.videoStem.textContent = "done";
    return;
  }
  renderSample(result.sample);
}

async function submitRedraw() {
  if (!state.sample) return;
  try {
    const payload = buildRedrawPayload();
    const result = await postJson("/api/review_redraw", payload);
    showToast("已提交重画结果");
    if (result.done || !result.sample) {
      state.sample = null;
      refs.pendingCount.textContent = "0";
      refs.videoStem.textContent = "done";
      return;
    }
    renderSample(result.sample);
    exitRedrawMode();
  } catch (err) {
    showToast(err.message, true);
  }
}

function initEvents() {
  refs.reviewerId.value = localStorage.getItem("ui_review_result_reviewer_id") || DEFAULT_REVIEWER_ID;
  refs.reviewerId.addEventListener("change", () => {
    localStorage.setItem("ui_review_result_reviewer_id", reviewerId());
  });
  refs.nextSampleBtn.addEventListener("click", () => loadNextSample().catch((err) => showToast(err.message, true)));
  refs.acceptLeftBtn.addEventListener("click", () => acceptSide("left").catch((err) => showToast(err.message, true)));
  refs.acceptRightBtn.addEventListener("click", () => acceptSide("right").catch((err) => showToast(err.message, true)));
  refs.redrawModeBtn.addEventListener("click", enterRedrawMode);
  refs.cancelRedrawBtn.addEventListener("click", exitRedrawMode);
  refs.submitRedrawBtn.addEventListener("click", submitRedraw);
  refs.p1UseLeftBtn.addEventListener("click", () => useCandidate("p1", "left"));
  refs.p1UseRightBtn.addEventListener("click", () => useCandidate("p1", "right"));
  refs.p2UseLeftBtn.addEventListener("click", () => useCandidate("p2", "left"));
  refs.p2UseRightBtn.addEventListener("click", () => useCandidate("p2", "right"));
  refs.p1DrawBtn.addEventListener("click", () => startDraw("p1"));
  refs.p2DrawBtn.addEventListener("click", () => startDraw("p2"));
  refs.p1AbsentBtn.addEventListener("click", () => markAbsent("p1"));
  refs.p2AbsentBtn.addEventListener("click", () => markAbsent("p2"));
  bindNumericInputs("p1");
  bindNumericInputs("p2");
  refs.canvas.addEventListener("mousedown", onCanvasDown);
  refs.canvas.addEventListener("mousemove", onCanvasMove);
  refs.canvas.addEventListener("mouseup", onCanvasUp);
  refs.canvas.addEventListener("mouseleave", onCanvasUp);
}

function init() {
  initEvents();
  exitRedrawMode();
  loadNextSample().catch((err) => showToast(err.message, true));
}

window.addEventListener("DOMContentLoaded", init);
