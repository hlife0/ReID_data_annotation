const refs = {
  refreshBtn: document.getElementById("refreshBtn"),
  mSegmentCount: document.getElementById("mSegmentCount"),
  mQueueTotal: document.getElementById("mQueueTotal"),
  mQueueCompleted: document.getElementById("mQueueCompleted"),
  mQueuePending: document.getElementById("mQueuePending"),
  mPass1Completed: document.getElementById("mPass1Completed"),
  mPass2Completed: document.getElementById("mPass2Completed"),
  mAnnotationCount: document.getElementById("mAnnotationCount"),
  mAnnotatorCount: document.getElementById("mAnnotatorCount"),
  segmentCountChart: document.getElementById("segmentCountChart"),
  annotatorProgressChart: document.getElementById("annotatorProgressChart"),
  annotatorBody: document.getElementById("annotatorBody"),
  recentBody: document.getElementById("recentBody"),
  segmentIdSelect: document.getElementById("segmentIdSelect"),
  querySegmentBtn: document.getElementById("querySegmentBtn"),
  segmentSummary: document.getElementById("segmentSummary"),
  segmentDetailBody: document.getElementById("segmentDetailBody"),
  toast: document.getElementById("toast"),
};

const state = {
  cachedOverview: null,
  cachedAnnotators: [],
  cachedRecent: [],
  cachedSegments: [],
  cachedSegmentDetail: null,
};

function showToast(text, isError = false) {
  refs.toast.textContent = text;
  refs.toast.style.background = isError ? "rgba(124, 32, 27, 0.94)" : "rgba(19, 32, 44, 0.92)";
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
    empty.textContent = "暂无数据";
    container.appendChild(empty);
    return;
  }

  const max = Math.max(...items.map((item) => Number(item[valueKey] || 0)), 1);
  for (const item of items) {
    const value = Number(item[valueKey] || 0);
    const ratio = Math.max(0, Math.min(1, value / max));
    const row = document.createElement("div");
    row.className = "bar-row";
    row.innerHTML = `
      <div class="bar-label">${item[labelKey]}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${Math.max(2, ratio * 100)}%"></div></div>
      <div class="bar-value">${value}</div>
    `;
    container.appendChild(row);
  }
}

function renderOverview(overview) {
  state.cachedOverview = overview;
  refs.mSegmentCount.textContent = overview.segment_count;
  refs.mQueueTotal.textContent = overview.queue_total;
  refs.mQueueCompleted.textContent = overview.queue_completed;
  refs.mQueuePending.textContent = overview.queue_pending;
  refs.mPass1Completed.textContent = overview.pass1_completed;
  refs.mPass2Completed.textContent = overview.pass2_completed;
  refs.mAnnotationCount.textContent = overview.annotation_count;
  refs.mAnnotatorCount.textContent = overview.annotator_count;

  renderBarChart(refs.segmentCountChart, overview.segment_annotation_bins || [], "label", "count");
  renderBarChart(refs.annotatorProgressChart, overview.annotator_frame_counts || [], "annotator_id", "completed_frames");
}

function renderAnnotatorTable(rows) {
  state.cachedAnnotators = rows;
  refs.annotatorBody.innerHTML = "";
  if (!rows.length) {
    refs.annotatorBody.innerHTML = `<tr><td colspan="5">暂无记录</td></tr>`;
    return;
  }
  for (const row of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.annotator_id}</td>
      <td>${row.annotation_count}</td>
      <td>${row.completed_frames}</td>
      <td>${row.completed_frames} / ${row.target_frames}</td>
      <td>${row.latest_submitted_at || "-"}</td>
    `;
    refs.annotatorBody.appendChild(tr);
  }
}

function renderRecentTable(rows) {
  state.cachedRecent = rows;
  refs.recentBody.innerHTML = "";
  if (!rows.length) {
    refs.recentBody.innerHTML = `<tr><td colspan="7">暂无记录</td></tr>`;
    return;
  }
  for (const row of rows) {
    const passLabel = row.pass_index > 0 ? `P${row.pass_index}` : "extra";
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td title="${row.annotation_id}">${row.annotation_id}</td>
      <td>${row.annotator_id}</td>
      <td>${row.segment_id}</td>
      <td>${passLabel}</td>
      <td>${row.frame_index}</td>
      <td>${row.submitted_at}</td>
      <td>${row.slots_summary || "-"}</td>
    `;
    refs.recentBody.appendChild(tr);
  }
}

function renderSegments(rows) {
  state.cachedSegments = rows;
  refs.segmentIdSelect.innerHTML = "";
  if (!rows.length) {
    refs.segmentIdSelect.innerHTML = `<option value="">（无 segment）</option>`;
    return;
  }
  for (const row of rows) {
    const option = document.createElement("option");
    option.value = row.segment_id;
    option.textContent = `${row.segment_id} · ${row.segment_type} · ${row.annotation_count}次`;
    refs.segmentIdSelect.appendChild(option);
  }
}

function renderSegmentDetail(detail) {
  state.cachedSegmentDetail = detail;
  const segment = detail.segment;
  refs.segmentSummary.textContent =
    `segment=${segment.segment_id}, video=${segment.video_stem}, type=${segment.segment_type}, ` +
    `frame_count=${segment.frame_count}, range=${segment.start_frame}-${segment.end_frame}, rep=${segment.representative_frame}`;

  refs.segmentDetailBody.innerHTML = "";
  const rows = [];
  for (const item of detail.queue_items || []) {
    rows.push(
      `<tr><td>queue</td><td>${item.queue_id}</td><td>P${item.pass_index}</td><td>${item.queue_order}</td><td>${item.status}</td><td>${item.completed_by || "-"}</td><td>${item.completed_at || "-"}</td></tr>`
    );
  }
  for (const item of detail.annotations || []) {
    rows.push(
      `<tr><td>annotation</td><td>${item.annotation_id}</td><td>-</td><td>-</td><td>submitted</td><td>${item.annotator_id}</td><td>${item.submitted_at} / ${item.slots_summary || "-"}</td></tr>`
    );
  }
  refs.segmentDetailBody.innerHTML = rows.length ? rows.join("") : `<tr><td colspan="7">暂无记录</td></tr>`;
}

async function loadOverview() {
  const payload = await fetchJson("/api/admin/overview");
  renderOverview(payload.overview);
}

async function loadAnnotators() {
  const payload = await fetchJson("/api/admin/annotators");
  renderAnnotatorTable(payload.annotators || []);
  renderRecentTable(payload.recent_annotations || []);
}

async function loadSegments() {
  const payload = await fetchJson("/api/admin/segments");
  renderSegments(payload.segments || []);
}

async function querySegmentDetail() {
  const segmentId = refs.segmentIdSelect.value.trim();
  if (!segmentId) {
    showToast("请先选择 segment", true);
    return;
  }
  const payload = await fetchJson(`/api/admin/segment_detail?segment_id=${encodeURIComponent(segmentId)}`);
  renderSegmentDetail(payload.detail);
}

async function refreshAll() {
  try {
    await Promise.all([loadOverview(), loadAnnotators(), loadSegments()]);
    if (refs.segmentIdSelect.value) {
      await querySegmentDetail();
    }
    showToast("数据已刷新");
  } catch (error) {
    showToast(error.message, true);
  }
}

function initEvents() {
  refs.refreshBtn.addEventListener("click", () => {
    refreshAll();
  });
  refs.querySegmentBtn.addEventListener("click", () => {
    querySegmentDetail().catch((error) => showToast(error.message, true));
  });
}

function init() {
  initEvents();
  refreshAll();
}

window.addEventListener("DOMContentLoaded", init);
