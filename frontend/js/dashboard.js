/**
 * js/dashboard.js
 * ===============
 * Main dashboard page controller.
 * Handles: KPI cards, traffic chart, distribution chart,
 * system status panel, detection pipeline, recent alerts,
 * suspicious devices, demo start/stop, polling.
 */

/* ---------------------------------------------------------------
   Chart instances (module-level, destroyed on re-init)
   --------------------------------------------------------------- */
let _trafficChart = null;
let _distChart = null;

// Traffic time-series data
const _trafficHistory = { labels: [], normal: [], ddos: [] };

// Polling timer
let _pollTimer = null;

/* ---------------------------------------------------------------
   Toast & Modal (shared across all pages via this module)
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
    <button class="toast-close" aria-label="Dismiss">&times;</button>
  `;
  toast.querySelector(".toast-close").onclick = () => removeToast(toast);
  container.appendChild(toast);
  if (duration > 0) setTimeout(() => removeToast(toast), duration);
}

function removeToast(el) {
  el.classList.add("removing");
  el.addEventListener("animationend", () => el.remove(), { once: true });
}

let _modalResolve = null;
function showConfirmModal(title, body, confirmLabel = "Confirm") {
  return new Promise(resolve => {
    _modalResolve = resolve;
    const modal = document.getElementById("confirm-modal");
    const titleEl = document.getElementById("modal-title");
    const bodyEl = document.getElementById("modal-body");
    const confirmBtn = document.getElementById("modal-confirm");
    if (!modal) { resolve(false); return; }
    if (titleEl) titleEl.textContent = title;
    if (bodyEl) bodyEl.textContent = body;
    if (confirmBtn) confirmBtn.textContent = confirmLabel;
    modal.classList.remove("hidden");
    document.getElementById("modal-confirm")?.focus();
  });
}
function closeModal() {
  document.getElementById("confirm-modal")?.classList.add("hidden");
}

/* ---------------------------------------------------------------
   Header wiring
   --------------------------------------------------------------- */
function initHeader() {
  // API status indicator
  document.getElementById("global-refresh")?.addEventListener("click", refresh);
  document.getElementById("page-refresh-btn")?.addEventListener("click", refresh);

  // Poll interval selector
  const pollSel = document.getElementById("poll-interval");
  if (pollSel) {
    pollSel.value = State.get("pollInterval");
    pollSel.addEventListener("change", () => {
      State.set("pollInterval", Number(pollSel.value));
      restartPolling();
    });
  }

  // Sidebar toggle (mobile)
  document.getElementById("sidebar-toggle")?.addEventListener("click", toggleSidebar);

  // Confirm modal buttons
  document.getElementById("modal-confirm")?.addEventListener("click", () => {
    closeModal();
    if (_modalResolve) { _modalResolve(true); _modalResolve = null; }
  });
  document.getElementById("modal-cancel")?.addEventListener("click", () => {
    closeModal();
    if (_modalResolve) { _modalResolve(false); _modalResolve = null; }
  });
  document.getElementById("confirm-modal")?.addEventListener("click", e => {
    if (e.target === e.currentTarget) { closeModal(); if (_modalResolve) { _modalResolve(false); _modalResolve = null; } }
  });
}

function toggleSidebar() {
  const sidebar = document.getElementById("sidebar");
  if (!sidebar) return;
  const isOpen = sidebar.classList.toggle("open");
  // Create/remove overlay
  let overlay = document.getElementById("sidebar-overlay");
  if (isOpen) {
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.className = "sidebar-overlay";
      overlay.id = "sidebar-overlay";
      overlay.addEventListener("click", toggleSidebar);
      document.body.appendChild(overlay);
    }
  } else {
    overlay?.remove();
  }
}

function updateHeaderStatus(online, demoMode, demoRunning) {
  const dot = document.getElementById("api-dot");
  const txt = document.getElementById("api-status-text");
  const badge = document.getElementById("demo-mode-badge");

  if (dot) { dot.classList.toggle("online", online); dot.classList.toggle("offline", !online); }
  if (txt) txt.textContent = online ? "Connected" : "Offline";
  if (badge) {
    badge.style.display = (demoMode !== undefined) ? "inline-flex" : "none";
    badge.className = demoMode ? "demo-badge" : "demo-badge real-badge";
    badge.innerHTML = demoMode
      ? '<i class="fa-solid fa-flask"></i> DEMO MODE'
      : '<i class="fa-solid fa-circle-check"></i> REAL MODE';
  }
  const timeEl = document.getElementById("last-updated-time");
  if (timeEl) timeEl.textContent = formatTimeShort(new Date().toISOString());
}

