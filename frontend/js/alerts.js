/**
 * js/alerts.js
 * ============
 * Detections & Alerts page controller.
 */

let _allAlerts = [];
let _filteredAlerts = [];
let _allDetections = [];
let _filteredDetections = [];
let _alertPage = 1;
let _detPage = 1;
const PAGE_SIZE = CONFIG.TABLE_PAGE_SIZE;
let _selectedAlertForMitigate = null;

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
   KPIs
   --------------------------------------------------------------- */
function updateAlertKPIs(alerts, detections) {
  const total = (alerts || []).length;
  const high = (alerts || []).filter(a => ["HIGH","CRITICAL"].includes((a.severity || "").toUpperCase())).length;
  const open = (alerts || []).filter(a => (a.status || "open").toLowerCase() === "open").length;
  const ddos = (detections || []).filter(d => d.prediction === "DDOS").length;

  setEl("kpi-total-alerts", total || "—");
  setEl("kpi-high-alerts", high || "—");
  setEl("kpi-open-alerts", open || "—");
  setEl("kpi-ddos-count", ddos || "—");
}

function setEl(id, v) { const e = document.getElementById(id); if (e) e.textContent = v; }

/* ---------------------------------------------------------------
   Alerts Table
   --------------------------------------------------------------- */
function renderAlertsTable() {
  const tbody = document.getElementById("alerts-tbody");
  if (!tbody) return;
  const start = (_alertPage - 1) * PAGE_SIZE;
  const page = _filteredAlerts.slice(start, start + PAGE_SIZE);

  const label = document.getElementById("alert-count-label");
  if (label) label.textContent = `${_filteredAlerts.length} alert${_filteredAlerts.length !== 1 ? "s" : ""}`;

  if (!_filteredAlerts.length) {
    tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state">
      <i class="fa-solid fa-bell-slash" aria-hidden="true"></i>
      <h3>No Alerts</h3>
      <p>No security alerts match the current filter. This is a good sign!</p>
    </div></td></tr>`;
    renderAlertsPagination(0);
    return;
  }

  tbody.innerHTML = page.map(a => {
    const sevCls = getSeverityClass(a.severity || "LOW");
    const status = a.status || "open";
    return `<tr>
      <td class="td-time">${escapeHtml(formatTimestamp(a.created_at))}</td>
      <td class="td-ip">${escapeHtml(a.source_ip || "—")}</td>
      <td><span class="badge badge-danger">${escapeHtml(a.alert_type || "ALERT")}</span></td>
      <td><span class="badge ${sevCls}">${escapeHtml((a.severity || "LOW").toUpperCase())}</span></td>
      <td class="td-muted">${escapeHtml(a.device_id || "—")}</td>
      <td class="td-muted" title="${escapeHtml(a.message || "")}" style="max-width:200px">${escapeHtml((a.message || "").substring(0, 60))}${(a.message || "").length > 60 ? "…" : ""}</td>
      <td><span class="badge ${status === 'open' ? 'badge-warning' : 'badge-secondary'}">${escapeHtml(status.toUpperCase())}</span></td>
      <td class="td-actions">
        <button class="btn btn-ghost btn-sm" onclick="openAlertDetail(${escapeHtml(JSON.stringify(a))})" title="View">
          <i class="fa-solid fa-eye" aria-hidden="true"></i>
        </button>
        ${a.source_ip ? `<button class="btn btn-danger btn-sm" onclick="mitigateAlert('${escapeHtml(a.source_ip)}')" title="Mitigate">
          <i class="fa-solid fa-ban" aria-hidden="true"></i>
        </button>` : ""}
      </td>
    </tr>`;
  }).join("");

  renderAlertsPagination(_filteredAlerts.length);
}

function renderAlertsPagination(total) {
  renderPagination("alerts-pagination", total, _alertPage, p => { _alertPage = p; renderAlertsTable(); });
}

function renderPagination(containerId, total, current, onChange) {
  const pages = Math.ceil(total / PAGE_SIZE);
  const c = document.getElementById(containerId);
  if (!c) return;
  if (pages <= 1) { c.innerHTML = ""; return; }
  let html = `<span style="margin-right:0.5rem;color:var(--text-secondary)">Page ${current} of ${pages}</span>`;
  html += `<button class="page-btn" onclick="paginateChange('${containerId}',${current - 1})" ${current <= 1 ? "disabled" : ""}>‹</button>`;
  for (let i = 1; i <= pages; i++) {
    if (i === 1 || i === pages || Math.abs(i - current) <= 1)
      html += `<button class="page-btn ${i === current ? "active" : ""}" onclick="paginateChange('${containerId}',${i})">${i}</button>`;
    else if (Math.abs(i - current) === 2)
      html += `<span style="color:var(--text-muted)">…</span>`;
  }
  html += `<button class="page-btn" onclick="paginateChange('${containerId}',${current + 1})" ${current >= pages ? "disabled" : ""}>›</button>`;
  c.innerHTML = html;
}

// Global paginateChange needed for inline onclick
window.paginateChange = function(containerId, p) {
  if (containerId === "alerts-pagination") { _alertPage = p; renderAlertsTable(); }
  if (containerId === "detections-pagination") { _detPage = p; renderDetectionsTable(); }
};

/* ---------------------------------------------------------------
   Alert Detail Modal
   --------------------------------------------------------------- */
window.openAlertDetail = function(alert) {
  const modal = document.getElementById("alert-modal");
  if (!modal) return;
  _selectedAlertForMitigate = alert.source_ip;
  const title = document.getElementById("alert-modal-title");
  if (title) title.textContent = `Alert: ${alert.alert_type || "ALERT"}`;
  const body = document.getElementById("alert-modal-body");
  if (body) body.innerHTML = `
    <div style="display:grid;grid-template-columns:auto 1fr;gap:0.4rem 1rem;font-size:0.82rem;margin-bottom:0.75rem">
      <span style="color:var(--text-muted)">Time</span>    <span>${escapeHtml(formatTimestamp(alert.created_at))}</span>
      <span style="color:var(--text-muted)">Source IP</span><span class="td-ip">${escapeHtml(alert.source_ip || "—")}</span>
      <span style="color:var(--text-muted)">Device</span>   <span>${escapeHtml(alert.device_id || "—")}</span>
      <span style="color:var(--text-muted)">Type</span>     <span><span class="badge badge-danger">${escapeHtml(alert.alert_type || "—")}</span></span>
      <span style="color:var(--text-muted)">Severity</span> <span><span class="badge ${getSeverityClass(alert.severity)}">${escapeHtml((alert.severity || "").toUpperCase())}</span></span>
      <span style="color:var(--text-muted)">Status</span>   <span>${escapeHtml(alert.status || "open")}</span>
    </div>
    <div style="font-size:0.82rem;color:var(--text-secondary);margin-top:0.5rem">
      <strong style="color:var(--text-primary)">Message:</strong><br>
      ${escapeHtml(alert.message || "—")}
    </div>`;
  const mitBtn = document.getElementById("alert-mitigate-btn");
  if (mitBtn) { mitBtn.style.display = alert.source_ip ? "" : "none"; }
  modal.classList.remove("hidden");
};

window.mitigateAlert = async function(ip) {
  if (!ip) return;
  document.getElementById("alert-modal")?.classList.add("hidden");
  if (!confirm(`Block traffic from ${ip}? (DEMO MODE: simulated)`)) return;
  const res = await mitigateSource(ip);
  if (res.ok && res.data?.success) {
    showToast("success", res.data.simulated ? "Simulated" : "Blocked", `Rule for ${ip}`);
  } else {
    showToast("error", "Failed", res.error || "Unknown error");
  }
};

/* ---------------------------------------------------------------
   Detections Table
   --------------------------------------------------------------- */
function renderDetectionsTable() {
  const tbody = document.getElementById("detections-tbody");
  if (!tbody) return;
  const start = (_detPage - 1) * PAGE_SIZE;
  const page = _filteredDetections.slice(start, start + PAGE_SIZE);
  const label = document.getElementById("detections-count-label");
  if (label) label.textContent = `${_filteredDetections.length} records`;

  if (!_filteredDetections.length) {
    tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state">
      <i class="fa-solid fa-brain" aria-hidden="true"></i>
      <h3>No Detection Records</h3>
      <p>No ML predictions recorded yet. Send traffic to /api/predict or start the demo.</p>
    </div></td></tr>`;
    renderPagination("detections-pagination", 0, 1, () => {});
    return;
  }

  tbody.innerHTML = page.map(d => {
    const pred = d.prediction || "—";
    const predCls = pred === "DDOS" ? "badge-danger" : pred === "NORMAL" ? "badge-success" : "badge-secondary";
    return `<tr>
      <td class="td-time">${escapeHtml(formatTimestamp(d.predicted_at))}</td>
      <td class="td-ip">${escapeHtml(d.source_ip || "—")}</td>
      <td class="td-ip" style="color:var(--text-secondary)">${escapeHtml(d.destination_ip || "—")}</td>
      <td class="td-mono td-muted">${escapeHtml(d.protocol || "—")}</td>
      <td>${pred !== "—" ? `<span class="badge ${predCls}"><i class="fa-solid ${pred === 'DDOS' ? 'fa-virus' : 'fa-check'}" aria-hidden="true"></i> ${escapeHtml(pred)}</span>` : "—"}</td>
      <td class="td-muted">${d.confidence != null ? escapeHtml(formatPercentage(d.confidence)) : "—"}</td>
      <td class="td-muted">${d.probability != null ? escapeHtml(formatPercentage(d.probability)) : "—"}</td>
    </tr>`;
  }).join("");

  renderPagination("detections-pagination", _filteredDetections.length, _detPage, p => { _detPage = p; renderDetectionsTable(); });
}

