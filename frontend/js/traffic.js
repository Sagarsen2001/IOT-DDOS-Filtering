/**
 * js/traffic.js
 * =============
 * Traffic monitoring page controller.
 * Handles: flow table, search/filter, pagination, auto-refresh, KPIs.
 */

let _allFlows = [];
let _filteredFlows = [];
let _currentPage = 1;
const PAGE_SIZE = CONFIG.TABLE_PAGE_SIZE;
let _pollTimer = null;
let _autoRefresh = false;
let _sortKey = "timestamp";
let _sortAsc = false;

/* ---------------------------------------------------------------
   Shared helpers
   --------------------------------------------------------------- */
function showToast(type, title, msg, dur = 4000) {
  const icons = { success: "fa-circle-check", error: "fa-circle-xmark", warning: "fa-triangle-exclamation", info: "fa-circle-info" };
  const c = document.getElementById("toast-container");
  if (!c) return;
  const t = document.createElement("div");
  t.className = `toast toast-${type}`;
  t.setAttribute("role", "alert");
  t.innerHTML = `<i class="fa-solid ${icons[type] || icons.info} toast-icon" aria-hidden="true"></i><div class="toast-body"><div class="toast-title">${escapeHtml(title)}</div>${msg ? `<div class="toast-msg">${escapeHtml(msg)}</div>` : ""}</div><button class="toast-close" aria-label="Dismiss">&times;</button>`;
  t.querySelector(".toast-close").onclick = () => { t.classList.add("removing"); t.addEventListener("animationend", () => t.remove(), { once: true }); };
  c.appendChild(t);
  if (dur > 0) setTimeout(() => { if (t.parentNode) { t.classList.add("removing"); t.addEventListener("animationend", () => t.remove(), { once: true }); } }, dur);
}

function updateHeader(online, demoMode) {
  const dot = document.getElementById("api-dot");
  const txt = document.getElementById("api-status-text");
  const badge = document.getElementById("demo-mode-badge");
  if (dot) { dot.classList.toggle("online", online); dot.classList.toggle("offline", !online); }
  if (txt) txt.textContent = online ? "Connected" : "Offline";
  if (badge) {
    badge.style.display = demoMode !== undefined ? "inline-flex" : "none";
    badge.className = demoMode ? "demo-badge" : "demo-badge real-badge";
    badge.innerHTML = demoMode ? '<i class="fa-solid fa-flask"></i> DEMO MODE' : '<i class="fa-solid fa-circle-check"></i> REAL MODE';
  }
  const tEl = document.getElementById("last-updated-time");
  if (tEl) tEl.textContent = formatTimeShort(new Date().toISOString());
}

/* ---------------------------------------------------------------
   Table rendering
   --------------------------------------------------------------- */
function renderTrafficTable() {
  const tbody = document.getElementById("traffic-tbody");
  if (!tbody) return;

  const start = (_currentPage - 1) * PAGE_SIZE;
  const page = _filteredFlows.slice(start, start + PAGE_SIZE);

  // Update KPIs
  const normalCount = _allFlows.filter(f => f.prediction === "NORMAL" || f.label == 0).length;
  const ddosCount = _allFlows.filter(f => f.prediction === "DDOS" || f.label == 1).length;
  setEl("total-flows", _allFlows.length || "—");
  setEl("normal-flows", normalCount || "—");
  setEl("ddos-flows", ddosCount || "—");

  if (!_filteredFlows.length) {
    tbody.innerHTML = `<tr><td colspan="13"><div class="empty-state">
      <i class="fa-solid fa-wave-square" aria-hidden="true"></i>
      <h3>No Traffic Data</h3>
      <p>No flows match the current filter, or no traffic has been recorded yet.</p>
    </div></td></tr>`;
    renderPagination(0);
    return;
  }

  tbody.innerHTML = page.map(f => {
    const pred = f.prediction || (f.label == 1 ? "DDOS" : f.label == 0 ? "NORMAL" : "—");
    const predCls = pred === "DDOS" ? "badge-danger" : pred === "NORMAL" ? "badge-success" : "badge-secondary";
    const conf = f.confidence != null ? formatPercentage(f.confidence) : "—";

    return `<tr>
      <td class="td-time">${escapeHtml(formatTimestamp(f.timestamp))}</td>
      <td class="td-ip">${escapeHtml(f.source_ip || "—")}</td>
      <td class="td-ip" style="color:var(--text-secondary)">${escapeHtml(f.destination_ip || "—")}</td>
      <td class="td-mono td-muted">${escapeHtml(String(f.source_port || "—"))}</td>
      <td class="td-mono td-muted">${escapeHtml(String(f.destination_port || "—"))}</td>
      <td class="td-mono">${escapeHtml(f.protocol || "—")}</td>
      <td class="td-muted">${escapeHtml(formatDuration(f.duration))}</td>
      <td class="td-muted">${escapeHtml(formatNumber(f.packet_count))}</td>
      <td class="td-muted">${escapeHtml(formatBytes(f.byte_count))}</td>
      <td class="${f.packet_rate > 500 ? 'td-ip' : 'td-muted'}" style="${f.packet_rate > 500 ? 'color:var(--yellow)' : ''}">${escapeHtml(formatRate(f.packet_rate))}</td>
      <td>${pred !== "—" ? `<span class="badge ${predCls}"><i class="fa-solid ${pred === 'DDOS' ? 'fa-virus' : 'fa-check'}" aria-hidden="true"></i> ${escapeHtml(pred)}</span>` : "—"}</td>
      <td class="td-muted">${escapeHtml(conf)}</td>
      <td class="td-actions">
        ${pred === "DDOS" ? `<button class="btn btn-danger btn-sm" onclick="blockIp('${escapeHtml(f.source_ip || '')}')"><i class="fa-solid fa-ban" aria-hidden="true"></i></button>` : ""}
      </td>
    </tr>`;
  }).join("");

  renderPagination(_filteredFlows.length);
}

