/**
 * js/devices.js
 * =============
 * IoT Devices page controller.
 * Handles: device table, search/filter/sort, pagination, detail modal, block/unblock.
 */

let _allDevices = [];
let _filteredDevices = [];
let _currentPage = 1;
const PAGE_SIZE = CONFIG.TABLE_PAGE_SIZE;
let _pollTimer = null;
let _modalResolve = null;

/* ---------------------------------------------------------------
   Shared helpers (duplicated from dashboard to keep pages independent)
   --------------------------------------------------------------- */
function showToast(type, title, msg, duration = 4000) {
  const icons = { success: "fa-circle-check", error: "fa-circle-xmark", warning: "fa-triangle-exclamation", info: "fa-circle-info" };
  const container = document.getElementById("toast-container");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.setAttribute("role", "alert");
  toast.innerHTML = `
    <i class="fa-solid ${icons[type] || icons.info} toast-icon" aria-hidden="true"></i>
    <div class="toast-body">
      <div class="toast-title">${escapeHtml(title)}</div>
      ${msg ? `<div class="toast-msg">${escapeHtml(msg)}</div>` : ""}
    </div>
    <button class="toast-close" aria-label="Dismiss">&times;</button>`;
  toast.querySelector(".toast-close").onclick = () => { toast.classList.add("removing"); toast.addEventListener("animationend", () => toast.remove(), { once: true }); };
  container.appendChild(toast);
  if (duration > 0) setTimeout(() => { if (toast.parentNode) { toast.classList.add("removing"); toast.addEventListener("animationend", () => toast.remove(), { once: true }); } }, duration);
}

function showConfirmModal(title, body, confirmLabel = "Confirm") {
  return new Promise(resolve => {
    _modalResolve = resolve;
    const modal = document.getElementById("confirm-modal");
    if (!modal) { resolve(false); return; }
    const t = document.getElementById("modal-title");
    const b = document.getElementById("modal-body");
    const c = document.getElementById("modal-confirm");
    if (t) t.textContent = title;
    if (b) b.textContent = body;
    if (c) c.textContent = confirmLabel;
    modal.classList.remove("hidden");
  });
}
function closeConfirmModal() {
  document.getElementById("confirm-modal")?.classList.add("hidden");
}

/* ---------------------------------------------------------------
   Header
   --------------------------------------------------------------- */
function initHeader() {
  document.getElementById("global-refresh")?.addEventListener("click", refresh);
  document.getElementById("sidebar-toggle")?.addEventListener("click", toggleSidebar);
  document.getElementById("modal-confirm")?.addEventListener("click", () => { closeConfirmModal(); if (_modalResolve) { _modalResolve(true); _modalResolve = null; } });
  document.getElementById("modal-cancel")?.addEventListener("click", () => { closeConfirmModal(); if (_modalResolve) { _modalResolve(false); _modalResolve = null; } });
}

function toggleSidebar() {
  const s = document.getElementById("sidebar");
  if (!s) return;
  const open = s.classList.toggle("open");
  let ov = document.getElementById("sidebar-overlay");
  if (open) {
    if (!ov) { ov = document.createElement("div"); ov.id = "sidebar-overlay"; ov.className = "sidebar-overlay"; ov.onclick = toggleSidebar; document.body.appendChild(ov); }
  } else { ov?.remove(); }
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
  const t = document.getElementById("last-updated-time");
  if (t) t.textContent = formatTimeShort(new Date().toISOString());
}

/* ---------------------------------------------------------------
   Devices Table
   --------------------------------------------------------------- */
