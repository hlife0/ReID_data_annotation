const SLOT_NAMES = ["p1", "p2", "p3", "p4", "p5", "p6", "p7"];
const ALLOWED_DECISIONS = ["ai_match", "absent", "needs_manual"];
const ANNOTATOR_STORAGE_KEY = "human_stage_1_annotator_id";
const HISTORY_COLLAPSED_KEY = "human_stage_1_history_collapsed";

const refs = {
  annotatorId: document.getElementById("annotatorId"),
  nextBtn: document.getElementById("nextBtn"),
  submitBtn: document.getElementById("submitBtn"),
  videoStem: document.getElementById("videoStem"),
  segmentId: document.getElementById("segmentId"),
  segmentType: document.getElementById("segmentType"),
  frameIndex: document.getElementById("frameIndex"),
  frameMeta: document.getElementById("frameMeta"),
  frameImage: document.getElementById("frameImage"),
  aiOverlay: document.getElementById("aiOverlay"),
  aiLegend: document.getElementById("aiLegend"),
  slotTabs: document.getElementById("slotTabs"),
  activeSlotTitle: document.getElementById("activeSlotTitle"),
  activeSlotSummary: document.getElementById("activeSlotSummary"),
  activeAiButtons: document.getElementById("activeAiButtons"),
  activeAbsentBtn: document.getElementById("activeAbsentBtn"),
  activeNeedsManualBtn: document.getElementById("activeNeedsManualBtn"),
  markRemainingAbsentBtn: document.getElementById("markRemainingAbsentBtn"),
  historyDock: document.getElementById("historyDock"),
  historyToggleBtn: document.getElementById("historyToggleBtn"),
  historyList: document.getElementById("historyList"),
  refreshHistoryBtn: document.getElementById("refreshHistoryBtn"),
  saveEditBtn: document.getElementById("saveEditBtn"),
  exitEditBtn: document.getElementById("exitEditBtn"),
  toast: document.getElementById("toast"),
};

const state = {
  task: null,
  slotNames: SLOT_NAMES.slice(),
  slotDecisions: new Map(),
  activeSlot: "p1",
  history: [],
  editing: false,
  editingAnnotationId: "",
  lastAssignedTask: null,
};

function annotatorId() {
  return refs.annotatorId.value.trim() || "annotator_demo";
}

function showToast(message, isError = false) {
  refs.toast.textContent = message;
  refs.toast.hidden = false;
  refs.toast.classList.toggle("error", Boolean(isError));
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => {
    refs.toast.hidden = true;
  }, 2400);
}

function buildDefaultDecisions() {
  const decisions = new Map();
  state.slotNames.forEach((slot) => {
    decisions.set(slot, { slot, decision_type: "pending", ai_track_id: "", selection_source: "" });
  });
  return decisions;
}

function applyRecommendations(recommendations = []) {
  recommendations.forEach((item) => {
    if (!item || !state.slotDecisions.has(item.slot)) return;
    state.slotDecisions.set(item.slot, {
      slot: item.slot,
      decision_type: "ai_match",
      ai_track_id: String(item.ai_track_id || ""),
      selection_source: "recommended_confirmed",
    });
  });
}

function activeDecision() {
  return state.slotDecisions.get(state.activeSlot) || {
    slot: state.activeSlot,
    decision_type: "pending",
    ai_track_id: "",
    selection_source: "",
  };
}

function decisionSummary(decision) {
  if (!decision || decision.decision_type === "pending") return "未设置";
  if (decision.decision_type === "ai_match") {
    const tail = decision.selection_source === "recommended_confirmed" ? "推荐" : "人选";
    return `AI ${decision.ai_track_id} · ${tail}`;
  }
  if (decision.decision_type === "absent") return "不存在";
  return "AI错/漏";
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "request failed");
  }
  return payload;
}

function setTaskFromPayload(payload, { rememberAssignment = true } = {}) {
  state.task = payload;
  state.slotNames = payload.slot_names || SLOT_NAMES.slice();
  if (!state.slotNames.includes(state.activeSlot)) {
    state.activeSlot = state.slotNames[0] || "p1";
  }
  state.slotDecisions = buildDefaultDecisions();
  applyRecommendations(payload.frame?.recommendations || []);
  if (rememberAssignment) {
    state.lastAssignedTask = payload;
  }
  renderTask();
}

