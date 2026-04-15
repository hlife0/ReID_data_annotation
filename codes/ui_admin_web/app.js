const I18N = {
  zh: {
    page_title: "UI 标注后台面板",
    page_subtitle: "端口 10087：Annotator统计、逐帧明细、整体进度分布",
    refresh: "刷新数据",
    metric_total_frames: "总帧数",
    metric_annotated_frames: "已被标注帧数",
    metric_total_annotations: "总提交数",
    metric_annotator_count: "Annotator数量",
    metric_segment_count: "总段数",
    metric_stable_segment_count: "稳定段数",
    metric_non_simple_count: "非简单单帧数",
    metric_max_stable_length: "最长稳定段",
    chart1_title: "Overall 统计图 1：帧被标注次数分布",
    chart1_hint: "展示被标注过 1、2、3、4+ 次的帧数量",
    chart2_title: "Overall 统计图 2：每个 Annotator 标注数量",
    chart2_hint: "按提交标注数降序",
    annotator_overview_title: "Annotator 总览",
    recent_annotations_title: "最近标注记录（谁标注了哪些帧）",
    frame_query_title: "指定视频 + 指定帧 查询",
    video: "视频",
    frame_index: "帧号",
    query_frame_detail: "查询帧明细",
    th_annotator: "Annotator",
    th_annotation_count: "标注数",
    th_assignment_count: "分配数",
    th_videos_covered: "覆盖视频数",
    th_latest_submitted: "最近提交时间",
    th_annotator_lower: "annotator",
    th_video: "video",
    th_frame: "frame",
    th_annotation_id: "annotation_id",
    th_submitted_at: "提交时间",
    th_slots: "标注槽位",
    empty_no_data: "暂无数据",
    empty_no_records: "暂无记录",
    empty_no_frame_annotations: "该帧还没有标注记录",
    no_videos: "（无视频）",
    frame_summary: "video={video}, frame={frame}, timestamp_ms={timestamp}, 被标注次数={count}",
    toast_select_video: "请先选择视频",
    toast_frame_index_invalid: "frame index 必须大于0",
    toast_refreshed: "数据已刷新",
    src_ai: "AI",
    src_manual_draw: "手动画框",
    src_manual_param: "参数修改",
    src_absent: "不存在",
    src_unknown: "未知",
    lang_toggle: "EN",
    na: "-",
  },
  en: {
    page_title: "UI Annotation Admin Panel",
    page_subtitle: "Port 10087: annotator stats, per-frame detail, and overall progress distribution",
    refresh: "Refresh",
    metric_total_frames: "Total Frames",
    metric_annotated_frames: "Annotated Frames",
    metric_total_annotations: "Total Submissions",
    metric_annotator_count: "Annotators",
    metric_segment_count: "Segments",
    metric_stable_segment_count: "Stable Segments",
    metric_non_simple_count: "Non-Simple Singles",
    metric_max_stable_length: "Max Stable Length",
    chart1_title: "Overall Chart 1: Frame Annotation Count Distribution",
    chart1_hint: "Count of frames annotated 1, 2, 3, and 4+ times",
    chart2_title: "Overall Chart 2: Annotations per Annotator",
    chart2_hint: "Sorted by annotation count descending",
    annotator_overview_title: "Annotator Overview",
    recent_annotations_title: "Recent Annotations (who annotated which frames)",
    frame_query_title: "Query by Video + Frame",
    video: "Video",
    frame_index: "Frame Index",
    query_frame_detail: "Query Frame Detail",
    th_annotator: "Annotator",
    th_annotation_count: "Annotations",
    th_assignment_count: "Assignments",
    th_videos_covered: "Videos Covered",
    th_latest_submitted: "Latest Submitted",
    th_annotator_lower: "annotator",
    th_video: "video",
    th_frame: "frame",
    th_annotation_id: "annotation_id",
    th_submitted_at: "submitted_at",
    th_slots: "Slots",
    empty_no_data: "No data",
    empty_no_records: "No records",
    empty_no_frame_annotations: "No annotations for this frame yet",
    no_videos: "(No videos)",
    frame_summary: "video={video}, frame={frame}, timestamp_ms={timestamp}, annotation_count={count}",
    toast_select_video: "Please select a video first",
    toast_frame_index_invalid: "frame index must be greater than 0",
    toast_refreshed: "Data refreshed",
    src_ai: "ai",
    src_manual_draw: "manual_draw",
    src_manual_param: "manual_param",
    src_absent: "absent",
    src_unknown: "unknown",
    lang_toggle: "中",
    na: "-",
  },
};

