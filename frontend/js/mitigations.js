/**
 * js/mitigations.js
 * =================
 * Mitigations page controller.
 * Clearly differentiates SIMULATED vs REAL mitigation actions.
 */

let _allMitigations = [];
let _filtered = [];
let _currentPage = 1;
const PAGE_SIZE = CONFIG.TABLE_PAGE_SIZE;

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
function updateKPIs() {
  const total = _allMitigations.length;
  const successful = _allMitigations.filter(m => m.success).length;
  const failed = _allMitigations.filter(m => !m.success).length;
  const simulated = _allMitigations.filter(m => m.simulated).length;
  const setEl = (id, v) => { const e = document.getElementById(id); if (e) e.textContent = v; };
  setEl("kpi-total-mit", total || "—");
  setEl("kpi-success-mit", successful || "—");
  setEl("kpi-failed-mit", failed || "—");
  setEl("kpi-simulated-mit", simulated || "—");
}

/* ---------------------------------------------------------------
   Table
   --------------------------------------------------------------- */
function renderTable() {
  const tbody = document.getElementById("mit-tbody");
  if (!tbody) return;
  const start = (_currentPage - 1) * PAGE_SIZE;
  const page = _filtered.slice(start, start + PAGE_SIZE);
  const label = document.getElementById("mit-count-label");
  if (label) label.textContent = `${_filtered.length} action${_filtered.length !== 1 ? "s" : ""}`;

  if (!_filtered.length) {
    tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state">
      <i class="fa-solid fa-shield-check" aria-hidden="true"></i>
      <h3>No Mitigation Actions</h3>
      <p>No mitigation rules have been applied yet. Trigger via the decision engine or manually.</p>
    </div></td></tr>`;
    renderPagination(0);
    return;
  }

  tbody.innerHTML = page.map(m => {
    const simulated = m.simulated;
    const success = m.success;
    const action = (m.action || "BLOCK").toUpperCase();

    // SIMULATED vs REAL must be unmistakably different
    const modeBadge = simulated
      ? `<span class="badge badge-warning" title="No actual OVS rule was installed">
           <i class="fa-solid fa-flask" aria-hidden="true"></i> SIMULATED
         </span>`
      : `<span class="badge badge-success">
           <i class="fa-solid fa-shield-check" aria-hidden="true"></i> REAL
         </span>`;

    const successBadge = success
      ? `<span class="badge badge-success"><i class="fa-solid fa-check" aria-hidden="true"></i> Yes</span>`
      : `<span class="badge badge-danger"><i class="fa-solid fa-xmark" aria-hidden="true"></i> No</span>`;

    return `<tr ${simulated ? 'style="opacity:0.9"' : ""}>
      <td class="td-time">${escapeHtml(formatTimestamp(m.created_at))}</td>
      <td class="td-ip">${escapeHtml(m.source_ip || "—")}</td>
      <td class="td-muted">${escapeHtml(m.device_id || "—")}</td>
      <td><span class="badge ${action === 'BLOCK' ? 'badge-danger' : 'badge-info'}">${escapeHtml(action)}</span></td>
      <td class="td-mono td-muted" title="${escapeHtml(m.rule_id || "")}">${m.rule_id ? escapeHtml(String(m.rule_id).substring(0, 20)) : "—"}</td>
      <td class="td-muted" title="${escapeHtml(m.reason || "")}">${escapeHtml((m.reason || "—").substring(0, 40))}${(m.reason || "").length > 40 ? "…" : ""}</td>
      <td>${successBadge}</td>
      <td>${modeBadge}</td>
    </tr>`;
  }).join("");

  renderPagination(_filtered.length);
}

function renderPagination(total) {
  const pages = Math.ceil(total / PAGE_SIZE);
  const c = document.getElementById("mit-pagination");
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

window.changePage = function(p) {
  const pages = Math.ceil(_filtered.length / PAGE_SIZE);
  _currentPage = Math.max(1, Math.min(p, pages));
  renderTable();
};

/* ---------------------------------------------------------------
   Filters
   --------------------------------------------------------------- */
function applyFilters() {
  const search = (document.getElementById("mit-search")?.value || "").toLowerCase();
  const action = document.getElementById("mit-action-filter")?.value || "";
  const sim = document.getElementById("mit-sim-filter")?.value || "";

  _filtered = _allMitigations.filter(m => {
    const ms = !search || (m.source_ip || "").toLowerCase().includes(search) || (m.device_id || "").toLowerCase().includes(search);
    const ma = !action || (m.action || "").toUpperCase() === action;
    const msim = !sim || (sim === "1" ? m.simulated : !m.simulated);
    return ms && ma && msim;
  });

  _currentPage = 1;
  renderTable();
}

/* ---------------------------------------------------------------
   Manual mitigation modal
   --------------------------------------------------------------- */
function openManualMitModal() {
  const modal = document.getElementById("manual-mit-modal");
  const ip = document.getElementById("manual-mit-ip");
  const err = document.getElementById("manual-mit-error");
  if (ip) ip.value = "";
  if (err) { err.textContent = ""; err.style.display = "none"; }
  modal?.classList.remove("hidden");
  ip?.focus();
}

function closeManualMitModal() {
  document.getElementById("manual-mit-modal")?.classList.add("hidden");
}

async function submitManualMitigation() {
  const ipEl = document.getElementById("manual-mit-ip");
  const errEl = document.getElementById("manual-mit-error");
  const ip = (ipEl?.value || "").trim();

  if (!ip) {
    if (errEl) { errEl.textContent = "IP address is required."; errEl.style.display = "block"; }
    return;
  }
  if (!isValidIPv4(ip)) {
    if (errEl) { errEl.textContent = `"${ip}" is not a valid IPv4 address.`; errEl.style.display = "block"; }
    return;
  }

  const btn = document.getElementById("manual-mit-confirm");
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Blocking…'; }

  const res = await mitigateSource(ip);

  if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-ban"></i> Block IP'; }

  if (res.ok && res.data?.success) {
    const isSimulated = res.data.simulated;
    showToast("success",
      isSimulated ? "Mitigation Simulated" : "Mitigation Applied",
      isSimulated
        ? `Simulated block rule for ${ip} (DEMO MODE — no real OVS rule installed)`
        : `Real DROP rule installed for ${ip} via Ryu/OVS`
    );
    closeManualMitModal();
    setTimeout(refresh, 800);
  } else {
    showToast("error", "Mitigation Failed", res.error || "Unknown error");
    if (errEl) { errEl.textContent = res.error || "Server error."; errEl.style.display = "block"; }
  }
}

/* ---------------------------------------------------------------
   Main refresh
   --------------------------------------------------------------- */
async function refresh() {
  const health = await getHealth();
  updateHeader(health.ok, undefined);
  if (!health.ok) {
    const tbody = document.getElementById("mit-tbody");
    if (tbody) tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state"><i class="fa-solid fa-plug-circle-xmark"></i><h3>Backend Unavailable</h3><p>${escapeHtml(health.error)}</p></div></td></tr>`;
    return;
  }

  const [statusRes, mitRes] = await Promise.all([getSystemStatus(), getMitigations({ limit: 500 })]);

  if (statusRes.ok) {
    updateHeader(true, statusRes.data?.demo_mode);
    // Update simulated note visibility
    const note = document.getElementById("simulated-note");
    if (note) note.style.display = statusRes.data?.demo_mode ? "" : "none";
  }

  if (mitRes.ok) {
    _allMitigations = mitRes.data?.mitigations || [];
    _filtered = [..._allMitigations];
    applyFilters();
    updateKPIs();
  }
}

