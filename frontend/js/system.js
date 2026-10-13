/**
 * js/system.js
 * ============
 * System Status page controller.
 * Shows component health, ML metrics + confusion matrix, network metrics.
 */

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

function setEl(id, v) { const e = document.getElementById(id); if (e) e.textContent = v; }

/* ---------------------------------------------------------------
   Component Status Cards
   --------------------------------------------------------------- */
const COMPONENTS = [
  { key: "flask",    label: "Flask API",    icon: "fa-server",               desc: "REST API server" },
  { key: "database", label: "Database",     icon: "fa-database",             desc: "SQLite storage" },
  { key: "ml_model", label: "ML Engine",    icon: "fa-brain",                desc: "RandomForest classifier" },
  { key: "mqtt",     label: "MQTT Broker",  icon: "fa-tower-broadcast",      desc: "Mosquitto" },
  { key: "zeek",     label: "Zeek Monitor", icon: "fa-magnifying-glass-chart", desc: "Flow log available" },
  { key: "ryu",      label: "Ryu SDN",      icon: "fa-network-wired",        desc: "OpenFlow controller" },
  { key: "ovs",      label: "Open vSwitch", icon: "fa-sitemap",              desc: "Packet switching" },
];

function renderComponentCards(status) {
  const grid = document.getElementById("system-status-grid");
  if (!grid) return;

  const checked = formatTimestamp(new Date().toISOString());

  grid.innerHTML = COMPONENTS.map(comp => {
    const raw = status ? status[comp.key] : null;
    const { label: stLabel, cls } = raw ? getComponentStatus(raw) : { label: "Unknown", cls: "status-unknown" };
    const isOnline = cls === "status-online";
    const iconColor = isOnline ? "var(--green)" : cls === "status-suspicious" ? "var(--yellow)" : "var(--text-muted)";

    return `
      <div class="card" style="display:flex;flex-direction:column;gap:0.5rem">
        <div style="display:flex;align-items:center;gap:0.65rem">
          <div style="width:36px;height:36px;border-radius:8px;background:var(--bg-raised);display:flex;align-items:center;justify-content:center;flex-shrink:0">
            <i class="fa-solid ${comp.icon}" style="color:${iconColor};font-size:0.95rem" aria-hidden="true"></i>
          </div>
          <div>
            <div style="font-weight:600;font-size:0.85rem;color:var(--text-primary)">${escapeHtml(comp.label)}</div>
            <div style="font-size:0.72rem;color:var(--text-muted)">${escapeHtml(comp.desc)}</div>
          </div>
        </div>
        <div style="display:flex;align-items:center;justify-content:space-between;margin-top:0.25rem">
          <span class="status-pill ${cls}">
            <span class="status-dot"></span>
            ${escapeHtml(stLabel)}
          </span>
          <span style="font-size:0.7rem;color:var(--text-muted)">${escapeHtml(checked)}</span>
        </div>
      </div>`;
  }).join("");

  // Demo mode extra card
  if (status) {
    const demoMode = status.demo_mode;
    grid.insertAdjacentHTML("beforeend", `
      <div class="card" style="display:flex;flex-direction:column;gap:0.5rem">
        <div style="display:flex;align-items:center;gap:0.65rem">
          <div style="width:36px;height:36px;border-radius:8px;background:var(--bg-raised);display:flex;align-items:center;justify-content:center;flex-shrink:0">
            <i class="fa-solid fa-flask" style="color:${demoMode ? 'var(--yellow)' : 'var(--green)'}" aria-hidden="true"></i>
          </div>
          <div>
            <div style="font-weight:600;font-size:0.85rem;color:var(--text-primary)">Operation Mode</div>
            <div style="font-size:0.72rem;color:var(--text-muted)">DEMO or REAL</div>
          </div>
        </div>
        <div style="display:flex;align-items:center;justify-content:space-between;margin-top:0.25rem">
          <span class="status-pill ${demoMode ? 'status-suspicious' : 'status-online'}">
            <span class="status-dot"></span>
            ${demoMode ? "DEMO MODE" : "REAL MODE"}
          </span>
        </div>
      </div>`);
  }
}