async function loadNextSegment() {
  const payload = await fetchJson(`/api/next_segment?annotator_id=${encodeURIComponent(annotatorId())}`);
  state.editing = false;
  state.editingAnnotationId = "";
  refs.saveEditBtn.hidden = true;
  refs.exitEditBtn.hidden = true;
  refs.submitBtn.disabled = false;
  setTaskFromPayload(payload, { rememberAssignment: true });
}

function renderTask() {
  if (!state.task) return;
  refs.videoStem.textContent = state.task.segment.video_stem;
  refs.segmentId.textContent = state.task.segment.segment_id;
  refs.segmentType.textContent = state.task.segment.segment_type;
  refs.frameIndex.textContent = String(state.task.frame.frame_index);
  refs.frameMeta.textContent = `timestamp ${state.task.frame.timestamp_ms}ms`;
  refs.frameImage.onload = () => renderAiOverlay();
  refs.frameImage.src = state.task.frame.image_url;
  renderAiLegend();
  renderSlotTabs();
  syncActiveSlotUI();
}

function renderAiLegend() {
  refs.aiLegend.innerHTML = "";
  (state.task?.frame?.ai_boxes || []).forEach((box) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "ai-chip";
    chip.textContent = legendLabelForTrackId(box.track_id);
    chip.addEventListener("click", () => applyAiTrackToSlot(state.activeSlot, box.track_id));
    refs.aiLegend.appendChild(chip);
  });
}

function assignedSlotByTrackId(trackId) {
  const target = String(trackId);
  for (const slot of state.slotNames) {
    const decision = state.slotDecisions.get(slot);
    if (decision?.decision_type === "ai_match" && decision.ai_track_id === target) {
      return slot;
    }
  }
  return "";
}

function labelForTrackId(trackId) {
  const assignedSlot = assignedSlotByTrackId(trackId);
  if (assignedSlot) {
    return `tid:${trackId} -> pid:${assignedSlot}`;
  }
  return `tid:${trackId}`;
}

function overlayLabelForTrackId(trackId) {
  const assignedSlot = assignedSlotByTrackId(trackId);
  if (assignedSlot) {
    return `t${trackId}:p${assignedSlot.slice(1)}`;
  }
  return `t${trackId}`;
}

function legendLabelForTrackId(trackId) {
  const assignedSlot = assignedSlotByTrackId(trackId);
  if (assignedSlot) {
    return `track ${trackId} (${assignedSlot})`;
  }
  return `track ${trackId}`;
}

function renderAiOverlay() {
  refs.aiOverlay.innerHTML = "";
  if (!state.task) return;
  const image = refs.frameImage;
  if (!image.naturalWidth || !image.naturalHeight) return;
  const scaleX = image.clientWidth / image.naturalWidth;
  const scaleY = image.clientHeight / image.naturalHeight;
  const current = activeDecision();
  state.task.frame.ai_boxes.forEach((box) => {
    const node = document.createElement("button");
    node.type = "button";
    node.className = "ai-box";
    if (current.decision_type === "ai_match" && current.ai_track_id === String(box.track_id)) {
      node.classList.add("active");
    }
    if (assignedSlotByTrackId(box.track_id)) {
      node.classList.add("mapped");
    }
    node.style.left = `${box.bbox_x * scaleX}px`;
    node.style.top = `${box.bbox_y * scaleY}px`;
    node.style.width = `${box.bbox_w * scaleX}px`;
    node.style.height = `${box.bbox_h * scaleY}px`;
    node.innerHTML = `<span>${overlayLabelForTrackId(box.track_id)}</span>`;
    node.addEventListener("click", () => applyAiTrackToSlot(state.activeSlot, box.track_id));
    refs.aiOverlay.appendChild(node);
  });
}

function renderSlotTabs() {
  refs.slotTabs.innerHTML = "";
  state.slotNames.forEach((slot) => {
    const decision = state.slotDecisions.get(slot);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "slot-tab";
    if (slot === state.activeSlot) btn.classList.add("active");
    btn.innerHTML = `
      <span class="slot-tab-label">${slot.toUpperCase()}</span>
      <span class="slot-tab-source">${decisionSummary(decision)}</span>
    `;
    btn.addEventListener("click", () => {
      state.activeSlot = slot;
      renderSlotTabs();
      syncActiveSlotUI();
      renderAiOverlay();
    });
    refs.slotTabs.appendChild(btn);
  });
}