function renderDevicesTable() {
  const tbody = document.getElementById("devices-tbody");
  if (!tbody) return;

  const start = (_currentPage - 1) * PAGE_SIZE;
  const page = _filteredDevices.slice(start, start + PAGE_SIZE);

  const label = document.getElementById("device-count-label");
  if (label) label.textContent = `${_filteredDevices.length} device${_filteredDevices.length !== 1 ? "s" : ""}`;

  if (!_filteredDevices.length) {
    tbody.innerHTML = `<tr><td colspan="8">
      <div class="empty-state">
        <i class="fa-solid fa-microchip" aria-hidden="true"></i>
        <h3>No Devices Found</h3>
        <p>No devices match the current filter, or no devices are registered yet.</p>
      </div></td></tr>`;
    renderPagination(0);
    return;
  }

  tbody.innerHTML = page.map(d => {
    const status = (d.status || "active").toLowerCase();
    const statusCls = getStatusClass(status);
    const prediction = d.last_prediction || "—";
    const predCls = prediction === "DDOS" ? "badge-danger" : prediction === "NORMAL" ? "badge-success" : "badge-secondary";
    const lastSeen = formatTimestamp(d.last_seen);
    const packetRate = d.packet_rate != null ? formatRate(d.packet_rate) : "—";
    const blocked = status === "blocked";

    return `<tr>
      <td class="td-mono">${escapeHtml(d.device_id || "—")}</td>
      <td class="td-ip">${escapeHtml(d.ip_address || "—")}</td>
      <td class="td-mono td-muted">${escapeHtml(d.mac_address || "—")}</td>
      <td><span class="status-pill ${statusCls}"><span class="status-dot"></span>${escapeHtml(status.toUpperCase())}</span></td>
      <td class="td-time">${escapeHtml(lastSeen)}</td>
      <td>${prediction !== "—" ? `<span class="badge ${predCls}">${escapeHtml(prediction)}</span>` : "—"}</td>
      <td class="td-muted">${escapeHtml(packetRate)}</td>
      <td class="td-actions">
        <button class="btn btn-ghost btn-sm" onclick="openDeviceModal('${escapeHtml(d.device_id)}')" title="View details">
          <i class="fa-solid fa-eye" aria-hidden="true"></i>
        </button>
        ${blocked
          ? `<button class="btn btn-ghost btn-sm" onclick="unblockDevice('${escapeHtml(d.ip_address)}')" title="Unblock">
               <i class="fa-solid fa-lock-open" aria-hidden="true"></i>
             </button>`
          : `<button class="btn btn-danger btn-sm" onclick="blockDevice('${escapeHtml(d.ip_address || d.device_id)}')" title="Block">
               <i class="fa-solid fa-ban" aria-hidden="true"></i>
             </button>`}
      </td>
    </tr>`;
  }).join("");

  renderPagination(_filteredDevices.length);
}

function renderPagination(total) {
  const pages = Math.ceil(total / PAGE_SIZE);
  const container = document.getElementById("devices-pagination");
  if (!container) return;
  if (pages <= 1) { container.innerHTML = ""; return; }
  let html = `<span style="margin-right:0.5rem;color:var(--text-secondary)">Page ${_currentPage} of ${pages}</span>`;
  html += `<button class="page-btn" onclick="changePage(${_currentPage - 1})" ${_currentPage <= 1 ? "disabled" : ""} aria-label="Previous page">‹</button>`;
  for (let i = 1; i <= pages; i++) {
    if (i === _currentPage || i === 1 || i === pages || Math.abs(i - _currentPage) <= 1) {
      html += `<button class="page-btn ${i === _currentPage ? "active" : ""}" onclick="changePage(${i})">${i}</button>`;
    } else if (Math.abs(i - _currentPage) === 2) {
      html += `<span style="color:var(--text-muted)">…</span>`;
    }
  }
  html += `<button class="page-btn" onclick="changePage(${_currentPage + 1})" ${_currentPage >= pages ? "disabled" : ""} aria-label="Next page">›</button>`;
  container.innerHTML = html;
}

function changePage(p) {
  const pages = Math.ceil(_filteredDevices.length / PAGE_SIZE);
  _currentPage = Math.max(1, Math.min(p, pages));
  renderDevicesTable();
}

/* ---------------------------------------------------------------
   Search / Filter / Sort
   --------------------------------------------------------------- */
function applyFilters() {
  const search = (document.getElementById("device-search")?.value || "").toLowerCase();
  const statusFilter = document.getElementById("device-status-filter")?.value || "";
  const sort = document.getElementById("device-sort")?.value || "last_seen";

  _filteredDevices = _allDevices.filter(d => {
    const matchesSearch = !search ||
      (d.device_id || "").toLowerCase().includes(search) ||
      (d.ip_address || "").toLowerCase().includes(search) ||
      (d.mac_address || "").toLowerCase().includes(search);
    const matchesStatus = !statusFilter || (d.status || "active").toLowerCase() === statusFilter.toLowerCase();
    return matchesSearch && matchesStatus;
  });

  _filteredDevices.sort((a, b) => {
    if (sort === "device_id") return (a.device_id || "").localeCompare(b.device_id || "");
    if (sort === "ip_address") return (a.ip_address || "").localeCompare(b.ip_address || "");
    // Default: last seen (most recent first)
    return new Date(b.last_seen || 0) - new Date(a.last_seen || 0);
  });

  _currentPage = 1;
  renderDevicesTable();
}

/* ---------------------------------------------------------------
   Device Detail Modal
   --------------------------------------------------------------- */