/* ---------------------------------------------------------------
   KPI Cards
   --------------------------------------------------------------- */
function updateKPIs(devices, metrics) {
  const devList = devices?.devices || [];
  const total = devList.length;
  const active = devList.filter(d => (d.status || "").toLowerCase() === "active").length;
  const suspicious = devList.filter(d => (d.status || "").toLowerCase() === "suspicious").length;
  const blocked = devList.filter(d => (d.status || "").toLowerCase() === "blocked").length;

  setKPI("kpi-total-devices", total > 0 ? total.toString() : "—");
  setKPI("kpi-active-devices", total > 0 ? active.toString() : "—");
  setKPI("kpi-suspicious", total > 0 ? suspicious.toString() : "0");
  setKPI("kpi-blocked", total > 0 ? blocked.toString() : "0");

  const ml = metrics?.ml || {};
  setKPI("kpi-accuracy", ml.accuracy != null ? formatPercentage(ml.accuracy) : "—");
  setKPI("kpi-fpr", ml.false_positive_rate != null ? formatPercentage(ml.false_positive_rate) : "—");
}

function setKPI(id, val) {
  // Try -val suffix first (the value span inside the KPI card)
  // then fall back to the raw id. This prevents overwriting the
  // card container when both id and id-val exist.
  const el = document.getElementById(id + "-val") || document.getElementById(id);
  if (el) el.textContent = val;
}

/* ---------------------------------------------------------------
   Traffic Chart & Theme Colors
   --------------------------------------------------------------- */
function getChartColors() {
  const isDark = document.documentElement.getAttribute("data-theme") === "dark";
  return {
    ticks: isDark ? "#8b949e" : "#64748B",
    grid: isDark ? "#21262d" : "#E2E8F0",
    legend: isDark ? "#8b949e" : "#475569",
    normalBorder: isDark ? "#10B981" : "#059669",
    normalBg: isDark ? "rgba(16, 185, 129, 0.15)" : "rgba(5, 150, 105, 0.12)",
    ddosBorder: isDark ? "#EF4444" : "#DC2626",
    ddosBg: isDark ? "rgba(239, 68, 68, 0.15)" : "rgba(220, 38, 38, 0.12)"
  };
}

window.addEventListener("themeChanged", () => {
  const colors = getChartColors();
  if (_trafficChart) {
    if (_trafficChart.options.scales.x) {
      _trafficChart.options.scales.x.ticks.color = colors.ticks;
      _trafficChart.options.scales.x.grid.color = colors.grid;
    }
    if (_trafficChart.options.scales.y) {
      _trafficChart.options.scales.y.ticks.color = colors.ticks;
      _trafficChart.options.scales.y.grid.color = colors.grid;
    }
    if (_trafficChart.data.datasets[0]) {
      _trafficChart.data.datasets[0].borderColor = colors.normalBorder;
      _trafficChart.data.datasets[0].backgroundColor = colors.normalBg;
    }
    if (_trafficChart.data.datasets[1]) {
      _trafficChart.data.datasets[1].borderColor = colors.ddosBorder;
      _trafficChart.data.datasets[1].backgroundColor = colors.ddosBg;
    }
    _trafficChart.update();
  }
  if (_distChart) {
    if (_distChart.options.plugins?.legend?.labels) {
      _distChart.options.plugins.legend.labels.color = colors.legend;
    }
    if (_distChart.data.datasets[0]) {
      _distChart.data.datasets[0].backgroundColor = [colors.normalBorder, colors.ddosBorder];
      _distChart.data.datasets[0].borderColor = [colors.normalBorder, colors.ddosBorder];
    }
    _distChart.update();
  }
});