/* ---------------------------------------------------------------
   Init
   --------------------------------------------------------------- */
(function init() {
  document.getElementById("global-refresh")?.addEventListener("click", refresh);
  document.getElementById("mit-refresh-btn")?.addEventListener("click", refresh);
  document.getElementById("mit-search")?.addEventListener("input", debounce(applyFilters, 250));
  document.getElementById("mit-action-filter")?.addEventListener("change", applyFilters);
  document.getElementById("mit-sim-filter")?.addEventListener("change", applyFilters);
  document.getElementById("manual-mitigate-btn")?.addEventListener("click", openManualMitModal);
  document.getElementById("manual-mit-cancel")?.addEventListener("click", closeManualMitModal);
  document.getElementById("manual-mit-confirm")?.addEventListener("click", submitManualMitigation);
  document.getElementById("manual-mit-modal")?.addEventListener("click", e => { if (e.target === e.currentTarget) closeManualMitModal(); });
  document.getElementById("sidebar-toggle")?.addEventListener("click", () => document.getElementById("sidebar")?.classList.toggle("open"));

  // Allow Enter key in IP field
  document.getElementById("manual-mit-ip")?.addEventListener("keydown", e => { if (e.key === "Enter") submitManualMitigation(); });

  refresh();
  setInterval(refresh, CONFIG.POLL_INTERVAL);
})();