const refs = {
  langToggleBtn: document.getElementById("langToggleBtn"),
  refreshBtn: document.getElementById("refreshBtn"),
  mTotalFrames: document.getElementById("mTotalFrames"),
  mAnnotatedFrames: document.getElementById("mAnnotatedFrames"),
  mTotalAnnotations: document.getElementById("mTotalAnnotations"),
  mAnnotatorCount: document.getElementById("mAnnotatorCount"),
  mSegmentCount: document.getElementById("mSegmentCount"),
  mStableSegmentCount: document.getElementById("mStableSegmentCount"),
  mNonSimpleCount: document.getElementById("mNonSimpleCount"),
  mMaxStableLength: document.getElementById("mMaxStableLength"),
  frameDistChart: document.getElementById("frameDistChart"),
  annotatorChart: document.getElementById("annotatorChart"),
  annotatorBody: document.getElementById("annotatorBody"),
  recentBody: document.getElementById("recentBody"),
  videoStemSelect: document.getElementById("videoStemSelect"),
  frameIndexInput: document.getElementById("frameIndexInput"),
  queryFrameBtn: document.getElementById("queryFrameBtn"),
  frameSummary: document.getElementById("frameSummary"),
  frameDetailBody: document.getElementById("frameDetailBody"),
  toast: document.getElementById("toast"),
};

const state = {
  lang: "zh",
  cachedVideos: [],
  cachedOverview: null,
  cachedAnnotators: null,
  cachedRecent: null,
  cachedFrame: null,
};

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

  if (state.cachedOverview) {
    renderOverview(state.cachedOverview);
  }
  if (state.cachedAnnotators || state.cachedRecent) {
    renderAnnotatorTable(state.cachedAnnotators || []);
    renderRecentTable(state.cachedRecent || []);
  }
  renderVideoSelect(state.cachedVideos || []);
  if (state.cachedFrame) {
    renderFrameDetail(state.cachedFrame);
  }
}

function toggleLanguage() {
  state.lang = state.lang === "zh" ? "en" : "zh";
  localStorage.setItem("ui_admin_lang", state.lang);
  applyLanguage();
}

function sourceLabel(source) {
  if (source === "ai") return t("src_ai");
  if (source === "manual_draw") return t("src_manual_draw");
  if (source === "manual_param") return t("src_manual_param");
  if (source === "absent") return t("src_absent");
  return t("src_unknown");
}

function showToast(text, isError = false) {
  refs.toast.textContent = text;
  refs.toast.style.background = isError
    ? "rgba(124, 32, 27, 0.94)"
    : "rgba(19, 32, 44, 0.92)";
  refs.toast.classList.add("show");
  setTimeout(() => refs.toast.classList.remove("show"), 1800);
}

async function fetchJson(url) {
  const res = await fetch(url, { cache: "no-store" });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok || !payload.ok) {
    throw new Error(payload.error || `request failed: ${res.status}`);
  }
  return payload;
}

function renderBarChart(container, items, labelKey, valueKey) {
  container.innerHTML = "";
  if (!Array.isArray(items) || items.length === 0) {
    const empty = document.createElement("div");
    empty.className = "hint";
    empty.textContent = t("empty_no_data");
    container.appendChild(empty);
    return;
  }

  const max = Math.max(...items.map((x) => Number(x[valueKey] || 0)), 1);
  for (const item of items) {
    const value = Number(item[valueKey] || 0);
    const ratio = Math.max(0, Math.min(1, value / max));

    const row = document.createElement("div");
    row.className = "bar-row";

    const label = document.createElement("div");
    label.className = "bar-label";
    label.textContent = item[labelKey];

    const track = document.createElement("div");
    track.className = "bar-track";

    const fill = document.createElement("div");
    fill.className = "bar-fill";
    fill.style.width = `${Math.max(2, ratio * 100)}%`;
    track.appendChild(fill);

    const valueEl = document.createElement("div");
    valueEl.className = "bar-value";
    valueEl.textContent = value;

    row.appendChild(label);
    row.appendChild(track);
    row.appendChild(valueEl);
    container.appendChild(row);
  }
}

function renderOverview(overview) {
  state.cachedOverview = overview;
  refs.mTotalFrames.textContent = overview.total_frames;
  refs.mAnnotatedFrames.textContent = overview.annotated_frames;
  refs.mTotalAnnotations.textContent = overview.total_annotations;
  refs.mAnnotatorCount.textContent = overview.unique_annotators;
  refs.mSegmentCount.textContent = overview.segment_summary?.segment_count ?? 0;
  refs.mStableSegmentCount.textContent = overview.segment_summary?.stable_segment_count ?? 0;
  refs.mNonSimpleCount.textContent = overview.segment_summary?.non_simple_single_frame_count ?? 0;
  refs.mMaxStableLength.textContent = overview.segment_summary?.max_stable_segment_length ?? 0;

  const bins = (overview.frame_count_bins || []).map((x) => ({ label: x.label, count: x.count }));
  renderBarChart(refs.frameDistChart, bins, "label", "count");
  renderBarChart(refs.annotatorChart, overview.annotator_counts || [], "annotator_id", "annotation_count");
}

