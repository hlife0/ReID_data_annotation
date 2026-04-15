const I18N = {
  zh: {
    page_title: "多人框段标注",
    page_subtitle: "稳定段与非简单单帧标注流程。",
    annotator_id: "标注员ID",
    next_segment: "下一段",
    skip_frame: "跳过当前段",
    submit_next: "提交并下一帧",
    submit_next_segment: "提交并下一段",
    video: "视频",
    frame: "帧号",
    timestamp_ms: "时间戳(ms)",
    annotation_count: "标注次数",
    segment_type: "段类型",
    segment_range: "段范围 #{start} - #{end}",
    segment_tracks: "轨迹 {tracks}",
    segment_stable: "稳定段",
    segment_non_simple_single_frame: "非简单单帧",
    chip_ai: "AI框（虚线 + track_id）",
    chip_user: "用户框（P1-P7）",
    source: "来源",
    apply_ai_box: "应用AI框",
    manual_draw: "手动画框",
    draw_new_box: "绘制新框",
    mark_absent: "不存在",
    mark_occluded: "遮挡",
    mark_outside: "出画",
    src_not_set: "未设置",
    src_ai: "AI",
    src_manual_draw: "手动画框",
    src_manual_param: "参数修改",
    src_absent: "不存在",
    src_occluded: "遮挡",
    src_outside: "出画",
    no_ai_box: "该帧无AI框",
    hint_start: "先加载一帧开始标注。",
    hint_loading: "正在加载帧图...",
    hint_ready: "准备就绪",
    hint_drag_resize: "拖动可移动框，拖拽控制点可缩放，或点击“绘制新框”手动画框。",
    hint_load_fail: "帧图加载失败。",
    hint_drawing: "正在绘制 {slot}，松开鼠标完成。",
    hint_editing: "正在编辑 {slot}",
    hint_used_ai: "{slot} 已应用 AI track {track}",
    hint_click_drag_draw: "请在画布上按住拖拽绘制 {slot}",
    hint_marked_absent: "{slot} 已标记为不存在",
    toast_frame_load_failed: "帧图加载失败",
    toast_loaded_segment: "已加载下一段",
    toast_loaded_next: "已加载下一帧",
    toast_no_frame: "当前没有可操作帧",
    toast_ai_not_found: "未找到该AI轨迹",
    toast_submitted: "已提交 {video}#{frame}，该帧累计 {count} 次",
    toast_recommend_applied: "已应用历史推荐",
    segment_none: "当前未加载标注段",
    err_bbox_missing: "{slot} 框未设置",
    err_bbox_wh: "{slot} 框必须满足 w>0 且 h>0",
    err_source_invalid: "{slot} 来源无效",
    annotator_modal_title: "先填写标注员ID",
    annotator_modal_desc: "未检测到有效的标注员ID。建议现在填写；关闭后将继续使用默认值 {default_id}。",
    annotator_modal_submit: "提交",
    annotator_modal_close: "关闭",
    annotator_modal_input_placeholder: "请输入你的标注员ID",
    annotator_modal_err_empty: "请输入非空标注员ID，或点击右上角关闭继续使用默认值。",
    toast_annotator_saved: "已设置标注员ID：{id}",
    history_title: "我的标注记录",
    history_hint: "点击条目进入编辑模式",
    history_refresh: "刷新",
    history_exit_edit: "退出编辑",
    history_save_edit: "保存修改",
    history_expand: "展开记录",
    history_collapse: "收起记录",
    history_empty: "暂无记录",
    toast_history_loaded: "已刷新标注记录",
    toast_edit_saved: "修改已保存",
    progress_label: "进度",
    slots_title: "标注槽位",
    lang_toggle: "EN",
  },
  en: {
    page_title: "Multi-Person Segment Labeling",
    page_subtitle: "Stable-segment and non-simple-frame labeling workflow.",
    annotator_id: "Annotator ID",
    next_segment: "Next Segment",
    skip_frame: "Skip This Segment",
    submit_next: "Submit & Next Frame",
    submit_next_segment: "Submit & Next Segment",
    video: "Video",
    frame: "Frame",
    timestamp_ms: "Timestamp (ms)",
    annotation_count: "Annotation Count",
    segment_type: "Segment Type",
    segment_range: "Range #{start} - #{end}",
    segment_tracks: "Tracks {tracks}",
    segment_stable: "Stable Segment",
    segment_non_simple_single_frame: "Non-Simple Single Frame",
    chip_ai: "AI box (dashed + track_id)",
    chip_user: "User boxes (P1-P7)",
    source: "Source",
    apply_ai_box: "Apply AI box",
    manual_draw: "Manual draw",
    draw_new_box: "Draw New Box",
    mark_absent: "Mark Missing",
    mark_occluded: "Occluded",
    mark_outside: "Outside",
    src_not_set: "not_set",
    src_ai: "ai",
    src_manual_draw: "manual_draw",
    src_manual_param: "manual_param",
    src_absent: "absent",
    src_occluded: "occluded",
    src_outside: "outside",
    no_ai_box: "No AI box in this frame",
    hint_start: "Load a frame to start.",
    hint_loading: "Loading frame image...",
    hint_ready: "Ready",
    hint_drag_resize: "Drag box to move, drag handles to resize, or click Draw New Box.",
    hint_load_fail: "Failed to load frame image.",
    hint_drawing: "Drawing {slot}... release mouse to finish",
    hint_editing: "Editing {slot}",
    hint_used_ai: "{slot} used AI track {track}",
    hint_click_drag_draw: "Click and drag on canvas to draw {slot}",
    hint_marked_absent: "{slot} marked as missing",
    toast_frame_load_failed: "Failed to load frame image",
    toast_loaded_segment: "Loaded next segment",
    toast_loaded_next: "Loaded next frame",
    toast_no_frame: "No frame loaded",
    toast_ai_not_found: "AI track not found",
    toast_submitted: "Submitted {video}#{frame} -> count {count}",
    toast_recommend_applied: "Applied historical recommendations",
    segment_none: "No segment loaded",
    err_bbox_missing: "{slot} bbox is missing",
    err_bbox_wh: "{slot} bbox must have w>0 and h>0",
    err_source_invalid: "{slot} source is invalid",
    annotator_modal_title: "Set Annotator ID First",
    annotator_modal_desc: "No valid annotator ID was detected. Please fill it now, or close to continue with default value {default_id}.",
    annotator_modal_submit: "Submit",
    annotator_modal_close: "Close",
    annotator_modal_input_placeholder: "Enter annotator ID",
    annotator_modal_err_empty: "Please enter a non-empty annotator ID, or close to continue with default.",
    toast_annotator_saved: "Annotator ID set: {id}",
    history_title: "My Annotations",
    history_hint: "Click an item to edit",
    history_refresh: "Refresh",
    history_exit_edit: "Exit Edit",
    history_save_edit: "Save Changes",
    history_expand: "Show History",
    history_collapse: "Hide History",
    history_empty: "No records",
    toast_history_loaded: "History refreshed",
    toast_edit_saved: "Changes saved",
    progress_label: "Progress",
    slots_title: "Slots",
    lang_toggle: "中",
  },
};

const SLOT_ORDER = ["p1", "p2", "p3", "p4", "p5", "p6", "p7"];
const SLOT_COLORS = ["#1d9a58", "#54606e", "#b05a13", "#7a43b6", "#c73752", "#0e8e9d", "#7d8d25"];
const SLOT_META = Object.fromEntries(
  SLOT_ORDER.map((slot, index) => [slot, { label: slot.toUpperCase(), color: SLOT_COLORS[index] }])
);

const HANDLE_SIZE = 8;
const MIN_BOX_SIZE = 2;
const DEFAULT_ANNOTATOR_ID = "annotator_demo";
const ANNOTATOR_STORAGE_KEY = "ui_review_annotator_id";
const PREFETCH_WINDOW = 5;
const IMAGE_CACHE_LIMIT = 12;

const state = {
  frame: null,
  image: null,
  aiBoxes: [],
  aiByTrack: new Map(),
  slotNames: SLOT_ORDER.slice(),
  slots: {},
  activeSlot: "p1",
  drawSlot: null,
  action: null,
  syncingInputs: false,
  lang: "zh",
  hintKey: "hint_start",
  hintVars: {},
  initialFrameRequested: false,
  imageRequestId: 0,
  imageCache: new Map(),
  inflightImageFetches: new Map(),
  history: [],
  editing: false,
  editingAnnotationId: "",
  lastAssignmentFrame: null,
  currentSegment: null,
  dispatchMode: "segment",
  progressTarget: 4000,
};