function initTrafficChart() {
  const ctx = document.getElementById("traffic-chart");
  if (!ctx || typeof Chart === "undefined") return;
  if (_trafficChart) { _trafficChart.destroy(); _trafficChart = null; }

  const colors = getChartColors();

  _trafficChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Normal (pkts/s)",
          data: [],
          borderColor: colors.normalBorder,
          backgroundColor: colors.normalBg,
          borderWidth: 2,
          pointRadius: 2,
          tension: 0.3,
          fill: true,
        },
        {
          label: "DDoS (pkts/s)",
          data: [],
          borderColor: colors.ddosBorder,
          backgroundColor: colors.ddosBg,
          borderWidth: 2,
          pointRadius: 2,
          tension: 0.3,
          fill: true,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      animation: { duration: 300 },
      plugins: { legend: { display: false }, tooltip: { mode: "index" } },
      scales: {
        x: {
          ticks: { color: colors.ticks, maxTicksLimit: 8, font: { size: 10 } },
          grid: { color: colors.grid },
        },
        y: {
          beginAtZero: true,
          ticks: { color: colors.ticks, font: { size: 10 } },
          grid: { color: colors.grid },
        },
      },
    },
  });
}

function updateTrafficChart(traffic) {
  if (!_trafficChart) return;
  const flows = traffic?.flows || [];

  // Look at the recent window of flows (latest batch)
  const recentFlows = flows.slice(0, 10);
  const normalFlows = recentFlows.filter(f => f.prediction === "NORMAL" || f.label === 0);
  const ddosFlows = recentFlows.filter(f => f.prediction === "DDOS" || f.label === 1);

  // Measure current average packet rate for each category
  const normalVal = normalFlows.length > 0
    ? Math.round(normalFlows.reduce((sum, f) => sum + (Number(f.packet_rate) || 5), 0) / normalFlows.length)
    : 0;

  const ddosVal = ddosFlows.length > 0
    ? Math.round(ddosFlows.reduce((sum, f) => sum + (Number(f.packet_rate) || 1000), 0) / ddosFlows.length)
    : 0;

  const label = formatTimeShort(new Date().toISOString());

  _trafficHistory.labels.push(label);
  _trafficHistory.normal.push(normalVal);
  _trafficHistory.ddos.push(ddosVal);

  const max = CONFIG.CHART_MAX_POINTS;
  if (_trafficHistory.labels.length > max) {
    _trafficHistory.labels.shift();
    _trafficHistory.normal.shift();
    _trafficHistory.ddos.shift();
  }

  _trafficChart.data.labels = [..._trafficHistory.labels];
  _trafficChart.data.datasets[0].data = [..._trafficHistory.normal];
  _trafficChart.data.datasets[1].data = [..._trafficHistory.ddos];
  _trafficChart.update("none");
}

/* ---------------------------------------------------------------
   Distribution Chart (doughnut)
   --------------------------------------------------------------- */
function initDistChart() {
  const ctx = document.getElementById("dist-chart");
  if (!ctx || typeof Chart === "undefined") return;
  if (_distChart) { _distChart.destroy(); _distChart = null; }

  const colors = getChartColors();

  _distChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Normal", "DDoS"],
      datasets: [{
        data: [1, 0],
        backgroundColor: [colors.normalBorder, colors.ddosBorder],
        borderColor: [colors.normalBorder, colors.ddosBorder],
        borderWidth: 2,
        hoverOffset: 6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "68%",
      animation: { duration: 400 },
      plugins: {
        legend: {
          position: "bottom",
          labels: { color: colors.legend, font: { size: 11 }, padding: 12, boxWidth: 12 },
        },
        tooltip: {
          callbacks: {
            label: ctx => {
              const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
              const pct = total > 0 ? ((ctx.parsed / total) * 100).toFixed(1) : 0;
              return ` ${ctx.label}: ${ctx.parsed} (${pct}%)`;
            },
          },
        },
      },
    },
  });
}

function updateDistChart(traffic) {
  if (!_distChart) return;
  const recent = (traffic?.flows || []).slice(0, 20);
  const normal = recent.filter(f => f.prediction === "NORMAL" || f.label === 0).length;
  const ddos = recent.filter(f => f.prediction === "DDOS" || f.label === 1).length;
  _distChart.data.datasets[0].data = [normal || 0, ddos || 0];
  _distChart.update("none");
}

/* ---------------------------------------------------------------
   System Status Panel
   --------------------------------------------------------------- */