async function openDeviceModal(deviceId) {
  const modal = document.getElementById("device-modal");
  if (!modal) return;
  modal.classList.remove("hidden");

  const titleEl = document.getElementById("device-modal-title");
  if (titleEl) titleEl.textContent = deviceId;

  // Find device in state
  const device = _allDevices.find(d => d.device_id === deviceId);
  if (!device) return;

  // Fill detail fields
  const fields = {
    "detail-ip": device.ip_address,
    "detail-mac": device.mac_address,
    "detail-status": device.status,
    "detail-last-seen": formatTimestamp(device.last_seen),
    "detail-packet-rate": device.packet_rate != null ? formatRate(device.packet_rate) : "—",
    "detail-protocol": device.protocol || "—",
  };
  Object.entries(fields).forEach(([id, val]) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val || "—";
  });

  // Block/unblock buttons
  const blocked = (device.status || "").toLowerCase() === "blocked";
  const blockBtn = document.getElementById("device-block-btn");
  const unblockBtn = document.getElementById("device-unblock-btn");
  if (blockBtn) { blockBtn.style.display = blocked ? "none" : ""; blockBtn.onclick = () => blockDevice(device.ip_address); }
  if (unblockBtn) { unblockBtn.style.display = blocked ? "" : "none"; }

  // Load predictions
  const predsEl = document.getElementById("device-predictions-list");
  if (predsEl) predsEl.innerHTML = '<div style="color:var(--text-muted);font-size:0.8rem">Loading…</div>';

  const detRes = await getDetections({ limit: 10 });
  if (predsEl) {
    if (detRes.ok) {
      const preds = (detRes.data?.detections || [])
        .filter(d => d.source_ip === device.ip_address)
        .slice(0, 5);
      if (!preds.length) {
        predsEl.innerHTML = '<div style="color:var(--text-muted);font-size:0.8rem">No recent predictions for this device.</div>';
      } else {
        predsEl.innerHTML = preds.map(p => `
          <div style="display:flex;justify-content:space-between;align-items:center;padding:0.35rem 0;border-bottom:1px solid var(--border-light);font-size:0.78rem">
            <span class="badge ${getPredictionClass(p.prediction)}">${escapeHtml(p.prediction || "—")}</span>
            <span style="color:var(--text-secondary)">${formatPercentage(p.confidence)}</span>
            <span class="td-time">${formatTimestamp(p.predicted_at)}</span>
          </div>`).join("");
      }
    } else {
      predsEl.innerHTML = '<div style="color:var(--text-muted);font-size:0.8rem">Could not load predictions.</div>';
    }
  }
}

/* ---------------------------------------------------------------
   Block / Unblock
   --------------------------------------------------------------- */
async function blockDevice(ip) {
  if (!ip) return;
  const confirmed = await showConfirmModal("Block Device", `Block all traffic from ${ip}? (DEMO MODE: simulated)`, "Block");
  if (!confirmed) return;
  const res = await mitigateSource(ip);
  if (res.ok && res.data?.success) {
    showToast("success", res.data.simulated ? "Simulated" : "Blocked", `Block rule for ${ip}.`);
    closeDeviceModal();
    refresh();
  } else {
    showToast("error", "Block Failed", res.error || "Unknown error");
  }
}

async function unblockDevice(ip) {
  showToast("info", "Note", "Unblock is not yet supported by the backend API.");
}

function closeDeviceModal() {
  document.getElementById("device-modal")?.classList.add("hidden");
}

/* ---------------------------------------------------------------
   Main refresh
   --------------------------------------------------------------- */
async function refresh() {
  const tbody = document.getElementById("devices-tbody");

  const health = await getHealth();
  updateHeader(health.ok, undefined);
  if (!health.ok) { if (tbody) tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state"><i class="fa-solid fa-plug-circle-xmark"></i><h3>Backend Unavailable</h3><p>${escapeHtml(health.error)}</p></div></td></tr>`; return; }

  const [statusRes, devicesRes] = await Promise.all([getSystemStatus(), getDevices()]);

  if (statusRes.ok) updateHeader(true, statusRes.data?.demo_mode);

  if (devicesRes.ok) {
    _allDevices = devicesRes.data?.devices || [];
    applyFilters();
  } else {
    if (tbody) tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state"><i class="fa-solid fa-circle-xmark"></i><h3>Could Not Load Devices</h3><p>${escapeHtml(devicesRes.error)}</p></div></td></tr>`;
  }
}

/* ---------------------------------------------------------------
   Init
   --------------------------------------------------------------- */
(function init() {
  initHeader();

  // Filter listeners
  document.getElementById("device-search")?.addEventListener("input", debounce(applyFilters, 250));
  document.getElementById("device-status-filter")?.addEventListener("change", applyFilters);
  document.getElementById("device-sort")?.addEventListener("change", applyFilters);

  // Modal close
  document.getElementById("device-modal-close")?.addEventListener("click", closeDeviceModal);
  document.getElementById("device-modal")?.addEventListener("click", e => { if (e.target === e.currentTarget) closeDeviceModal(); });

  refresh();
  _pollTimer = setInterval(refresh, STATE_POLL || CONFIG.POLL_INTERVAL);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) clearInterval(_pollTimer);
    else { _pollTimer = setInterval(refresh, STATE_POLL || CONFIG.POLL_INTERVAL); refresh(); }
  });
})();

const STATE_POLL = CONFIG.POLL_INTERVAL;