/* ---------------------------------------------------------------
   Filters
   --------------------------------------------------------------- */
function applyAlertFilters() {
  const search = (document.getElementById("alert-search")?.value || "").toLowerCase();
  const sev = document.getElementById("alert-severity-filter")?.value || "";
  const status = document.getElementById("alert-status-filter")?.value || "";
  const type = document.getElementById("alert-type-filter")?.value || "";

  _filteredAlerts = _allAlerts.filter(a => {
    const ms = !search || (a.source_ip || "").toLowerCase().includes(search) || (a.message || "").toLowerCase().includes(search);
    const msev = !sev || (a.severity || "").toUpperCase() === sev;
    const mst = !status || (a.status || "open").toLowerCase() === status;
    const mtype = !type || (a.alert_type || "").toUpperCase() === type.toUpperCase();
    return ms && msev && mst && mtype;
  });
  _alertPage = 1;
  renderAlertsTable();
}

/* ---------------------------------------------------------------
   Main refresh
   --------------------------------------------------------------- */
async function refresh() {
  const health = await getHealth();
  updateHeader(health.ok, undefined);
  if (!health.ok) {
    ["alerts-tbody","detections-tbody"].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.innerHTML = `<tr><td colspan="13"><div class="empty-state"><i class="fa-solid fa-plug-circle-xmark"></i><h3>Backend Unavailable</h3><p>${escapeHtml(health.error)}</p></div></td></tr>`;
    });
    return;
  }

  const [statusRes, alertsRes, detRes] = await Promise.all([
    getSystemStatus(),
    getAlerts({ limit: 200 }),
    getDetections({ limit: 200 }),
  ]);

  if (statusRes.ok) updateHeader(true, statusRes.data?.demo_mode);

  const alerts = alertsRes.ok ? (alertsRes.data?.alerts || []) : [];
  const detections = detRes.ok ? (detRes.data?.detections || []) : [];

  _allAlerts = alerts;
  _filteredAlerts = [...alerts];
  _allDetections = detections;
  _filteredDetections = [...detections];

  updateAlertKPIs(alerts, detections);
  renderAlertsTable();
  renderDetectionsTable();
}