const refs = {
  langToggleBtn: document.getElementById("langToggleBtn"),
  annotatorId: document.getElementById("annotatorId"),
  nextSegmentBtn: document.getElementById("nextSegmentBtn"),
  nextFrameBtn: document.getElementById("nextFrameBtn"),
  submitBtn: document.getElementById("submitBtn"),
  videoStem: document.getElementById("videoStem"),
  frameIndex: document.getElementById("frameIndex"),
  timestampMs: document.getElementById("timestampMs"),
  annoCount: document.getElementById("annoCount"),
  canvas: document.getElementById("frameCanvas"),
  canvasHint: document.getElementById("canvasHint"),
  toast: document.getElementById("toast"),
  slotTabs: document.getElementById("slotTabs"),
  activeSlotTitle: document.getElementById("activeSlotTitle"),
  activeSource: document.getElementById("activeSource"),
  activeAiButtons: document.getElementById("activeAiButtons"),
  activeDrawBtn: document.getElementById("activeDrawBtn"),
  activeAbsentBtn: document.getElementById("activeAbsentBtn"),
  activeOccludedBtn: document.getElementById("activeOccludedBtn"),
  activeOutsideBtn: document.getElementById("activeOutsideBtn"),
  activeX: document.getElementById("activeX"),
  activeY: document.getElementById("activeY"),
  activeW: document.getElementById("activeW"),
  activeH: document.getElementById("activeH"),
  annotatorModal: document.getElementById("annotatorModal"),
  annotatorModalCloseBtn: document.getElementById("annotatorModalCloseBtn"),
  annotatorModalInput: document.getElementById("annotatorModalInput"),
  annotatorModalSubmitBtn: document.getElementById("annotatorModalSubmitBtn"),
  annotatorModalHint: document.getElementById("annotatorModalHint"),
  historyList: document.getElementById("historyList"),
  refreshHistoryBtn: document.getElementById("refreshHistoryBtn"),
  saveEditBtn: document.getElementById("saveEditBtn"),
  exitEditBtn: document.getElementById("exitEditBtn"),
  historyDock: document.getElementById("historyDock"),
  historyToggleBtn: document.getElementById("historyToggleBtn"),
  progressFill: document.getElementById("progressFill"),
  progressText: document.getElementById("progressText"),
  segmentSummary: document.getElementById("segmentSummary"),
  segmentBadge: document.getElementById("segmentBadge"),
  segmentIdText: document.getElementById("segmentIdText"),
  segmentRangeText: document.getElementById("segmentRangeText"),
  segmentTrackText: document.getElementById("segmentTrackText"),
};

const ctx = refs.canvas.getContext("2d");

function t(key, vars = {}) {
  const bundle = I18N[state.lang] || I18N.zh;
  let out = bundle[key] || I18N.en[key] || key;
  for (const [k, v] of Object.entries(vars)) {
    out = out.replaceAll(`{${k}}`, String(v));
  }
  return out;
}

function applyLanguage() {
  document.documentElement.lang = state.lang === "zh" ? "zh-CN" : "en";
  document.title = t("page_title");

  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (key) {
      el.textContent = t(key);
    }
  });

  refs.langToggleBtn.textContent = t("lang_toggle");
  refs.annotatorModalCloseBtn.title = t("annotator_modal_close");
  refs.annotatorModalCloseBtn.setAttribute("aria-label", t("annotator_modal_close"));
  refs.annotatorModalInput.placeholder = t("annotator_modal_input_placeholder");
  if (refs.historyDock) {
    setHistoryToggle(refs.historyDock.classList.contains("collapsed"));
  }
  const desc = document.getElementById("annotatorModalDesc");
  if (desc) {
    desc.textContent = t("annotator_modal_desc", { default_id: DEFAULT_ANNOTATOR_ID });
  }
  syncActiveSlotUI();
  renderSlotTabs();
  renderAiButtons();
  renderCurrentHint();
  renderSegmentSummary();
  updateActionLabels();
  updateProgress();
}

function toggleLanguage() {
  state.lang = state.lang === "zh" ? "en" : "zh";
  localStorage.setItem("ui_review_lang", state.lang);
  applyLanguage();
}

function annotatorId() {
  const value = refs.annotatorId.value.trim();
  return value || "annotator_unknown";
}

function getStoredAnnotatorId() {
  return (localStorage.getItem(ANNOTATOR_STORAGE_KEY) || "").trim();
}

function shouldPromptAnnotatorModal(storedAnnotatorId) {
  return !storedAnnotatorId || storedAnnotatorId === DEFAULT_ANNOTATOR_ID;
}

function requestInitialSegmentOnce() {
  if (state.initialFrameRequested) {
    return;
  }
  state.initialFrameRequested = true;
  requestNextSegment();
}

function closeAnnotatorModalAndContinue() {
  refs.annotatorModal.hidden = true;
  refs.annotatorModalHint.textContent = "";
  requestInitialSegmentOnce();
}

function submitAnnotatorModal() {
  const value = refs.annotatorModalInput.value.trim();
  if (!value) {
    refs.annotatorModalHint.textContent = t("annotator_modal_err_empty");
    refs.annotatorModalInput.focus();
    return;
  }
  refs.annotatorId.value = value;
  localStorage.setItem(ANNOTATOR_STORAGE_KEY, value);
  closeAnnotatorModalAndContinue();
  showToastKey("toast_annotator_saved", { id: value });
}

function maybePromptAnnotatorModal() {
  const storedId = getStoredAnnotatorId();
  if (!shouldPromptAnnotatorModal(storedId)) {
    return false;
  }
  refs.annotatorModal.hidden = false;
  refs.annotatorModalHint.textContent = "";
  refs.annotatorModalInput.value = "";
  setTimeout(() => refs.annotatorModalInput.focus(), 0);
  return true;
}

function slotName(slot) {
  return SLOT_META[slot]?.label || slot.toUpperCase();
}

function sourceLabel(source) {
  if (source === "ai") return t("src_ai");
  if (source === "manual_draw") return t("src_manual_draw");
  if (source === "manual_param") return t("src_manual_param");
  if (source === "absent") return t("src_absent");
  if (source === "occluded") return t("src_occluded");
  if (source === "outside") return t("src_outside");
  return t("src_not_set");
}

function setHintByKey(key, vars = {}) {
  state.hintKey = key;
  state.hintVars = vars;
  renderCurrentHint();
}

function renderCurrentHint() {
  refs.canvasHint.textContent = t(state.hintKey, state.hintVars);
}

function updateActionLabels() {
  refs.submitBtn.textContent =
    state.dispatchMode === "segment" ? t("submit_next_segment") : t("submit_next");
  const stable = state.currentSegment?.segment_type === "stable_segment";
  if (refs.activeOccludedBtn) {
    refs.activeOccludedBtn.hidden = stable;
  }
  if (refs.activeOutsideBtn) {
    refs.activeOutsideBtn.hidden = stable;
  }
}

function showToast(text, isError = false) {
  refs.toast.textContent = text;
  refs.toast.style.background = isError
    ? "rgba(140, 29, 25, 0.92)"
    : "rgba(20, 35, 48, 0.92)";
  refs.toast.classList.add("show");
  setTimeout(() => refs.toast.classList.remove("show"), 1800);
}