function renderAiButtons() {
  refs.activeAiButtons.innerHTML = "";
  const current = activeDecision();
  const boxes = state.task?.frame?.ai_boxes || [];
  if (boxes.length === 0) {
    const empty = document.createElement("span");
    empty.className = "empty-note";
    empty.textContent = "该帧无 AI 框";
    refs.activeAiButtons.appendChild(empty);
    return;
  }
  boxes.forEach((box) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "ai-track-btn";
    if (current.decision_type === "ai_match" && current.ai_track_id === String(box.track_id)) {
      btn.classList.add("active");
    }
    btn.textContent = legendLabelForTrackId(box.track_id);
    btn.addEventListener("click", () => applyAiTrackToSlot(state.activeSlot, box.track_id));
    refs.activeAiButtons.appendChild(btn);
  });
}

function syncActiveSlotUI() {
  const decision = activeDecision();
  refs.activeSlotTitle.textContent = state.activeSlot.toUpperCase();
  refs.activeSlotSummary.textContent = decisionSummary(decision);
  refs.activeAbsentBtn.classList.toggle("active", decision.decision_type === "absent");
  refs.activeNeedsManualBtn.classList.toggle("active", decision.decision_type === "needs_manual");
  renderAiButtons();
}

function setDecision(slot, decisionType, aiTrackId = "") {
  let selectionSource = "";
  if (decisionType === "ai_match") {
    const recommendation = (state.task?.frame?.recommendations || []).find((item) => item.slot === slot);
    selectionSource =
      recommendation && String(recommendation.ai_track_id) === String(aiTrackId)
        ? "recommended_confirmed"
        : "manual_selected";
  } else if (decisionType === "absent") {
    selectionSource = "absent";
  } else if (decisionType === "needs_manual") {
    selectionSource = "needs_manual";
  }
  state.slotDecisions.set(slot, {
    slot,
    decision_type: decisionType,
    ai_track_id: aiTrackId,
    selection_source: selectionSource,
  });
  renderSlotTabs();
  syncActiveSlotUI();
  renderAiOverlay();
  renderAiLegend();
}

function applyAiTrackToSlot(slot, trackId) {
  setDecision(slot, "ai_match", String(trackId));
}

function markRemainingSlotsAbsent() {
  state.slotNames.forEach((slot) => {
    const decision = state.slotDecisions.get(slot);
    if (!decision || decision.decision_type === "pending") {
      state.slotDecisions.set(slot, {
        slot,
        decision_type: "absent",
        ai_track_id: "",
        selection_source: "absent",
      });
    }
  });
  renderSlotTabs();
  syncActiveSlotUI();
  renderAiOverlay();
  renderAiLegend();
  showToast("其余未分配槽位已标为不存在");
}

function buildSubmitPayload() {
  if (!state.task) {
    throw new Error("当前没有任务");
  }
  const slot_decisions = state.slotNames.map((slot) => state.slotDecisions.get(slot));
  const pending = slot_decisions.find((item) => !item || item.decision_type === "pending");
  if (pending) {
    throw new Error(`${pending.slot.toUpperCase()} 还没设置`);
  }
  return {
    annotator_id: annotatorId(),
    segment_id: state.task.segment.segment_id,
    video_stem: state.task.segment.video_stem,
    frame_index: state.task.frame.frame_index,
    slot_decisions: slot_decisions.filter((item) => ALLOWED_DECISIONS.includes(item.decision_type)),
  };
}

async function submitCurrent() {
  const payload = buildSubmitPayload();
  await fetchJson("/api/submit_segment", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  showToast(`已提交 ${payload.segment_id}`);
  await loadHistory({ silent: true });
  await loadNextSegment();
}

function renderHistory() {
  refs.historyList.innerHTML = "";
  if (!state.history.length) {
    const empty = document.createElement("div");
    empty.className = "history-empty";
    empty.textContent = "暂无记录";
    refs.historyList.appendChild(empty);
    return;
  }
  state.history.forEach((item) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "history-item";
    if (item.annotation_id === state.editingAnnotationId) row.classList.add("active");
    row.innerHTML = `
      <div class="time">${item.submitted_at.replace("T", " ").slice(0, 19)}</div>
      <div class="meta">${item.video_stem} #${item.frame_index}</div>
      <div class="summary">${item.slots_summary}</div>
    `;
    row.addEventListener("click", () => loadAnnotationDetail(item.annotation_id));
    refs.historyList.appendChild(row);
  });
}