/* ---------------------------------------------------------------
   Init
   --------------------------------------------------------------- */
(function init() {
  document.getElementById("global-refresh")?.addEventListener("click", refresh);
  document.getElementById("alerts-refresh-btn")?.addEventListener("click", refresh);
  document.getElementById("alert-search")?.addEventListener("input", debounce(applyAlertFilters, 250));
  document.getElementById("alert-severity-filter")?.addEventListener("change", applyAlertFilters);
  document.getElementById("alert-status-filter")?.addEventListener("change", applyAlertFilters);
  document.getElementById("alert-type-filter")?.addEventListener("change", applyAlertFilters);

  document.getElementById("sidebar-toggle")?.addEventListener("click", () => document.getElementById("sidebar")?.classList.toggle("open"));

  // Alert modal close
  document.getElementById("alert-modal-close")?.addEventListener("click", () => document.getElementById("alert-modal")?.classList.add("hidden"));
  document.getElementById("alert-modal")?.addEventListener("click", e => { if (e.target === e.currentTarget) e.currentTarget.classList.add("hidden"); });
  document.getElementById("alert-mitigate-btn")?.addEventListener("click", () => { if (_selectedAlertForMitigate) mitigateAlert(_selectedAlertForMitigate); });

  // Confirm modal
  document.getElementById("modal-cancel")?.addEventListener("click", () => document.getElementById("confirm-modal")?.classList.add("hidden"));

  refresh();
  setInterval(refresh, CONFIG.POLL_INTERVAL);
})();