function setEl(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function renderPagination(total) {
  const pages = Math.ceil(total / PAGE_SIZE);
  const c = document.getElementById("traffic-pagination");
  if (!c) return;
  if (pages <= 1) { c.innerHTML = ""; return; }
  let html = `<span style="margin-right:0.5rem;color:var(--text-secondary)">Page ${_currentPage} of ${pages}</span>`;
  html += `<button class="page-btn" onclick="changePage(${_currentPage - 1})" ${_currentPage <= 1 ? "disabled" : ""}>‹</button>`;
  for (let i = 1; i <= pages; i++) {
    if (i === 1 || i === pages || Math.abs(i - _currentPage) <= 1)
      html += `<button class="page-btn ${i === _currentPage ? "active" : ""}" onclick="changePage(${i})">${i}</button>`;
    else if (Math.abs(i - _currentPage) === 2)
      html += `<span style="color:var(--text-muted)">…</span>`;
  }
  html += `<button class="page-btn" onclick="changePage(${_currentPage + 1})" ${_currentPage >= pages ? "disabled" : ""}>›</button>`;
  c.innerHTML = html;
}

function changePage(p) {
  _currentPage = Math.max(1, Math.min(p, Math.ceil(_filteredFlows.length / PAGE_SIZE)));
  renderTrafficTable();
}

/* ---------------------------------------------------------------
   Filters
   --------------------------------------------------------------- */
function applyFilters() {
  const search = (document.getElementById("traffic-search")?.value || "").toLowerCase();
  const pred = document.getElementById("traffic-prediction-filter")?.value || "";
  const proto = document.getElementById("traffic-protocol-filter")?.value || "";

  _filteredFlows = _allFlows.filter(f => {
    const matchSearch = !search || (f.source_ip || "").toLowerCase().includes(search) || (f.destination_ip || "").toLowerCase().includes(search);
    const fpred = f.prediction || (f.label == 1 ? "DDOS" : f.label == 0 ? "NORMAL" : "");
    const matchPred = !pred || fpred.toUpperCase() === pred.toUpperCase();
    const matchProto = !proto || (f.protocol || "").toUpperCase() === proto.toUpperCase();
    return matchSearch && matchPred && matchProto;
  });

  // Sort
  _filteredFlows.sort((a, b) => {
    let av = a[_sortKey], bv = b[_sortKey];
    if (_sortKey === "timestamp") { av = new Date(av || 0); bv = new Date(bv || 0); }
    if (av < bv) return _sortAsc ? -1 : 1;
    if (av > bv) return _sortAsc ? 1 : -1;
    return 0;
  });

  _currentPage = 1;
  renderTrafficTable();
}

/* ---------------------------------------------------------------
   Block IP (quick action from table)
   --------------------------------------------------------------- */
async function blockIp(ip) {
  if (!ip) return;
  if (!confirm(`Block traffic from ${ip}? (will be simulated in DEMO MODE)`)) return;
  const res = await mitigateSource(ip);
  if (res.ok && res.data?.success) {
    showToast("success", res.data.simulated ? "Simulated Block" : "Blocked", `Rule applied for ${ip}`);
  } else {
    showToast("error", "Block Failed", res.error || "Unknown error");
  }
}

/* ---------------------------------------------------------------
   Main refresh
   --------------------------------------------------------------- */
async function refresh() {
  const tbody = document.getElementById("traffic-tbody");
  const limitSel = document.getElementById("traffic-limit");
  const limit = limitSel ? parseInt(limitSel.value) : 100;

  const health = await getHealth();
  updateHeader(health.ok, undefined);
  if (!health.ok) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="13"><div class="empty-state"><i class="fa-solid fa-plug-circle-xmark"></i><h3>Backend Unavailable</h3><p>${escapeHtml(health.error)}</p></div></td></tr>`;
    return;
  }

  const [statusRes, trafficRes] = await Promise.all([getSystemStatus(), getTraffic({ limit })]);

  if (statusRes.ok) updateHeader(true, statusRes.data?.demo_mode);

  if (trafficRes.ok) {
    _allFlows = trafficRes.data?.flows || [];
    applyFilters();
  } else {
    if (tbody) tbody.innerHTML = `<tr><td colspan="13"><div class="empty-state"><i class="fa-solid fa-circle-xmark"></i><h3>Error</h3><p>${escapeHtml(trafficRes.error)}</p></div></td></tr>`;
  }
}

/* ---------------------------------------------------------------
   Sort by column header click
   --------------------------------------------------------------- */
function setupSortHeaders() {
  const colMap = {
    0: "timestamp", 1: "source_ip", 9: "packet_rate", 10: "prediction", 11: "confidence"
  };
  document.querySelectorAll("#traffic-table thead th").forEach((th, i) => {
    if (colMap[i]) {
      th.style.cursor = "pointer";
      th.addEventListener("click", () => {
        if (_sortKey === colMap[i]) _sortAsc = !_sortAsc;
        else { _sortKey = colMap[i]; _sortAsc = false; }
        document.querySelectorAll("#traffic-table thead th").forEach(h => h.classList.remove("sort-asc", "sort-desc"));
        th.classList.add(_sortAsc ? "sort-asc" : "sort-desc");
        applyFilters();
      });
    }
  });
}

/* ---------------------------------------------------------------
   Auto-refresh toggle
   --------------------------------------------------------------- */
function toggleAutoRefresh(btn) {
  _autoRefresh = !_autoRefresh;
  if (_autoRefresh) {
    btn.classList.remove("btn-ghost");
    btn.classList.add("btn-primary");
    btn.innerHTML = '<i class="fa-solid fa-rotate-right"></i> Auto ON';
    _pollTimer = setInterval(refresh, CONFIG.POLL_INTERVAL);
    btn.setAttribute("aria-checked", "true");
  } else {
    btn.classList.remove("btn-primary");
    btn.classList.add("btn-ghost");
    btn.innerHTML = '<i class="fa-solid fa-rotate-right"></i> Auto OFF';
    clearInterval(_pollTimer);
    btn.setAttribute("aria-checked", "false");
  }
}

/* ---------------------------------------------------------------
   Init
   --------------------------------------------------------------- */
(function init() {
  document.getElementById("global-refresh")?.addEventListener("click", refresh);
  document.getElementById("traffic-refresh-btn")?.addEventListener("click", refresh);
  document.getElementById("traffic-search")?.addEventListener("input", debounce(applyFilters, 250));
  document.getElementById("traffic-prediction-filter")?.addEventListener("change", applyFilters);
  document.getElementById("traffic-protocol-filter")?.addEventListener("change", applyFilters);
  document.getElementById("traffic-limit")?.addEventListener("change", refresh);

  const autoBtn = document.getElementById("traffic-auto-refresh");
  if (autoBtn) autoBtn.addEventListener("click", () => toggleAutoRefresh(autoBtn));

  document.getElementById("sidebar-toggle")?.addEventListener("click", () => {
    const s = document.getElementById("sidebar");
    s?.classList.toggle("open");
  });

  setupSortHeaders();
  refresh();
})();