/* ---------------------------------------------------------------
   ML Metrics
   --------------------------------------------------------------- */
function renderMLMetrics(ml) {
  const fmt = v => v != null ? formatPercentage(v) : "—";
  setEl("ml-accuracy",  fmt(ml.accuracy));
  setEl("ml-precision", fmt(ml.precision));
  setEl("ml-recall",    fmt(ml.recall));
  setEl("ml-f1",        fmt(ml.f1_score));
  setEl("ml-fpr",       fmt(ml.false_positive_rate));
  setEl("ml-tpr",       fmt(ml.true_positive_rate));

  const ver = document.getElementById("model-version-label");
  if (ver) ver.textContent = ml.model_version ? `Model: ${ml.model_version}` : "";

  // Confusion matrix
  const cm = ml.confusion_matrix || {};
  setEl("cm-tn-val", cm.tn != null ? formatNumber(cm.tn) : "—");
  setEl("cm-fp-val", cm.fp != null ? formatNumber(cm.fp) : "—");
  setEl("cm-fn-val", cm.fn != null ? formatNumber(cm.fn) : "—");
  setEl("cm-tp-val", cm.tp != null ? formatNumber(cm.tp) : "—");
}

/* ---------------------------------------------------------------
   Network Metrics
   --------------------------------------------------------------- */
function renderNetworkMetrics(net) {
  // Field names match backend: calculator.py _network_metrics()
  const throughput = net.average_throughput_bps != null
    ? formatBytes(net.average_throughput_bps) + "/s"
    : "—";
  const duration = net.average_flow_duration_s != null
    ? formatDuration(net.average_flow_duration_s)
    : "—";
  const flows = net.total_flows_recorded != null
    ? formatNumber(net.total_flows_recorded)
    : "—";

  setEl("net-throughput", throughput);
  setEl("net-duration",   duration);
  setEl("net-flows",      flows);
  setEl("net-pkt-loss",   "N/A");
  setEl("net-latency",    "N/A");
}

/* ---------------------------------------------------------------
   Main refresh
   --------------------------------------------------------------- */
async function refresh() {
  const health = await getHealth();
  updateHeader(health.ok, undefined);

  if (!health.ok) {
    const grid = document.getElementById("system-status-grid");
    if (grid) grid.innerHTML = `<div class="card" style="grid-column:1/-1"><div class="empty-state">
      <i class="fa-solid fa-plug-circle-xmark" aria-hidden="true"></i>
      <h3>Backend Unavailable</h3><p>${escapeHtml(health.error)}</p>
    </div></div>`;
    return;
  }

  const [statusRes, metricsRes] = await Promise.all([getSystemStatus(), getMetrics()]);

  if (statusRes.ok) {
    updateHeader(true, statusRes.data?.demo_mode);
    renderComponentCards(statusRes.data);
  } else {
    renderComponentCards(null);
  }

  if (metricsRes.ok) {
    const m = metricsRes.data;
    if (m.ml && Object.keys(m.ml).length > 0) {
      renderMLMetrics(m.ml);
    } else {
      // Show placeholder
      ["ml-accuracy","ml-precision","ml-recall","ml-f1","ml-fpr","ml-tpr","cm-tn-val","cm-fp-val","cm-fn-val","cm-tp-val"]
        .forEach(id => setEl(id, "—"));
      showToast("warning", "ML Metrics Unavailable", "Train the model first: python -m ml.train", 6000);
    }
    renderNetworkMetrics(m.network || {});
  }
}

/* ---------------------------------------------------------------
   Init
   --------------------------------------------------------------- */
(function init() {
  document.getElementById("global-refresh")?.addEventListener("click", refresh);
  document.getElementById("sys-refresh-btn")?.addEventListener("click", refresh);
  document.getElementById("sidebar-toggle")?.addEventListener("click", () => document.getElementById("sidebar")?.classList.toggle("open"));

  refresh();
  setInterval(refresh, CONFIG.POLL_INTERVAL);
})();