function showToastKey(key, vars = {}, isError = false) {
  showToast(t(key, vars), isError);
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

function round3(num) {
  return Math.round(num * 1000) / 1000;
}

function frameCacheKey(videoStem, frameIndex) {
  return `${videoStem}::${frameIndex}`;
}

function touchCachedImage(key) {
  const cached = state.imageCache.get(key);
  if (!cached) {
    return null;
  }
  state.imageCache.delete(key);
  state.imageCache.set(key, cached);
  return cached;
}

function storeCachedImage(key, record) {
  const existing = state.imageCache.get(key);
  if (existing && existing.blobUrl && existing.blobUrl !== record.blobUrl) {
    URL.revokeObjectURL(existing.blobUrl);
  }
  if (state.imageCache.has(key)) {
    state.imageCache.delete(key);
  }
  state.imageCache.set(key, record);

  while (state.imageCache.size > IMAGE_CACHE_LIMIT) {
    const oldestKey = state.imageCache.keys().next().value;
    if (!oldestKey) {
      break;
    }
    const oldest = state.imageCache.get(oldestKey);
    state.imageCache.delete(oldestKey);
    if (oldest && oldest.blobUrl) {
      URL.revokeObjectURL(oldest.blobUrl);
    }
  }
}

async function prefetchFrameImage(frame) {
  if (!frame || !frame.image_url) {
    return null;
  }
  const key = frameCacheKey(frame.video_stem, frame.frame_index);
  const cached = touchCachedImage(key);
  if (cached) {
    return cached;
  }
  if (state.inflightImageFetches.has(key)) {
    return state.inflightImageFetches.get(key);
  }

  const promise = fetch(frame.image_url, { cache: "no-store" })
    .then((res) => {
      if (!res.ok) {
        throw new Error(`Prefetch failed (${res.status})`);
      }
      return res.blob();
    })
    .then((blob) => {
      const record = { blobUrl: URL.createObjectURL(blob), fetchedAt: Date.now() };
      storeCachedImage(key, record);
      return record;
    })
    .finally(() => {
      state.inflightImageFetches.delete(key);
    });

  state.inflightImageFetches.set(key, promise);
  return promise;
}

function schedulePrefetch(frames) {
  const candidates = Array.isArray(frames) ? frames.slice(0, PREFETCH_WINDOW) : [];
  for (const frame of candidates) {
    prefetchFrameImage(frame).catch(() => {});
  }
}

function cloneBbox(b) {
  return b ? { x: b.x, y: b.y, w: b.w, h: b.h } : null;
}

function clampBbox(bbox) {
  if (!state.image) {
    return bbox;
  }
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

function bboxValid(bbox) {
  return !!bbox && bbox.w > 0 && bbox.h > 0;
}

function setSlotBbox(slot, bbox, source, aiTrackId = "") {
  state.slots[slot].bbox = bbox ? clampBbox(bbox) : null;
  state.slots[slot].source = source;
  state.slots[slot].aiTrackId = aiTrackId;
  syncActiveSlotUI();
  renderSlotTabs();
  drawCanvas();
}

function sourceClass(source) {
  if (
    source === "ai" ||
    source === "manual_draw" ||
    source === "manual_param" ||
    source === "absent" ||
    source === "occluded" ||
    source === "outside"
  ) {
    return source;
  }
  return "";
}

function renderSlotTabs() {
  if (!refs.slotTabs) return;
  refs.slotTabs.innerHTML = "";
  for (const slot of state.slotNames) {
    const slotState = state.slots[slot];
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "slot-tab";
    if (slot === state.activeSlot) {
      btn.classList.add("active");
    }
    btn.style.setProperty("--slot-color", SLOT_META[slot].color);
    btn.innerHTML = `
      <span class="slot-tab-label">${slotName(slot)}</span>
      <span class="slot-tab-source">${sourceLabel(slotState.source)}</span>
    `;
    btn.addEventListener("click", () => {
      state.activeSlot = slot;
      syncActiveSlotUI();
      renderSlotTabs();
      drawCanvas();
    });
    refs.slotTabs.appendChild(btn);
  }
}

function syncActiveSlotUI() {
  const slot = state.activeSlot;
  const slotState = state.slots[slot];
  if (!slotState) return;
  const isAbsent = slotState.source === "absent";
  const inputs = [refs.activeX, refs.activeY, refs.activeW, refs.activeH];

  refs.activeSlotTitle.textContent = slotName(slot);
  refs.activeSlotTitle.style.color = SLOT_META[slot].color;

  state.syncingInputs = true;
  if (isAbsent) {
    inputs[0].value = "0";
    inputs[1].value = "0";
    inputs[2].value = "0";
    inputs[3].value = "0";
  } else if (slotState.bbox) {
    inputs[0].value = slotState.bbox.x;
    inputs[1].value = slotState.bbox.y;
    inputs[2].value = slotState.bbox.w;
    inputs[3].value = slotState.bbox.h;
  } else {
    inputs.forEach((el) => {
      el.value = "";
    });
  }
  state.syncingInputs = false;
  for (const el of inputs) {
    el.disabled = isAbsent;
  }

  refs.activeSource.textContent = sourceLabel(slotState.source);
  refs.activeSource.className = `source-badge ${sourceClass(slotState.source)}`;
  renderAiButtons();
}

function syncHeader() {
  if (!state.frame) {
    refs.videoStem.textContent = "-";
    refs.frameIndex.textContent = "-";
    refs.timestampMs.textContent = "-";
    refs.annoCount.textContent = "-";
    return;
  }
  refs.videoStem.textContent = state.frame.video_stem;
  refs.frameIndex.textContent = state.frame.frame_index;
  refs.timestampMs.textContent = state.frame.timestamp_ms;
  refs.annoCount.textContent = state.frame.annotation_count;
}

function segmentTypeLabel(segmentType) {
  if (segmentType === "stable_segment") return t("segment_stable");
  if (segmentType === "non_simple_single_frame") return t("segment_non_simple_single_frame");
  return segmentType || t("segment_none");
}

function renderSegmentSummary() {
  if (!refs.segmentSummary) return;
  const segment = state.currentSegment;
  if (!segment) {
    refs.segmentSummary.hidden = true;
    updateActionLabels();
    return;
  }
  refs.segmentSummary.hidden = false;
  refs.segmentBadge.textContent = segmentTypeLabel(segment.segment_type);
  refs.segmentBadge.className = `issue-badge ${segment.segment_type === "stable_segment" ? "green" : "red"}`;
  refs.segmentIdText.textContent = segment.segment_id || t("segment_none");
  refs.segmentRangeText.textContent = t("segment_range", {
    start: segment.start_frame,
    end: segment.end_frame,
  });
  const tracks = Array.isArray(segment.track_ids) && segment.track_ids.length
    ? segment.track_ids.join(", ")
    : "-";
  refs.segmentTrackText.textContent = t("segment_tracks", { tracks });
  updateActionLabels();
}

function renderIssueSummary() {
  if (!refs.issueSummary) return;
  const issue = state.currentIssue;
  if (!issue) {
    refs.issueSummary.hidden = true;
    renderTrajectoryCards();
    renderKeyframeList();
    updateActionLabels();
    return;
  }
  refs.issueSummary.hidden = false;
  refs.issueBadge.textContent = String(issue.severity || "issue").toUpperCase();
  refs.issueBadge.className = `issue-badge ${String(issue.severity || "").toLowerCase()}`;
  refs.issueIdText.textContent = issue.issue_id || t("issue_none");
  refs.issueRangeText.textContent = t("issue_range", {
    start: issue.start_frame,
    end: issue.end_frame,
  });
  const tracks = Array.isArray(issue.primary_track_ids) && issue.primary_track_ids.length
    ? issue.primary_track_ids.join(", ")
    : "-";
  refs.issueTrackText.textContent = t("issue_tracks", { tracks });
  if (refs.issuePrevFrameBtn) {
    refs.issuePrevFrameBtn.disabled = Number(state.frame?.frame_index) <= Number(issue.start_frame);
  }
  if (refs.issueNextFrameBtn) {
    refs.issueNextFrameBtn.disabled = Number(state.frame?.frame_index) >= Number(issue.end_frame);
  }
  refs.issueReasonList.innerHTML = "";
  const reasons = Array.isArray(issue.reason_codes) ? issue.reason_codes : [];
  for (const reason of reasons) {
    const pill = document.createElement("span");
    pill.className = "issue-reason-pill";
    pill.textContent = reason;
    refs.issueReasonList.appendChild(pill);
  }
  if (
    Number(issue.imu_count || 0) > 0
    && reasons.some((reason) => ["count_change", "track_boundary"].includes(reason))
  ) {
    const pill = document.createElement("span");
    pill.className = "issue-reason-pill";
    pill.textContent = t("imu_conflict_hint", { count: issue.imu_count });
    refs.issueReasonList.appendChild(pill);
  }
  updateActionLabels();
  renderTrajectoryCards();
  renderKeyframeList();
}

function renderIssueList() {
  if (!refs.issueListBody) return;
  refs.issueListBody.innerHTML = "";
  const issues = Array.isArray(state.issues) ? state.issues : [];
  if (issues.length === 0) {
    const empty = document.createElement("div");
    empty.className = "issue-list-item";
    empty.textContent = t("issue_none");
    refs.issueListBody.appendChild(empty);
    return;
  }

  for (const issue of issues) {
    const row = document.createElement("div");
    row.className = `issue-list-item ${String(issue.severity || "").toLowerCase()}`;
    if (state.currentIssue && issue.issue_id === state.currentIssue.issue_id) {
      row.classList.add("active");
    }
    const tracks = Array.isArray(issue.primary_track_ids) && issue.primary_track_ids.length
      ? issue.primary_track_ids.join(", ")
      : "-";
    row.innerHTML = `
      <div class="issue-list-item-top">
        <span>${issue.issue_id}</span>
        <span>${String(issue.severity || "").toUpperCase()}</span>
      </div>
      <div class="issue-list-item-meta">#${issue.start_frame} - #${issue.end_frame} | tracks ${tracks}</div>
    `;
    row.addEventListener("click", () => loadIssueDetail(issue.issue_id));
    refs.issueListBody.appendChild(row);
  }
}

function renderIssueTimeline() {
  if (!refs.issueTimeline) return;
  refs.issueTimeline.innerHTML = "";
  const issues = Array.isArray(state.issues) ? state.issues : [];
  if (issues.length === 0) {
    return;
  }
  const minFrame = Math.min(...issues.map((issue) => Number(issue.start_frame)));
  const maxFrame = Math.max(...issues.map((issue) => Number(issue.end_frame)));
  const span = Math.max(1, maxFrame - minFrame + 1);

  for (const issue of issues) {
    const start = Number(issue.start_frame);
    const end = Number(issue.end_frame);
    const left = ((start - minFrame) / span) * 100;
    const width = Math.max(1.2, ((end - start + 1) / span) * 100);
    const bar = document.createElement("button");
    bar.type = "button";
    bar.className = `issue-timeline-bar ${String(issue.severity || "").toLowerCase()}`;
    if (state.currentIssue && issue.issue_id === state.currentIssue.issue_id) {
      bar.classList.add("active");
    }
    bar.style.left = `${left}%`;
    bar.style.width = `${width}%`;
    bar.title = `${issue.issue_id} | #${issue.start_frame}-#${issue.end_frame}`;
    bar.addEventListener("click", () => loadIssueDetail(issue.issue_id));
    refs.issueTimeline.appendChild(bar);
  }
}

function issueTrackItems() {
  if (!state.currentIssue) {
    return [];
  }
  if (Array.isArray(state.currentIssue.issue_tracks) && state.currentIssue.issue_tracks.length) {
    return state.currentIssue.issue_tracks;
  }
  return (state.currentIssue.primary_track_ids || []).map((trackId) => ({
    track_id: trackId,
    visible_start_frame: state.currentIssue.start_frame,
    visible_end_frame: state.currentIssue.end_frame,
    min_score: 0,
    max_jump_distance: 0,
  }));
}

function sortIssueKeyframes() {
  state.issueKeyframes.sort((a, b) => a.frameIndex - b.frameIndex);
}

function findIssueKeyframe(frameIndex) {
  return state.issueKeyframes.find((item) => item.frameIndex === Number(frameIndex)) || null;
}

function upsertCurrentKeyframe(options = {}) {
  const { silent = false } = options;
  if (!state.currentIssue || !state.frame) {
    return false;
  }
  const entry = {
    frameIndex: Number(state.frame.frame_index),
    slots: cloneCurrentSlots(),
  };
  const existing = findIssueKeyframe(entry.frameIndex);
  if (existing) {
    existing.slots = entry.slots;
  } else {
    state.issueKeyframes.push(entry);
  }
  sortIssueKeyframes();
  renderKeyframeList();
  if (!silent) {
    showToastKey("toast_keyframe_saved", { frame: entry.frameIndex });
  }
  return true;
}

function removeKeyframeByFrame(frameIndex, options = {}) {
  const { silent = false } = options;
  const normalized = Number(frameIndex);
  const before = state.issueKeyframes.length;
  state.issueKeyframes = state.issueKeyframes.filter((item) => item.frameIndex !== normalized);
  renderKeyframeList();
  if (!silent && before !== state.issueKeyframes.length) {
    showToastKey("toast_keyframe_removed", { frame: normalized });
  }
}

function removeCurrentKeyframe() {
  if (!state.currentIssue || !state.frame) {
    return;
  }
  removeKeyframeByFrame(state.frame.frame_index);
}

function clearIssueKeyframes() {
  state.issueKeyframes = [];
  renderKeyframeList();
  showToastKey("toast_keyframes_cleared");
}

function renderKeyframeList() {
  if (!refs.keyframeList) return;
  refs.keyframeList.innerHTML = "";
  if (!state.currentIssue || state.issueKeyframes.length === 0) {
    const empty = document.createElement("div");
    empty.className = "keyframe-item";
    empty.textContent = t("keyframe_empty");
    refs.keyframeList.appendChild(empty);
    return;
  }
  for (const item of state.issueKeyframes) {
    const row = document.createElement("div");
    row.className = "keyframe-item";
    if (Number(state.frame?.frame_index) === item.frameIndex) {
      row.classList.add("active");
    }
    row.innerHTML = `
      <div class="keyframe-item-meta">
        <div class="keyframe-item-title">${t("keyframe_label", { frame: item.frameIndex })}</div>
        <div class="keyframe-item-subtitle">${t("keyframe_sources", {
          count: item.slots.filter((slot) => slot.source !== "not_set").length,
        })}</div>
      </div>
      <div class="keyframe-item-actions">
        <button type="button" class="btn subtle" data-action="jump">${t("track_jump")}</button>
        <button type="button" class="btn subtle" data-action="remove">${t("remove_keyframe")}</button>
      </div>
    `;
    row.querySelector('[data-action="jump"]').addEventListener("click", () => {
      loadIssueFrame(state.currentIssue.issue_id, item.frameIndex);
    });
    row.querySelector('[data-action="remove"]').addEventListener("click", () => {
      removeKeyframeByFrame(item.frameIndex);
    });
    refs.keyframeList.appendChild(row);
  }
}

function jumpToTrack(track) {
  if (!state.currentIssue) {
    return;
  }
  const start = Number(track.visible_start_frame || state.currentIssue.start_frame);
  const end = Number(track.visible_end_frame || state.currentIssue.end_frame);
  let target = Number(state.frame?.frame_index || start);
  if (target < start || target > end) {
    target = start;
  }
  loadIssueFrame(state.currentIssue.issue_id, target);
}

function mergeTrackIntoActiveSlot(trackId) {
  if (!state.currentIssue || !state.frame) {
    return;
  }
  const normalized = String(trackId);
  if (!state.aiByTrack.has(normalized)) {
    showToastKey("toast_ai_not_found", {}, true);
    return;
  }
  applyAiToSlot(state.activeSlot, normalized);
  upsertCurrentKeyframe({ silent: true });
  showToastKey("toast_track_merged", { slot: slotName(state.activeSlot), track: normalized });
}

function splitActiveTrack() {
  const person = state.slots[state.activeSlot];
  if (!person || !bboxValid(person.bbox)) {
    showToastKey("toast_no_frame", {}, true);
    return;
  }
  setSlotBbox(
    state.activeSlot,
    { x: person.bbox.x, y: person.bbox.y, w: person.bbox.w, h: person.bbox.h },
    "manual_param",
    ""
  );
  upsertCurrentKeyframe({ silent: true });
  showToastKey("toast_split_track", { slot: slotName(state.activeSlot) });
}

function markReappearKeyframe() {
  const person = state.slots[state.activeSlot];
  if (!person || !bboxValid(person.bbox)) {
    showToastKey("toast_no_frame", {}, true);
    return;
  }
  upsertCurrentKeyframe({ silent: true });
  showToastKey("toast_reappear_marked", { slot: slotName(state.activeSlot) });
}

function renderTrajectoryCards() {
  if (!refs.trajectoryCards) return;
  refs.trajectoryCards.innerHTML = "";
  const tracks = issueTrackItems();
  if (!state.currentIssue || tracks.length === 0) {
    const empty = document.createElement("div");
    empty.className = "trajectory-card";
    empty.textContent = t("trajectory_empty");
    refs.trajectoryCards.appendChild(empty);
    return;
  }
  for (const track of tracks) {
    const trackId = String(track.track_id);
    const visibleNow = state.aiByTrack.has(trackId);
    const start = Number(track.visible_start_frame || state.currentIssue.start_frame);
    const end = Number(track.visible_end_frame || state.currentIssue.end_frame);
    const row = document.createElement("div");
    row.className = "trajectory-card";
    if (visibleNow) {
      row.classList.add("active");
    }
    row.innerHTML = `
      <div class="trajectory-card-top">
        <span>track ${trackId}</span>
        <span>${visibleNow ? "ACTIVE" : ""}</span>
      </div>
      <div class="trajectory-card-meta">${t("track_range", { start, end })}</div>
      <div class="trajectory-card-meta">${t("track_stats", {
        min: Number(track.min_score || 0).toFixed(3),
        jump: Number(track.max_jump_distance || 0).toFixed(3),
      })}</div>
      <div class="trajectory-card-actions">
        <button type="button" class="btn subtle" data-action="jump">${t("track_jump")}</button>
        <button type="button" class="btn subtle" data-action="merge" ${visibleNow ? "" : "disabled"}>${t("track_merge")}</button>
      </div>
    `;
    row.querySelector('[data-action="jump"]').addEventListener("click", () => jumpToTrack(track));
    row.querySelector('[data-action="merge"]').addEventListener("click", () => mergeTrackIntoActiveSlot(trackId));
    refs.trajectoryCards.appendChild(row);
  }
}

function resetSlots() {
  state.slots = {};
  const names = Array.isArray(state.frame?.slot_names) && state.frame.slot_names.length
    ? state.frame.slot_names
    : SLOT_ORDER;
  state.slotNames = names.slice();
  for (const slot of state.slotNames) {
    state.slots[slot] = { bbox: null, source: "not_set", aiTrackId: "" };
  }
  if (!state.slotNames.includes(state.activeSlot)) {
    state.activeSlot = state.slotNames[0] || "p1";
  }
  syncActiveSlotUI();
  renderSlotTabs();
}

function applyFrame(frame, options = {}) {
  state.frame = frame;
  if (Number.isFinite(Number(frame.total_frames)) && Number(frame.total_frames) > 0) {
    state.progressTarget = Number(frame.total_frames);
  }
  state.aiBoxes = Array.isArray(frame.ai_boxes) ? frame.ai_boxes : [];
  state.aiByTrack = new Map();
  for (const box of state.aiBoxes) {
    const tid = String(box.track_id);
    if (!state.aiByTrack.has(tid)) {
      state.aiByTrack.set(tid, box);
    }
  }
  state.image = null;
  drawCanvas();
  setHintByKey("hint_loading");
  renderAiButtons();
  resetSlots();
  if (!options.skipRecommendations) {
    applyRecommendations(frame.recommendations);
  }
  syncHeader();
  renderSegmentSummary();
  updateProgress();
  loadFrameImage(frame);
  if (options.isAssignment) {
    state.lastAssignmentFrame = frame;
  }
}

function applySegmentPayload(payload, options = {}) {
  state.dispatchMode = "segment";
  state.currentSegment = payload.segment || null;
  applyFrame(payload.frame, options);
}

function applyIssuePayload(payload, options = {}) {
  const prevIssueId = state.currentIssue?.issue_id || "";
  state.dispatchMode = "issue";
  state.currentIssue = payload.issue || null;
  if ((state.currentIssue?.issue_id || "") !== prevIssueId) {
    state.issueKeyframes = [];
  }
  if (options.isAssignment) {
    state.lastAssignmentIssue = state.currentIssue;
  }
  applyFrame(payload.frame, options);
}

function renderAiButtons() {
  const slot = state.activeSlot;
  const container = refs.activeAiButtons;
  container.innerHTML = "";
  const tracks = Array.from(state.aiByTrack.keys()).sort((a, b) => Number(a) - Number(b));
  if (tracks.length === 0) {
    const empty = document.createElement("span");
    empty.textContent = t("no_ai_box");
    empty.style.color = "#5f6e7a";
    empty.style.fontSize = "0.84rem";
    container.appendChild(empty);
    return;
  }

  for (const tid of tracks) {
    const box = state.aiByTrack.get(tid);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "ai-track-btn";
    btn.textContent = `id:${tid}`;
    btn.title = `${slotName(slot)} | track ${tid} | score ${box.score}`;
    btn.addEventListener("click", () => applyAiToSlot(slot, tid));
    container.appendChild(btn);
  }
}

function canAutoApply(slot) {
  const s = state.slots[slot];
  return s.source === "not_set" && !bboxValid(s.bbox) && !s.aiTrackId;
}

function applyRecommendations(recommendations) {
  return;
}

function renderImageSource(src, requestId) {
  const img = new Image();
  img.decoding = "async";
  img.onload = () => {
    if (requestId !== state.imageRequestId) {
      return;
    }
    state.image = img;
    refs.canvas.width = img.width;
    refs.canvas.height = img.height;
    drawCanvas();
    setHintByKey("hint_drag_resize");
  };
  img.onerror = () => {
    if (requestId !== state.imageRequestId) {
      return;
    }
    setHintByKey("hint_load_fail");
    showToastKey("toast_frame_load_failed", {}, true);
  };
  img.src = src;
}

function loadFrameImage(frame) {
  const requestId = ++state.imageRequestId;
  const key = frameCacheKey(frame.video_stem, frame.frame_index);
  const cached = touchCachedImage(key);
  if (cached && cached.blobUrl) {
    renderImageSource(cached.blobUrl, requestId);
    return;
  }
  renderImageSource(`${frame.image_url}&_ts=${Date.now()}`, requestId);
}

function trackColor(trackId) {
  const hue = (Number(trackId) * 47 + 17) % 360;
  return `hsl(${hue}, 72%, 45%)`;
}

function drawLabel(text, x, y, color) {
  ctx.font = "bold 14px 'Trebuchet MS', sans-serif";
  const w = ctx.measureText(text).width + 10;
  ctx.fillStyle = color;
  ctx.fillRect(x, Math.max(0, y - 18), w, 18);
  ctx.fillStyle = "#fff";
  ctx.fillText(text, x + 5, Math.max(12, y - 4));
}

function drawCanvas() {
  if (!state.image) {
    ctx.clearRect(0, 0, refs.canvas.width, refs.canvas.height);
    return;
  }

  ctx.clearRect(0, 0, refs.canvas.width, refs.canvas.height);
  ctx.drawImage(state.image, 0, 0, refs.canvas.width, refs.canvas.height);

  for (const box of state.aiBoxes) {
    ctx.save();
    const color = trackColor(box.track_id);
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.setLineDash([8, 6]);
    ctx.strokeRect(box.bbox_x, box.bbox_y, box.bbox_w, box.bbox_h);
    drawLabel(`id:${box.track_id}`, box.bbox_x + 2, box.bbox_y + 2, color);
    ctx.restore();
  }

  for (const slot of state.slotNames) {
    const slotState = state.slots[slot];
    if (!bboxValid(slotState.bbox)) {
      continue;
    }
    const b = slotState.bbox;
    const color = SLOT_META[slot].color;
    ctx.save();
    ctx.setLineDash([]);
    ctx.lineWidth = slot === state.activeSlot ? 3 : 2;
    ctx.strokeStyle = color;
    ctx.strokeRect(b.x, b.y, b.w, b.h);
    drawLabel(`${SLOT_META[slot].label}`, b.x + 2, b.y + 2, color);
    drawHandles(b, color, slot === state.activeSlot);
    ctx.restore();
  }
}

function handlePoints(bbox) {
  const x1 = bbox.x;
  const y1 = bbox.y;
  const x2 = bbox.x + bbox.w;
  const y2 = bbox.y + bbox.h;
  const xm = (x1 + x2) / 2;
  const ym = (y1 + y2) / 2;
  return {
    nw: { x: x1, y: y1 },
    n: { x: xm, y: y1 },
    ne: { x: x2, y: y1 },
    e: { x: x2, y: ym },
    se: { x: x2, y: y2 },
    s: { x: xm, y: y2 },
    sw: { x: x1, y: y2 },
    w: { x: x1, y: ym },
  };
}

function drawHandles(bbox, color, isActive) {
  const points = handlePoints(bbox);
  for (const p of Object.values(points)) {
    ctx.fillStyle = isActive ? color : "#fff";
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.fillRect(p.x - HANDLE_SIZE / 2, p.y - HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE);
    ctx.strokeRect(p.x - HANDLE_SIZE / 2, p.y - HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE);
  }
}

function canvasPoint(evt) {
  const rect = refs.canvas.getBoundingClientRect();
  const scaleX = refs.canvas.width / rect.width;
  const scaleY = refs.canvas.height / rect.height;
  return {
    x: (evt.clientX - rect.left) * scaleX,
    y: (evt.clientY - rect.top) * scaleY,
  };
}

function pointInBbox(point, bbox) {
  return (
    point.x >= bbox.x &&
    point.x <= bbox.x + bbox.w &&
    point.y >= bbox.y &&
    point.y <= bbox.y + bbox.h
  );
}

function hitTest(point) {
  for (const slot of [state.activeSlot, ...state.slotNames.filter((item) => item !== state.activeSlot)]) {
    const b = state.slots[slot].bbox;
    if (!bboxValid(b)) continue;
    const handles = handlePoints(b);
    for (const [name, h] of Object.entries(handles)) {
      if (Math.abs(point.x - h.x) <= HANDLE_SIZE && Math.abs(point.y - h.y) <= HANDLE_SIZE) {
        return { slot, type: "resize", handle: name };
      }
    }
  }
  for (const slot of state.slotNames) {
    const b = state.slots[slot].bbox;
    if (!bboxValid(b)) continue;
    if (pointInBbox(point, b)) {
      return { slot, type: "move" };
    }
  }
  return null;
}

function resizeFromHandle(orig, handle, point) {
  let x1 = orig.x;
  let y1 = orig.y;
  let x2 = orig.x + orig.w;
  let y2 = orig.y + orig.h;

  if (handle.includes("n")) y1 = point.y;
  if (handle.includes("s")) y2 = point.y;
  if (handle.includes("w")) x1 = point.x;
  if (handle.includes("e")) x2 = point.x;

  if (x2 - x1 < MIN_BOX_SIZE) {
    if (handle.includes("w")) x1 = x2 - MIN_BOX_SIZE;
    else x2 = x1 + MIN_BOX_SIZE;
  }
  if (y2 - y1 < MIN_BOX_SIZE) {
    if (handle.includes("n")) y1 = y2 - MIN_BOX_SIZE;
    else y2 = y1 + MIN_BOX_SIZE;
  }

  const bbox = {
    x: Math.min(x1, x2),
    y: Math.min(y1, y2),
    w: Math.abs(x2 - x1),
    h: Math.abs(y2 - y1),
  };
  return clampBbox(bbox);
}

function setCursorByHit(hit) {
  if (!hit) {
    refs.canvas.style.cursor = state.drawSlot ? "crosshair" : "default";
    return;
  }
  if (hit.type === "move") {
    refs.canvas.style.cursor = "move";
    return;
  }
  const map = {
    n: "ns-resize",
    s: "ns-resize",
    e: "ew-resize",
    w: "ew-resize",
    ne: "nesw-resize",
    sw: "nesw-resize",
    nw: "nwse-resize",
    se: "nwse-resize",
  };
  refs.canvas.style.cursor = map[hit.handle] || "default";
}

function onCanvasDown(evt) {
  if (!state.frame || !state.image) return;
  const point = canvasPoint(evt);

  if (state.drawSlot) {
    const slot = state.drawSlot;
    state.activeSlot = slot;
    state.action = {
      type: "drawing",
      slot,
      start: point,
    };
    setSlotBbox(slot, { x: point.x, y: point.y, w: MIN_BOX_SIZE, h: MIN_BOX_SIZE }, "manual_draw", "");
    setHintByKey("hint_drawing", { slot: slotName(slot) });
    return;
  }

  const hit = hitTest(point);
  setCursorByHit(hit);
  if (!hit) {
    return;
  }
  state.activeSlot = hit.slot;
  const orig = cloneBbox(state.slots[hit.slot].bbox);
  state.action = {
    ...hit,
    start: point,
    orig,
  };
  setHintByKey("hint_editing", { slot: slotName(hit.slot) });
  drawCanvas();
}

function onCanvasMove(evt) {
  if (!state.frame || !state.image) return;
  const point = canvasPoint(evt);
  if (!state.action) {
    setCursorByHit(hitTest(point));
    return;
  }

  const action = state.action;
  if (action.type === "drawing") {
    const x = Math.min(action.start.x, point.x);
    const y = Math.min(action.start.y, point.y);
    const w = Math.max(MIN_BOX_SIZE, Math.abs(point.x - action.start.x));
    const h = Math.max(MIN_BOX_SIZE, Math.abs(point.y - action.start.y));
    setSlotBbox(action.slot, { x, y, w, h }, "manual_draw", "");
    return;
  }

  if (action.type === "move") {
    const dx = point.x - action.start.x;
    const dy = point.y - action.start.y;
    const b = action.orig;
    if (!b) return;
    setSlotBbox(
      action.slot,
      { x: b.x + dx, y: b.y + dy, w: b.w, h: b.h },
      "manual_draw",
      ""
    );
    return;
  }

  if (action.type === "resize") {
    const b = action.orig;
    if (!b) return;
    const resized = resizeFromHandle(b, action.handle, point);
    setSlotBbox(action.slot, resized, "manual_draw", "");
  }
}

function onCanvasUp() {
  if (state.action && state.action.type === "drawing") {
    state.drawSlot = null;
  }
  state.action = null;
  refs.canvas.style.cursor = "default";
  setHintByKey("hint_ready");
}

function bindNumericInputs() {
  const fields = { x: refs.activeX, y: refs.activeY, w: refs.activeW, h: refs.activeH };
  const onInput = () => {
    if (state.syncingInputs) return;
    const values = {
      x: Number(fields.x.value),
      y: Number(fields.y.value),
      w: Number(fields.w.value),
      h: Number(fields.h.value),
    };
    if (Object.values(values).some((v) => Number.isNaN(v))) {
      return;
    }
    setSlotBbox(state.activeSlot, values, "manual_param", "");
  };
  fields.x.addEventListener("input", onInput);
  fields.y.addEventListener("input", onInput);
  fields.w.addEventListener("input", onInput);
  fields.h.addEventListener("input", onInput);
}

function applyAiToSlot(slot, tid) {
  const box = state.aiByTrack.get(tid);
  if (!box) {
    showToastKey("toast_ai_not_found", {}, true);
    return;
  }
  state.activeSlot = slot;
  setSlotBbox(
    slot,
    { x: box.bbox_x, y: box.bbox_y, w: box.bbox_w, h: box.bbox_h },
    "ai",
    tid
  );
  setHintByKey("hint_used_ai", { slot: slotName(slot), track: tid });
}

function startDraw(slot) {
  if (!state.frame) {
    showToastKey("toast_no_frame", {}, true);
    return;
  }
  state.drawSlot = slot;
  state.activeSlot = slot;
  refs.canvas.style.cursor = "crosshair";
  setHintByKey("hint_click_drag_draw", { slot: slotName(slot) });
}

function markSlotAbsent(slot) {
  if (!state.frame) {
    showToastKey("toast_no_frame", {}, true);
    return;
  }
  state.activeSlot = slot;
  state.drawSlot = null;
  state.action = null;
  refs.canvas.style.cursor = "default";
  setSlotBbox(slot, null, "absent", "");
  setHintByKey("hint_marked_absent", { slot: slotName(slot) });
}

function markSlotState(slot, source) {
  if (!state.frame) {
    showToastKey("toast_no_frame", {}, true);
    return;
  }
  state.activeSlot = slot;
  state.drawSlot = null;
  state.action = null;
  refs.canvas.style.cursor = "default";
  setSlotBbox(slot, null, source, "");
  setHintByKey("hint_marked_absent", { slot: slotName(slot) });
}

function validateSubmission() {
  for (const slot of state.slotNames) {
    const s = state.slots[slot];
    const slotLabel = slotName(slot);
    if (["absent", "occluded", "outside"].includes(s.source)) {
      continue;
    }
    if (!bboxValid(s.bbox)) {
      throw new Error(t("err_bbox_missing", { slot: slotLabel }));
    }
    if (s.bbox.w <= 0 || s.bbox.h <= 0) {
      throw new Error(t("err_bbox_wh", { slot: slotLabel }));
    }
    if (!["ai", "manual_draw", "manual_param", "absent", "occluded", "outside"].includes(s.source)) {
      throw new Error(t("err_source_invalid", { slot: slotLabel }));
    }
  }
}

function personSubmitPayload(slot) {
  const person = state.slots[slot];
  if (["absent", "occluded", "outside"].includes(person.source)) {
    return {
      slot,
      bbox_x: 0,
      bbox_y: 0,
      bbox_w: 0,
      bbox_h: 0,
      source: person.source,
      ai_track_id: "",
    };
  }
  return {
    slot,
    bbox_x: round3(person.bbox.x),
    bbox_y: round3(person.bbox.y),
    bbox_w: round3(person.bbox.w),
    bbox_h: round3(person.bbox.h),
    source: person.source,
    ai_track_id: person.aiTrackId || "",
  };
}

function buildSubmitPayload() {
  return {
    annotator_id: annotatorId(),
    video_stem: state.frame.video_stem,
    frame_index: state.frame.frame_index,
    timestamp_ms: state.frame.timestamp_ms,
    slots: state.slotNames.map(personSubmitPayload),
  };
}

async function requestNextFrame() {
  refs.nextFrameBtn.disabled = true;
  try {
    const payload = await postJson("/api/next_frame", { annotator_id: annotatorId() });
    state.dispatchMode = "frame";
    state.currentIssue = null;
    state.lastAssignmentIssue = null;
    exitEditMode();
    applyFrame(payload.frame, { isAssignment: true });
    schedulePrefetch(payload.prefetch_frames);
    showToastKey("toast_loaded_next");
  } catch (err) {
    showToast(err.message, true);
  } finally {
    refs.nextFrameBtn.disabled = false;
  }
}

async function requestNextSegment() {
  if (refs.nextSegmentBtn) {
    refs.nextSegmentBtn.disabled = true;
  }
  try {
    const payload = await postJson("/api/next_segment", { annotator_id: annotatorId() });
    exitEditMode();
    applySegmentPayload(payload, { isAssignment: true });
    showToastKey("toast_loaded_segment");
  } catch (err) {
    showToast(err.message, true);
  } finally {
    if (refs.nextSegmentBtn) {
      refs.nextSegmentBtn.disabled = false;
    }
  }
}

async function requestNextIssue() {
  if (refs.nextIssueBtn) {
    refs.nextIssueBtn.disabled = true;
  }
  try {
    const payload = await postJson("/api/next_issue", { annotator_id: annotatorId() });
    exitEditMode();
    applyIssuePayload(payload, { isAssignment: true });
    loadIssues({ silent: true });
    showToastKey("toast_loaded_issue");
  } catch (err) {
    showToast(err.message, true);
  } finally {
    if (refs.nextIssueBtn) {
      refs.nextIssueBtn.disabled = false;
    }
  }
}

async function loadIssues(options = {}) {
  const { silent = false, videoStem = undefined } = options;
  try {
    const effectiveStem =
      videoStem !== undefined
        ? videoStem
        : (state.currentIssue?.video_stem || state.frame?.video_stem || "");
    const query = new URLSearchParams();
    query.set("limit", "80");
    if (effectiveStem) {
      query.set("video_stem", effectiveStem);
    }
    const payload = await getJson(`/api/issues?${query.toString()}`);
    state.issues = payload.issues || [];
    state.issueListVideoStem = effectiveStem || "";
    renderIssueList();
    renderIssueTimeline();
    if (!silent) {
      showToastKey("toast_loaded_issue");
    }
  } catch (err) {
    showToast(err.message, true);
  }
}

async function loadIssueDetail(issueId) {
  try {
    const payload = await getJson(`/api/issue_detail?issue_id=${encodeURIComponent(issueId)}`);
    exitEditMode();
    applyIssuePayload(payload, { isAssignment: true });
    loadIssues({ silent: true, videoStem: payload.issue?.video_stem || "" });
  } catch (err) {
    showToast(err.message, true);
  }
}

async function loadIssueFrame(issueId, frameIndex) {
  try {
    const payload = await getJson(
      `/api/issue_frame?issue_id=${encodeURIComponent(issueId)}&frame_index=${encodeURIComponent(frameIndex)}`
    );
    applyIssuePayload(payload, { isAssignment: true });
  } catch (err) {
    showToast(err.message, true);
  }
}

function stepIssueFrame(delta) {
  if (!state.currentIssue || !state.frame) {
    return;
  }
  const nextFrame = Number(state.frame.frame_index) + delta;
  loadIssueFrame(state.currentIssue.issue_id, nextFrame);
}

async function submitAndNext() {
  if (!state.frame) {
    showToastKey("toast_no_frame", {}, true);
    return;
  }
  try {
    validateSubmission();
  } catch (err) {
    showToast(err.message, true);
    return;
  }

  refs.submitBtn.disabled = true;
  try {
    const payload = buildSubmitPayload();
    const isSegmentMode = state.dispatchMode === "segment" && state.currentSegment;
    if (isSegmentMode && state.currentSegment?.segment_id) {
      payload.segment_id = state.currentSegment.segment_id;
    }
    const result = await postJson(isSegmentMode ? "/api/submit_segment" : "/api/submit", payload);
    exitEditMode();
    if (isSegmentMode && result.next_segment) {
      applySegmentPayload(result.next_segment, { isAssignment: true });
    } else if (isSegmentMode) {
      state.currentSegment = null;
      renderSegmentSummary();
    } else {
      state.dispatchMode = "segment";
      state.currentSegment = null;
      applyFrame(result.next_frame, { isAssignment: true });
      schedulePrefetch(result.prefetch_frames);
    }
    loadHistory();
    if (isSegmentMode) {
      showToast(`已提交段 ${result.submitted.segment_id}，写入 ${result.submitted_frame_count} 帧`);
    } else {
      showToastKey("toast_submitted", {
        video: result.submitted.video_stem,
        frame: result.submitted.frame_index,
        count: result.submitted.count_after_submit,
      });
    }
  } catch (err) {
    showToast(err.message, true);
  } finally {
    refs.submitBtn.disabled = false;
  }
}

async function submitIssueRange() {
  if (!state.frame || !state.currentIssue) {
    showToastKey("toast_no_frame", {}, true);
    return;
  }
  try {
    validateSubmission();
  } catch (err) {
    showToast(err.message, true);
    return;
  }
  if (refs.submitIssueRangeBtn) {
    refs.submitIssueRangeBtn.disabled = true;
  }
  try {
    const payload = {
      ...buildSubmitPayload(),
      issue_id: state.currentIssue.issue_id,
    };
    const result = await postJson("/api/submit_issue_range", payload);
    if (result.next_issue) {
      applyIssuePayload(result.next_issue, { isAssignment: true });
      loadIssues({ silent: true });
    }
    loadHistory({ silent: true });
    showToast(`已整段应用 ${result.submitted_frame_count} 帧`);
  } catch (err) {
    showToast(err.message, true);
  } finally {
    if (refs.submitIssueRangeBtn) {
      refs.submitIssueRangeBtn.disabled = false;
    }
  }
}

async function submitIssueForwardRange() {
  if (!state.frame || !state.currentIssue) {
    showToastKey("toast_no_frame", {}, true);
    return;
  }
  try {
    validateSubmission();
  } catch (err) {
    showToast(err.message, true);
    return;
  }
  if (refs.submitIssueForwardBtn) {
    refs.submitIssueForwardBtn.disabled = true;
  }
  try {
    const payload = {
      ...buildSubmitPayload(),
      issue_id: state.currentIssue.issue_id,
      start_frame: state.frame.frame_index,
      end_frame: state.currentIssue.end_frame,
    };
    const result = await postJson("/api/submit_issue_partial_range", payload);
    if (result.next_issue) {
      applyIssuePayload(result.next_issue, { isAssignment: true });
      loadIssues({ silent: true });
    } else {
      loadIssues({ silent: true });
    }
    loadHistory({ silent: true });
    showToast(`已向后应用 ${result.submitted_frame_count} 帧`);
  } catch (err) {
    showToast(err.message, true);
  } finally {
    if (refs.submitIssueForwardBtn) {
      refs.submitIssueForwardBtn.disabled = false;
    }
  }
}

async function submitIssueBackwardRange() {
  if (!state.frame || !state.currentIssue) {
    showToastKey("toast_no_frame", {}, true);
    return;
  }
  try {
    validateSubmission();
  } catch (err) {
    showToast(err.message, true);
    return;
  }
  if (refs.submitIssueBackwardBtn) {
    refs.submitIssueBackwardBtn.disabled = true;
  }
  try {
    const payload = {
      ...buildSubmitPayload(),
      issue_id: state.currentIssue.issue_id,
      start_frame: state.currentIssue.start_frame,
      end_frame: state.frame.frame_index,
    };
    const result = await postJson("/api/submit_issue_partial_range", payload);
    if (result.next_issue) {
      applyIssuePayload(result.next_issue, { isAssignment: true });
      loadIssues({ silent: true });
    } else {
      loadIssues({ silent: true });
    }
    loadHistory({ silent: true });
    showToast(`已向前应用 ${result.submitted_frame_count} 帧`);
  } catch (err) {
    showToast(err.message, true);
  } finally {
    if (refs.submitIssueBackwardBtn) {
      refs.submitIssueBackwardBtn.disabled = false;
    }
  }
}

function cloneCurrentSlots() {
  return state.slotNames.map((slot) => personSubmitPayload(slot));
}

function setKeyframeAnchor() {
  upsertCurrentKeyframe();
}

async function submitInterpolation() {
  if (!state.currentIssue || !state.frame) {
    showToastKey("toast_no_frame", {}, true);
    return;
  }
  try {
    validateSubmission();
  } catch (err) {
    showToast(err.message, true);
    return;
  }
  if (!findIssueKeyframe(state.frame.frame_index)) {
    upsertCurrentKeyframe({ silent: true });
  }
  if (state.issueKeyframes.length === 0) {
    showToastKey("keyframe_empty", {}, true);
    return;
  }
  if (refs.submitInterpolationBtn) {
    refs.submitInterpolationBtn.disabled = true;
  }
  try {
    const result = await postJson("/api/submit_issue_propagation", {
      annotator_id: annotatorId(),
      issue_id: state.currentIssue.issue_id,
      keyframes: state.issueKeyframes.map((item) => ({
        frame_index: item.frameIndex,
        slots: item.slots,
      })),
    });
    if (result.next_issue) {
      applyIssuePayload(result.next_issue, { isAssignment: true });
      loadIssues({ silent: true });
    } else {
      loadIssues({ silent: true });
    }
    loadHistory({ silent: true });
    state.issueKeyframes = [];
    renderKeyframeList();
    showToastKey("toast_propagated", { count: result.submitted_frame_count });
  } catch (err) {
    showToast(err.message, true);
  } finally {
    if (refs.submitInterpolationBtn) {
      refs.submitInterpolationBtn.disabled = false;
    }
  }
}

async function getJson(url) {
  const res = await fetch(url, { cache: "no-store" });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok || !payload.ok) {
    throw new Error(payload.error || `Request failed (${res.status})`);
  }
  return payload;
}

function formatTime(ts) {
  if (!ts) return "";
  return ts.replace("T", " ").slice(0, 19);
}

function renderHistory() {
  const container = refs.historyList;
  if (!container) return;
  container.innerHTML = "";
  if (!state.history || state.history.length === 0) {
    const empty = document.createElement("div");
    empty.textContent = t("history_empty");
    empty.style.color = "#5f6e7a";
    empty.style.fontSize = "0.84rem";
    container.appendChild(empty);
    return;
  }

  for (const item of state.history) {
    const btn = document.createElement("div");
    btn.className = "history-item";
    if (item.annotation_id === state.editingAnnotationId) {
      btn.classList.add("active");
    }
    btn.innerHTML = `
      <div class="time">${formatTime(item.submitted_at)}</div>
      <div class="meta">${item.video_stem} #${item.frame_index}</div>
    `;
    btn.addEventListener("click", () => loadAnnotationDetail(item.annotation_id));
    container.appendChild(btn);
  }
}

function updateProgress() {
  if (!refs.progressFill || !refs.progressText) return;
  const count = Array.isArray(state.history) ? state.history.length : 0;
  const target = Math.max(1, Number(state.progressTarget) || 1);
  const ratio = Math.min(1, count / target);
  refs.progressFill.style.width = `${Math.round(ratio * 100)}%`;
  refs.progressText.textContent = `${count}/${target}`;
}

async function loadHistory(options = {}) {
  const { silent = false } = options;
  try {
    const payload = await getJson(`/api/my_annotations?annotator_id=${encodeURIComponent(annotatorId())}`);
    state.history = payload.annotations || [];
    renderHistory();
    updateProgress();
    if (!silent) {
      showToastKey("toast_history_loaded");
    }
  } catch (err) {
    showToast(err.message, true);
  }
}

function applySlotsFromAnnotation(slots) {
  resetSlots();
  if (!Array.isArray(slots)) {
    return;
  }
  for (const item of slots) {
    if (!item || !state.slotNames.includes(item.slot)) continue;
    if (["absent", "occluded", "outside"].includes(item.source)) {
      setSlotBbox(item.slot, null, item.source, "");
      continue;
    }
    if (!item.bbox_w || !item.bbox_h) {
      continue;
    }
    setSlotBbox(
      item.slot,
      {
        x: Number(item.bbox_x),
        y: Number(item.bbox_y),
        w: Number(item.bbox_w),
        h: Number(item.bbox_h),
      },
      item.source || "not_set",
      String(item.ai_track_id || "")
    );
  }
  syncActiveSlotUI();
  renderSlotTabs();
}

async function loadAnnotationDetail(annotationId) {
  try {
    const payload = await getJson(
      `/api/annotation_detail?annotation_id=${encodeURIComponent(annotationId)}&annotator_id=${encodeURIComponent(annotatorId())}`
    );
    enterEditMode(annotationId);
    applyFrame(payload.frame, { skipRecommendations: true, isAssignment: false });
    applySlotsFromAnnotation(payload.annotation.slots);
    syncHeader();
    renderHistory();
  } catch (err) {
    showToast(err.message, true);
  }
}

function enterEditMode(annotationId) {
  state.editing = true;
  state.editingAnnotationId = annotationId;
  refs.saveEditBtn.hidden = false;
  refs.exitEditBtn.hidden = false;
  refs.submitBtn.disabled = true;
  refs.nextFrameBtn.disabled = true;
  if (refs.nextIssueBtn) {
    refs.nextIssueBtn.disabled = true;
  }
}

function exitEditMode() {
  if (!state.editing) {
    return;
  }
  state.editing = false;
  state.editingAnnotationId = "";
  refs.saveEditBtn.hidden = true;
  refs.exitEditBtn.hidden = true;
  refs.submitBtn.disabled = false;
  refs.nextFrameBtn.disabled = false;
  if (refs.nextIssueBtn) {
    refs.nextIssueBtn.disabled = false;
  }
  if (state.dispatchMode === "issue" && state.lastAssignmentFrame && state.lastAssignmentIssue) {
    applyIssuePayload(
      { issue: state.lastAssignmentIssue, frame: state.lastAssignmentFrame },
      { isAssignment: true }
    );
  } else if (state.lastAssignmentFrame) {
    applyFrame(state.lastAssignmentFrame, { skipRecommendations: false, isAssignment: true });
  }
}

function setHistoryToggle(collapsed) {
  if (!refs.historyToggleBtn) return;
  const label = collapsed ? t("history_expand") : t("history_collapse");
  refs.historyToggleBtn.textContent = collapsed ? "⟩" : "⟨";
  refs.historyToggleBtn.title = label;
  refs.historyToggleBtn.setAttribute("aria-label", label);
  refs.historyToggleBtn.setAttribute("data-label", label);
}

function initHistoryDock() {
  const dock = refs.historyDock;
  if (!dock) return;
  const collapsed = localStorage.getItem("ui_review_history_collapsed") === "1";
  dock.classList.toggle("collapsed", collapsed);
  setHistoryToggle(collapsed);
}

function toggleHistoryDock() {
  const dock = refs.historyDock;
  if (!dock) return;
  const next = !dock.classList.contains("collapsed");
  dock.classList.toggle("collapsed", next);
  localStorage.setItem("ui_review_history_collapsed", next ? "1" : "0");
  setHistoryToggle(next);
}

async function saveEdit() {
  if (!state.editing || !state.frame) {
    return;
  }
  try {
    validateSubmission();
  } catch (err) {
    showToast(err.message, true);
    return;
  }
  refs.saveEditBtn.disabled = true;
  try {
    const payload = {
      annotation_id: state.editingAnnotationId,
      annotator_id: annotatorId(),
      video_stem: state.frame.video_stem,
      frame_index: state.frame.frame_index,
      timestamp_ms: state.frame.timestamp_ms,
      slots: state.slotNames.map(personSubmitPayload),
    };
    await postJson("/api/update_annotation", payload);
    await loadHistory({ silent: true });
    showToastKey("toast_edit_saved");
  } catch (err) {
    showToast(err.message, true);
  } finally {
    refs.saveEditBtn.disabled = false;
  }
}
function initEvents() {
  refs.annotatorId.value = getStoredAnnotatorId() || DEFAULT_ANNOTATOR_ID;
  refs.annotatorId.addEventListener("change", () => {
    localStorage.setItem(ANNOTATOR_STORAGE_KEY, annotatorId());
    loadHistory({ silent: true });
  });

  refs.langToggleBtn.addEventListener("click", toggleLanguage);
  if (refs.nextSegmentBtn) {
    refs.nextSegmentBtn.addEventListener("click", requestNextSegment);
  }
  refs.nextFrameBtn.addEventListener("click", requestNextSegment);
  refs.submitBtn.addEventListener("click", submitAndNext);

  refs.activeDrawBtn.addEventListener("click", () => startDraw(state.activeSlot));
  refs.activeAbsentBtn.addEventListener("click", () => markSlotAbsent(state.activeSlot));
  if (refs.activeOccludedBtn) {
    refs.activeOccludedBtn.addEventListener("click", () => markSlotState(state.activeSlot, "occluded"));
  }
  if (refs.activeOutsideBtn) {
    refs.activeOutsideBtn.addEventListener("click", () => markSlotState(state.activeSlot, "outside"));
  }
  refs.refreshHistoryBtn.addEventListener("click", () => loadHistory());
  refs.saveEditBtn.addEventListener("click", saveEdit);
  refs.exitEditBtn.addEventListener("click", exitEditMode);
  if (refs.historyToggleBtn && refs.historyDock) {
    refs.historyToggleBtn.addEventListener("click", () => toggleHistoryDock());
  }

  bindNumericInputs();

  refs.canvas.addEventListener("mousedown", onCanvasDown);
  refs.canvas.addEventListener("mousemove", onCanvasMove);
  refs.canvas.addEventListener("mouseup", onCanvasUp);
  refs.canvas.addEventListener("mouseleave", onCanvasUp);

  refs.annotatorModalCloseBtn.addEventListener("click", closeAnnotatorModalAndContinue);
  refs.annotatorModalSubmitBtn.addEventListener("click", submitAnnotatorModal);
  refs.annotatorModalInput.addEventListener("keydown", (evt) => {
    if (evt.key === "Enter") {
      evt.preventDefault();
      submitAnnotatorModal();
    } else if (evt.key === "Escape") {
      evt.preventDefault();
      closeAnnotatorModalAndContinue();
    }
  });
}

function init() {
  state.lang = localStorage.getItem("ui_review_lang") || "zh";
  if (!I18N[state.lang]) {
    state.lang = "zh";
  }

  initEvents();
  syncHeader();
  resetSlots();
  setHintByKey("hint_start");
  applyLanguage();
  const prompted = maybePromptAnnotatorModal();
  if (!prompted) {
    requestInitialSegmentOnce();
  }
  refs.saveEditBtn.hidden = true;
  refs.exitEditBtn.hidden = true;
  initHistoryDock();
  loadHistory({ silent: true });
}

window.addEventListener("DOMContentLoaded", init);