function renderAnnotatorTable(rows) {
  state.cachedAnnotators = rows;
  refs.annotatorBody.innerHTML = "";
  if (!rows || rows.length === 0) {
    refs.annotatorBody.innerHTML = `<tr><td colspan="5">${t("empty_no_records")}</td></tr>`;
    return;
  }

  for (const row of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.annotator_id}</td>
      <td>${row.annotation_count}</td>
      <td>${row.assignment_count}</td>
      <td>${row.videos_covered}</td>
      <td>${row.latest_submitted_at || t("na")}</td>
    `;
    refs.annotatorBody.appendChild(tr);
  }
}

function renderRecentTable(rows) {
  state.cachedRecent = rows;
  refs.recentBody.innerHTML = "";
  if (!rows || rows.length === 0) {
    refs.recentBody.innerHTML = `<tr><td colspan="7">${t("empty_no_records")}</td></tr>`;
    return;
  }

  for (const row of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td title="${row.annotation_id}">${row.annotation_id}</td>
      <td>${row.annotator_id}</td>
      <td>${row.video_stem}</td>
      <td>${row.frame_index}</td>
      <td>${row.submitted_at}</td>
      <td colspan="2">${row.slots_summary || t("na")}</td>
    `;
    refs.recentBody.appendChild(tr);
  }
}

function renderFrameDetail(frame) {
  state.cachedFrame = frame;
  refs.frameSummary.textContent = t("frame_summary", {
    video: frame.video_stem,
    frame: frame.frame_index,
    timestamp: frame.timestamp_ms.toFixed(3),
    count: frame.annotation_count,
  });

  refs.frameDetailBody.innerHTML = "";
  if (!frame.annotations || frame.annotations.length === 0) {
    refs.frameDetailBody.innerHTML = `<tr><td colspan="5">${t("empty_no_frame_annotations")}</td></tr>`;
    return;
  }

  for (const row of frame.annotations) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td title="${row.annotation_id}">${row.annotation_id}</td>
      <td>${row.annotator_id}</td>
      <td>${row.submitted_at}</td>
      <td colspan="2">${row.slots_summary || t("na")}</td>
    `;
    refs.frameDetailBody.appendChild(tr);
  }
}

function renderVideoSelect(videos) {
  const prev = refs.videoStemSelect.value;
  refs.videoStemSelect.innerHTML = "";
  if (!videos || videos.length === 0) {
    refs.videoStemSelect.innerHTML = `<option value="">${t("no_videos")}</option>`;
    return;
  }

  for (const video of videos) {
    const option = document.createElement("option");
    option.value = video.video_stem;
    option.textContent = `${video.video_stem} [${video.min_frame}-${video.max_frame}]`;
    refs.videoStemSelect.appendChild(option);
  }

  const hasPrev = videos.some((x) => x.video_stem === prev);
  refs.videoStemSelect.value = hasPrev ? prev : videos[0].video_stem;
  if (!hasPrev) {
    refs.frameIndexInput.value = videos[0].min_frame;
  }
}

async function loadOverview() {
  const payload = await fetchJson("/api/overview");
  renderOverview(payload.overview);
}

async function loadAnnotators() {
  const payload = await fetchJson("/api/annotators");
  renderAnnotatorTable(payload.annotators || []);
  renderRecentTable(payload.recent_annotations || []);
}

async function loadVideos() {
  const payload = await fetchJson("/api/videos");
  state.cachedVideos = payload.videos || [];
  renderVideoSelect(state.cachedVideos);
}

async function queryFrameDetail() {
  const videoStem = refs.videoStemSelect.value;
  const frameIndex = Number(refs.frameIndexInput.value);
  if (!videoStem) {
    showToast(t("toast_select_video"), true);
    return;
  }
  if (!Number.isFinite(frameIndex) || frameIndex <= 0) {
    showToast(t("toast_frame_index_invalid"), true);
    return;
  }

  try {
    const payload = await fetchJson(
      `/api/frame_detail?video_stem=${encodeURIComponent(videoStem)}&frame_index=${frameIndex}`
    );
    renderFrameDetail(payload.frame);
  } catch (err) {
    showToast(err.message, true);
  }
}

async function refreshAll() {
  refs.refreshBtn.disabled = true;
  try {
    await Promise.all([loadOverview(), loadAnnotators(), loadVideos()]);
    await queryFrameDetail();
    showToast(t("toast_refreshed"));
  } catch (err) {
    showToast(err.message, true);
  } finally {
    refs.refreshBtn.disabled = false;
  }
}

function initEvents() {
  refs.langToggleBtn.addEventListener("click", toggleLanguage);
  refs.refreshBtn.addEventListener("click", refreshAll);
  refs.queryFrameBtn.addEventListener("click", queryFrameDetail);
  refs.videoStemSelect.addEventListener("change", () => {
    const selected = state.cachedVideos.find((x) => x.video_stem === refs.videoStemSelect.value);
    if (selected) {
      refs.frameIndexInput.value = selected.min_frame;
    }
  });
}

function init() {
  state.lang = localStorage.getItem("ui_admin_lang") || "zh";
  if (!I18N[state.lang]) {
    state.lang = "zh";
  }
  initEvents();
  applyLanguage();
  refreshAll();
}

window.addEventListener("DOMContentLoaded", init);