function updateSystemStatusPanel(status) {
  const components = [
    { key: "flask",    label: "Flask API",   icon: "fa-server" },
    { key: "database", label: "Database",    icon: "fa-database" },
    { key: "ml_model", label: "ML Engine",   icon: "fa-brain" },
    { key: "mqtt",     label: "MQTT",        icon: "fa-tower-broadcast" },
    { key: "zeek",     label: "Zeek",        icon: "fa-magnifying-glass-chart" },
    { key: "ryu",      label: "Ryu SDN",     icon: "fa-network-wired" },
    { key: "ovs",      label: "OVS",         icon: "fa-sitemap" },
  ];

  const grid = document.getElementById("system-status-grid");
  if (!grid || !status) return;

  grid.innerHTML = components.map(c => {
    const raw = status[c.key];
    const { label: stLabel, cls } = getComponentStatus(raw);
    return `
      <div class="status-row" id="status-${c.key}">
        <span class="status-row-label">
          <i class="fa-solid ${c.icon}" aria-hidden="true" style="width:14px;margin-right:0.4rem;color:var(--text-muted)"></i>
          ${escapeHtml(c.label)}
        </span>
        <span class="status-pill ${cls}">
          <span class="status-dot"></span>
          ${escapeHtml(stLabel)}
        </span>
      </div>`;
  }).join("");

  // Demo mode row
  const demoHtml = `
    <div class="status-row">
      <span class="status-row-label"><i class="fa-solid fa-flask" style="width:14px;margin-right:0.4rem;color:var(--text-muted)"></i> Mode</span>
      <span class="status-pill ${status.demo_mode ? 'status-suspicious' : 'status-online'}">
        <span class="status-dot"></span>
        ${status.demo_mode ? "DEMO" : "REAL"}
      </span>
    </div>`;
  grid.insertAdjacentHTML("beforeend", demoHtml);
}

/* ---------------------------------------------------------------
   Detection Pipeline Visualization
   --------------------------------------------------------------- */
function updatePipeline(hasDdos, hasMitigation) {
  const el = document.getElementById("pipeline-steps");
  if (!el) return;

  const steps = [
    { label: "IoT Traffic",       icon: "fa-microchip",         cls: "active" },
    { label: "Feature Extraction",icon: "fa-sliders",           cls: "active" },
    { label: "ML Classification", icon: "fa-brain",             cls: "active" },
    { label: hasDdos ? "DDoS Detected" : "Normal Traffic", icon: hasDdos ? "fa-virus" : "fa-check", cls: hasDdos ? "danger" : "success" },
    { label: "Decision Engine",   icon: "fa-scale-balanced",    cls: hasDdos ? "danger" : "" },
    { label: hasMitigation ? "Block Rule Installed" : "Allow Traffic", icon: hasMitigation ? "fa-ban" : "fa-check-circle", cls: hasMitigation ? "danger" : "success" },
  ];

  el.innerHTML = steps.map((s, i) => `
    ${i > 0 ? '<div class="pipeline-arrow"></div>' : ""}
    <div class="pipeline-step ${s.cls || ""}">
      <i class="fa-solid ${s.icon}" aria-hidden="true"></i>
      ${escapeHtml(s.label)}
    </div>
  `).join("");
}

/* ---------------------------------------------------------------
   Recent Alerts mini-list
   --------------------------------------------------------------- */
function updateRecentAlerts(alerts) {
  const list = document.getElementById("recent-alerts-list");
  if (!list) return;

  const items = alerts?.alerts?.slice(0, 5) || [];
  if (!items.length) {
    list.innerHTML = `
      <div class="empty-state" style="padding:1.5rem">
        <i class="fa-solid fa-bell-slash" aria-hidden="true"></i>
        <p>No alerts yet</p>
      </div>`;
    return;
  }

  list.innerHTML = `<div class="alert-mini-list">${items.map(a => {
    const sev = (a.severity || "").toUpperCase();
    const cls = getSeverityClass(sev);
    return `
      <div class="alert-mini-item">
        <i class="fa-solid fa-circle-exclamation alert-icon" style="color:${sev === 'HIGH' || sev === 'CRITICAL' ? 'var(--red)' : 'var(--yellow)'}" aria-hidden="true"></i>
        <div class="alert-mini-info">
          <div class="alert-mini-type">${escapeHtml(a.alert_type || "ALERT")}</div>
          <div class="alert-mini-meta">
            ${escapeHtml(a.source_ip || "—")} &bull;
            ${formatTimestamp(a.created_at)}
            &bull; <span class="badge ${cls}">${escapeHtml(sev)}</span>
          </div>
        </div>
      </div>`;
  }).join("")}</div>
  <div style="padding:0.5rem 0;text-align:right">
    <a href="alerts.html" style="font-size:0.78rem;color:var(--accent)">View all alerts →</a>
  </div>`;
}

