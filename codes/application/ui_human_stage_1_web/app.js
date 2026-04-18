const SLOT_NAMES = ["p1", "p2", "p3", "p4", "p5", "p6", "p7"];
const ALLOWED_DECISIONS = ["ai_match", "absent", "needs_manual"];

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
  slotList: document.getElementById("slotList"),
  toast: document.getElementById("toast"),
};

const state = {
  task: null,
  slotDecisions: new Map(),
};

function showToast(message) {
  refs.toast.textContent = message;
  refs.toast.hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => {
    refs.toast.hidden = true;
  }, 2400);
}

function buildDefaultDecisions() {
  const decisions = new Map();
  SLOT_NAMES.forEach((slot) => {
    decisions.set(slot, { slot, decision_type: "absent", ai_track_id: "" });
  });
  return decisions;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "request failed");
  }
  return payload;
}

async function loadNextSegment() {
  const annotatorId = refs.annotatorId.value.trim() || "annotator_demo";
  const payload = await fetchJson(`/api/next_segment?annotator_id=${encodeURIComponent(annotatorId)}`);
  state.task = payload;
  state.slotDecisions = buildDefaultDecisions();
  renderTask();
}

function renderTask() {
  const task = state.task;
  if (!task) {
    return;
  }
  refs.videoStem.textContent = task.segment.video_stem;
  refs.segmentId.textContent = task.segment.segment_id;
  refs.segmentType.textContent = task.segment.segment_type;
  refs.frameIndex.textContent = String(task.frame.frame_index);
  refs.frameMeta.textContent = `timestamp ${task.frame.timestamp_ms}ms`;
  refs.frameImage.src = task.frame.image_url;
  refs.frameImage.onload = renderAiOverlay;
  renderAiLegend();
  renderSlots();
}

function renderAiLegend() {
  const task = state.task;
  refs.aiLegend.innerHTML = "";
  task.frame.ai_boxes.forEach((box) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "ai-chip";
    chip.textContent = `track ${box.track_id}`;
    chip.addEventListener("click", () => applyAiTrackToFirstAvailable(box.track_id));
    refs.aiLegend.appendChild(chip);
  });
}

function renderAiOverlay() {
  const task = state.task;
  refs.aiOverlay.innerHTML = "";
  const image = refs.frameImage;
  const scaleX = image.clientWidth / image.naturalWidth;
  const scaleY = image.clientHeight / image.naturalHeight;
  task.frame.ai_boxes.forEach((box) => {
    const node = document.createElement("div");
    node.className = "ai-box";
    node.style.left = `${box.bbox_x * scaleX}px`;
    node.style.top = `${box.bbox_y * scaleY}px`;
    node.style.width = `${box.bbox_w * scaleX}px`;
    node.style.height = `${box.bbox_h * scaleY}px`;
    node.innerHTML = `<span>track ${box.track_id}</span>`;
    node.addEventListener("click", () => applyAiTrackToFirstAvailable(box.track_id));
    refs.aiOverlay.appendChild(node);
  });
}

function applyAiTrackToFirstAvailable(trackId) {
  for (const slot of SLOT_NAMES) {
    const decision = state.slotDecisions.get(slot);
    if (decision.decision_type !== "ai_match") {
      state.slotDecisions.set(slot, {
        slot,
        decision_type: "ai_match",
        ai_track_id: String(trackId),
      });
      renderSlots();
      return;
    }
  }
  showToast("所有槽位都已经使用 ai_match 了");
}

function setDecision(slot, decisionType, aiTrackId = "") {
  state.slotDecisions.set(slot, {
    slot,
    decision_type: decisionType,
    ai_track_id: aiTrackId,
  });
  renderSlots();
}

function renderSlots() {
  const task = state.task;
  refs.slotList.innerHTML = "";
  SLOT_NAMES.forEach((slot) => {
    const decision = state.slotDecisions.get(slot);
    const card = document.createElement("article");
    card.className = "slot-card";

    const header = document.createElement("div");
    header.className = "slot-head";
    header.innerHTML = `<h3>${slot.toUpperCase()}</h3><span>${decision.decision_type}</span>`;

    const aiRow = document.createElement("div");
    aiRow.className = "slot-row";
    const aiLabel = document.createElement("span");
    aiLabel.textContent = "ai_match";
    const aiSelect = document.createElement("select");
    aiSelect.dataset.action = "ai_match";
    const emptyOption = document.createElement("option");
    emptyOption.value = "";
    emptyOption.textContent = "选择 AI 框";
    aiSelect.appendChild(emptyOption);
    task.frame.ai_boxes.forEach((box) => {
      const option = document.createElement("option");
      option.value = String(box.track_id);
      option.textContent = `track ${box.track_id}`;
      if (decision.decision_type === "ai_match" && decision.ai_track_id === String(box.track_id)) {
        option.selected = true;
      }
      aiSelect.appendChild(option);
    });
    aiSelect.addEventListener("change", (event) => {
      const value = event.target.value;
      if (value) {
        setDecision(slot, "ai_match", value);
      }
    });
    aiRow.append(aiLabel, aiSelect);

    const actions = document.createElement("div");
    actions.className = "slot-actions";
    const absentBtn = document.createElement("button");
    absentBtn.type = "button";
    absentBtn.className = `decision-btn${decision.decision_type === "absent" ? " active" : ""}`;
    absentBtn.dataset.action = "absent";
    absentBtn.textContent = "absent";
    absentBtn.addEventListener("click", () => setDecision(slot, "absent"));

    const manualBtn = document.createElement("button");
    manualBtn.type = "button";
    manualBtn.className = `decision-btn${decision.decision_type === "needs_manual" ? " active" : ""}`;
    manualBtn.dataset.action = "needs_manual";
    manualBtn.textContent = "needs_manual";
    manualBtn.addEventListener("click", () => setDecision(slot, "needs_manual"));

    actions.append(absentBtn, manualBtn);

    card.append(header, aiRow, actions);
    refs.slotList.appendChild(card);
  });
}

function buildSubmitPayload() {
  if (!state.task) {
    throw new Error("当前没有任务");
  }
  const slot_decisions = SLOT_NAMES.map((slot) => state.slotDecisions.get(slot));
  return {
    annotator_id: refs.annotatorId.value.trim() || "annotator_demo",
    segment_id: state.task.segment.segment_id,
    video_stem: state.task.segment.video_stem,
    frame_index: state.task.frame.frame_index,
    slot_decisions,
  };
}

async function submitCurrent() {
  const payload = buildSubmitPayload();
  const response = await fetchJson("/api/submit_segment", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  showToast(`已提交 ${response.segment_id}`);
  await loadNextSegment();
}

refs.nextBtn.addEventListener("click", () => {
  loadNextSegment().catch((error) => showToast(error.message));
});

refs.submitBtn.addEventListener("click", () => {
  submitCurrent().catch((error) => showToast(error.message));
});

loadNextSegment().catch((error) => showToast(error.message));