async function loadHistory({ silent = false } = {}) {
  try {
    const payload = await fetchJson(`/api/my_annotations?annotator_id=${encodeURIComponent(annotatorId())}`);
    state.history = payload.annotations || [];
    renderHistory();
    if (!silent) showToast("已刷新历史记录");
  } catch (error) {
    showToast(error.message, true);
  }
}

function applySlotDecisions(slotDecisions) {
  state.slotDecisions = buildDefaultDecisions();
  (slotDecisions || []).forEach((item) => {
    if (!item || !state.slotDecisions.has(item.slot)) return;
    state.slotDecisions.set(item.slot, {
      slot: item.slot,
      decision_type: item.decision_type,
      ai_track_id: String(item.ai_track_id || ""),
      selection_source: String(item.selection_source || ""),
    });
  });
  renderSlotTabs();
  syncActiveSlotUI();
  renderAiOverlay();
  renderAiLegend();
}

function enterEditMode(annotationId) {
  state.editing = true;
  state.editingAnnotationId = annotationId;
  refs.saveEditBtn.hidden = false;
  refs.exitEditBtn.hidden = false;
  refs.submitBtn.disabled = true;
}

function exitEditMode() {
  state.editing = false;
  state.editingAnnotationId = "";
  refs.saveEditBtn.hidden = true;
  refs.exitEditBtn.hidden = true;
  refs.submitBtn.disabled = false;
  if (state.lastAssignedTask) {
    setTaskFromPayload(state.lastAssignedTask, { rememberAssignment: true });
  }
  renderHistory();
}

async function loadAnnotationDetail(annotationId) {
  try {
    const payload = await fetchJson(
      `/api/annotation_detail?annotation_id=${encodeURIComponent(annotationId)}&annotator_id=${encodeURIComponent(annotatorId())}`
    );
    enterEditMode(annotationId);
    setTaskFromPayload(payload, { rememberAssignment: false });
    applySlotDecisions(payload.annotation.slot_decisions || []);
    renderHistory();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function saveEdit() {
  if (!state.editing || !state.editingAnnotationId || !state.task) return;
  try {
    const payload = buildSubmitPayload();
    payload.annotation_id = state.editingAnnotationId;
    await fetchJson("/api/update_annotation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    await loadHistory({ silent: true });
    showToast("修改已保存");
  } catch (error) {
    showToast(error.message, true);
  }
}

function setHistoryToggle(collapsed) {
  refs.historyToggleBtn.textContent = collapsed ? "⟩" : "⟨";
}

function initHistoryDock() {
  const collapsed = localStorage.getItem(HISTORY_COLLAPSED_KEY) === "1";
  refs.historyDock.classList.toggle("collapsed", collapsed);
  setHistoryToggle(collapsed);
}

function toggleHistoryDock() {
  const collapsed = !refs.historyDock.classList.contains("collapsed");
  refs.historyDock.classList.toggle("collapsed", collapsed);
  localStorage.setItem(HISTORY_COLLAPSED_KEY, collapsed ? "1" : "0");
  setHistoryToggle(collapsed);
}

function initEvents() {
  refs.annotatorId.value = localStorage.getItem(ANNOTATOR_STORAGE_KEY) || "annotator_demo";
  refs.annotatorId.addEventListener("change", () => {
    localStorage.setItem(ANNOTATOR_STORAGE_KEY, annotatorId());
    loadHistory({ silent: true });
  });
  refs.nextBtn.addEventListener("click", () => {
    loadNextSegment().catch((error) => showToast(error.message, true));
  });
  refs.submitBtn.addEventListener("click", () => {
    submitCurrent().catch((error) => showToast(error.message, true));
  });
  refs.activeAbsentBtn.addEventListener("click", () => setDecision(state.activeSlot, "absent"));
  refs.activeNeedsManualBtn.addEventListener("click", () => setDecision(state.activeSlot, "needs_manual"));
  refs.markRemainingAbsentBtn.addEventListener("click", markRemainingSlotsAbsent);
  refs.refreshHistoryBtn.addEventListener("click", () => loadHistory());
  refs.saveEditBtn.addEventListener("click", () => saveEdit());
  refs.exitEditBtn.addEventListener("click", exitEditMode);
  refs.historyToggleBtn.addEventListener("click", toggleHistoryDock);
}

function init() {
  initHistoryDock();
  initEvents();
  loadHistory({ silent: true });
  loadNextSegment().catch((error) => showToast(error.message, true));
}

window.addEventListener("DOMContentLoaded", init);