/* ---------------------------------------------------------------
   Suspicious Devices mini-list
   --------------------------------------------------------------- */
function updateSuspiciousDevices(devices, detections) {
  const list = document.getElementById("suspicious-devices-list");
  if (!list) return;

  const devList = devices?.devices || [];
  const suspicious = devList.filter(d =>
    (d.status || "").toLowerCase() === "suspicious" ||
    (d.status || "").toLowerCase() === "blocked"
  );

  if (!suspicious.length) {
    // Check if detections show suspicious IPs
    const ddos = (detections?.detections || []).filter(d => d.prediction === "DDOS").slice(0, 3);
    if (!ddos.length) {
      list.innerHTML = `
        <div class="empty-state" style="padding:1.5rem">
          <i class="fa-solid fa-shield-check" aria-hidden="true"></i>
          <p>No suspicious devices</p>
        </div>`;
      return;
    }
    // Show suspicious IPs from predictions
    list.innerHTML = `<div class="suspicious-list">${ddos.map(d => `
      <div class="suspicious-item">
        <div>
          <div class="device-id">${escapeHtml(d.source_ip || "Unknown")}</div>
          <div class="device-ip">via /api/detections</div>
        </div>
        <span class="badge badge-danger"><i class="fa-solid fa-virus"></i> DDOS</span>
        <span class="device-rate" style="margin-left:0">${formatPercentage(d.confidence)}</span>
        <button class="btn btn-danger btn-sm" onclick="triggerMitigate('${escapeHtml(d.source_ip || '')}')">
          <i class="fa-solid fa-ban"></i>
        </button>
      </div>`).join("")}</div>`;
    return;
  }

  list.innerHTML = `<div class="suspicious-list">${suspicious.slice(0, 5).map(d => `
    <div class="suspicious-item">
      <div>
        <div class="device-id">${escapeHtml(d.device_id || "—")}</div>
        <div class="device-ip">${escapeHtml(d.ip_address || "—")}</div>
      </div>
      <span class="badge ${d.status === 'blocked' ? 'badge-danger' : 'badge-warning'}">
        ${escapeHtml((d.status || "").toUpperCase())}
      </span>
      <button class="btn btn-danger btn-sm" onclick="triggerMitigate('${escapeHtml(d.ip_address || '')}')">
        <i class="fa-solid fa-ban"></i>
      </button>
    </div>`).join("")}</div>`;
}

/* ---------------------------------------------------------------
   Demo start/stop
   --------------------------------------------------------------- */
async function startDemoHandler() {
  const btn1 = document.getElementById("btn-start-demo");
  const btn2 = document.getElementById("btn-start-demo2");
  [btn1, btn2].forEach(b => { if (b) { b.disabled = true; b.innerHTML = '<span class="spinner"></span> Starting…'; } });

  const res = await startDemo();
  if (res.ok) {
    State.set("demoRunning", true);
    _trafficHistory.labels = [];
    _trafficHistory.normal = [];
    _trafficHistory.ddos = [];
    showToast("success", "Demo Started", res.data?.message || "Demo workflow is running.");
    setTimeout(refresh, 500);
    setTimeout(refresh, 2500);
  } else {
    showToast("error", "Failed to Start Demo", res.error);
  }
  [btn1, btn2].forEach(b => {
    if (b) { b.disabled = false; b.innerHTML = '<i class="fa-solid fa-play"></i> Start Demo'; }
  });
}

async function stopDemoHandler() {
  const confirmed = await showConfirmModal("Stop Demo", "Stop the demo workflow? Active monitoring will pause.");
  if (!confirmed) return;

  const res = await stopDemo();
  if (res.ok) {
    State.set("demoRunning", false);
    showToast("info", "Demo Stopped", "Demo workflow has been stopped.");
    setTimeout(refresh, 800);
  } else {
    showToast("error", "Failed to Stop Demo", res.error);
  }
}

async function triggerMitigate(ip) {
  if (!ip) return;
  const confirmed = await showConfirmModal(
    "Block Traffic",
    `Block all traffic from ${ip}? In DEMO MODE this will be simulated.`,
    "Block"
  );
  if (!confirmed) return;

  const res = await mitigateSource(ip);
  if (res.ok && res.data?.success) {
    const simulated = res.data.simulated;
    showToast("success",
      simulated ? "Mitigation Simulated" : "Mitigation Applied",
      simulated ? `Simulated block rule for ${ip}` : `OVS/Ryu rule installed for ${ip}`
    );
    setTimeout(refresh, 1000);
  } else {
    showToast("error", "Mitigation Failed", res.error || "Unknown error");
  }
}

/* ---------------------------------------------------------------
   Main refresh — fetch all data and update UI
   --------------------------------------------------------------- */
async function refresh() {
  // Health check
  const health = await getHealth();
  const online = health.ok;
  State.set("backendOnline", online);

  const banner = document.getElementById("backend-offline-banner");
  if (banner) banner.style.display = online ? "none" : "flex";

  if (!online) {
    updateHeaderStatus(false, undefined, false);
    showToast("error", "Backend Unavailable", health.error, 6000);
    return;
  }

  // Parallel fetches
  const [statusRes, devicesRes, trafficRes, alertsRes, metricsRes, detRes] = await Promise.all([
    getSystemStatus(),
    getDevices(),
    getTraffic({ limit: 100 }),
    getAlerts({ limit: 50 }),
    getMetrics(),
    getDetections({ limit: 50 }),
  ]);

  const status = statusRes.ok ? statusRes.data : null;
  const devices = devicesRes.ok ? devicesRes.data : null;
  const traffic = trafficRes.ok ? trafficRes.data : null;
  const alerts = alertsRes.ok ? alertsRes.data : null;
  const metrics = metricsRes.ok ? metricsRes.data : null;
  const detections = detRes.ok ? detRes.data : null;

  // Update state
  State.patch({ systemStatus: status, devices: devices?.devices || [], metrics, lastUpdated: new Date() });

  // Header
  updateHeaderStatus(true, status?.demo_mode, status?.demo_running);

  // KPIs
  updateKPIs(devices, metrics);

  // Charts
  updateTrafficChart(traffic);
  updateDistChart(traffic);

  // Panels
  updateSystemStatusPanel(status);
  const hasDdos = (detections?.detections || []).some(d => d.prediction === "DDOS");
  const hasMitigation = ((await getMitigations({ limit: 5 })).data?.mitigations || []).length > 0;
  updatePipeline(hasDdos, hasMitigation);
  updateRecentAlerts(alerts);
  updateSuspiciousDevices(devices, detections);

  // Alert badge in nav
  const alertCount = alerts?.count || 0;
  const badge = document.getElementById("alerts-badge");
  if (badge) {
    badge.textContent = alertCount;
    badge.style.display = alertCount > 0 ? "inline-block" : "none";
  }

  // Demo state
  if (status) {
    State.set("demoMode", status.demo_mode);
    State.set("demoRunning", status.demo_running);
  }
}

/* ---------------------------------------------------------------
   Polling
   --------------------------------------------------------------- */
function startPolling() {
  stopPolling();
  _pollTimer = setInterval(refresh, State.get("pollInterval") || CONFIG.POLL_INTERVAL);
}
function stopPolling() {
  if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null; }
}
function restartPolling() { startPolling(); }

/* ---------------------------------------------------------------
   Demo buttons
   --------------------------------------------------------------- */
function initDemoButtons() {
  document.getElementById("btn-start-demo")?.addEventListener("click", startDemoHandler);
  document.getElementById("btn-start-demo2")?.addEventListener("click", startDemoHandler);
  document.getElementById("btn-stop-demo")?.addEventListener("click", stopDemoHandler);
  document.getElementById("btn-stop-demo2")?.addEventListener("click", stopDemoHandler);
}

/* ---------------------------------------------------------------
   Page visibility — pause polling when tab hidden
   --------------------------------------------------------------- */
document.addEventListener("visibilitychange", () => {
  if (document.hidden) stopPolling();
  else { refresh(); startPolling(); }
});

/* ---------------------------------------------------------------
   Init
   --------------------------------------------------------------- */
(async function init() {
  try {
    initHeader();
    initDemoButtons();
    initTrafficChart();
    initDistChart();
    updatePipeline(false, false);
  } catch (err) {
    console.error("Dashboard component init error:", err);
  }

  try {
    await refresh();
  } catch (err) {
    console.error("Dashboard refresh error:", err);
  }
  startPolling();
})();
