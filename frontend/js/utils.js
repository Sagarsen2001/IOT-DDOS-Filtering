/**
 * js/utils.js
 * ===========
 * Reusable pure utility functions.
 * No DOM access, no API calls, no state mutations.
 */

/** Escape HTML to prevent XSS via innerHTML */
function escapeHtml(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/** Format an ISO timestamp to a human-readable local string */
function formatTimestamp(ts) {
  if (!ts) return "—";
  try {
    const d = new Date(ts);
    if (isNaN(d)) return "—";
    return d.toLocaleString(undefined, {
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return "—";
  }
}

/** Format an ISO timestamp to HH:MM:SS (for chart labels) */
function formatTimeShort(ts) {
  if (!ts) return new Date().toLocaleTimeString();
  try {
    return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return "—";
  }
}

/** Format a number with locale separators */
function formatNumber(n, decimals = 0) {
  if (n == null || isNaN(n)) return "—";
  return Number(n).toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/** Format a float as a percentage string e.g. 0.972 → "97.2%" */
function formatPercentage(n, decimals = 1) {
  if (n == null || isNaN(n)) return "—";
  return (Number(n) * 100).toFixed(decimals) + "%";
}

/** Format bytes into human-readable string */
function formatBytes(bytes) {
  if (bytes == null || isNaN(bytes)) return "—";
  const b = Number(bytes);
  if (b < 1024) return `${b} B`;
  if (b < 1024 ** 2) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 ** 3) return `${(b / 1024 ** 2).toFixed(1)} MB`;
  return `${(b / 1024 ** 3).toFixed(2)} GB`;
}

/** Format a duration in seconds to a readable string */
function formatDuration(s) {
  if (s == null || isNaN(s)) return "—";
  const sec = Number(s);
  if (sec < 60) return `${sec.toFixed(2)}s`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ${(sec % 60).toFixed(0)}s`;
  return `${(sec / 3600).toFixed(1)}h`;
}

/** Format a packet rate */
function formatRate(rate, unit = "pkt/s") {
  if (rate == null || isNaN(rate)) return "—";
  return `${formatNumber(rate, 1)} ${unit}`;
}

/**
 * Return a CSS class for a severity level.
 * HIGH/CRITICAL → danger, MEDIUM → warning, LOW → info
 */
function getSeverityClass(severity) {
  switch ((severity || "").toUpperCase()) {
    case "CRITICAL": return "badge-critical";
    case "HIGH":     return "badge-danger";
    case "MEDIUM":   return "badge-warning";
    case "LOW":      return "badge-info";
    default:         return "badge-secondary";
  }
}

/** Return CSS class for a prediction value */
function getPredictionClass(prediction) {
  return (prediction || "").toUpperCase() === "DDOS" ? "badge-danger" : "badge-success";
}

/** Return CSS class for device status */
function getStatusClass(status) {
  switch ((status || "").toUpperCase()) {
    case "BLOCKED":    return "status-blocked";
    case "SUSPICIOUS": return "status-suspicious";
    case "OFFLINE":    return "status-offline";
    case "ACTIVE":
    case "ONLINE":     return "status-online";
    default:           return "status-unknown";
  }
}

/** Return human-readable label for system component status strings */
function getComponentStatus(val) {
  const map = {
    running: { label: "Running", cls: "status-online" },
    ok: { label: "OK", cls: "status-online" },
    loaded: { label: "Loaded", cls: "status-online" },
    connected: { label: "Connected", cls: "status-online" },
    available: { label: "Available", cls: "status-online" },
    reachable: { label: "Reachable", cls: "status-online" },
    log_found: { label: "Active", cls: "status-online" },
    simulated: { label: "Simulated", cls: "status-online" },
    error: { label: "Error", cls: "status-blocked" },
    not_loaded: { label: "Not Loaded", cls: "status-suspicious" },
    disconnected: { label: "Disconnected", cls: "status-suspicious" },
    unavailable: { label: "Unavailable", cls: "status-offline" },
    unreachable: { label: "Unreachable", cls: "status-offline" },
    log_not_found: { label: "Log Not Found", cls: "status-suspicious" },
  };
  return map[(val || "").toLowerCase()] || { label: val || "Unknown", cls: "status-unknown" };
}

/** Validate IPv4 address */
function isValidIPv4(ip) {
  return /^(\d{1,3}\.){3}\d{1,3}$/.test(ip) &&
    ip.split(".").every(n => Number(n) >= 0 && Number(n) <= 255);
}

/** Debounce a function */
function debounce(fn, wait = 300) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

/** Clamp a number between min and max */
function clamp(n, min, max) {
  return Math.min(Math.max(n, min), max);
}

/** Return "—" when a value is null/undefined/empty */
function dash(val) {
  if (val == null || val === "" || val === "N/A") return "—";
  return val;
}

/** Safe accessor: obj.a.b.c → safeGet(obj, 'a','b','c') */
function safeGet(obj, ...keys) {
  return keys.reduce((acc, k) => (acc != null ? acc[k] : undefined), obj);
}

/**
 * ---------------------------------------------------------------
 * Theme Management (Light / Dark)
 * ---------------------------------------------------------------
 */
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  const icon = document.getElementById('theme-toggle-icon');
  if (icon) {
    if (theme === 'dark') {
      icon.className = 'fa-solid fa-sun';
      icon.parentElement?.setAttribute('title', 'Switch to Light Mode');
    } else {
      icon.className = 'fa-solid fa-moon';
      icon.parentElement?.setAttribute('title', 'Switch to Dark Mode');
    }
  }
}

function initThemeToggle() {
  localStorage.removeItem('theme'); // Clear legacy dark preference
  const currentTheme = localStorage.getItem('theme_v2') || 'light';
  applyTheme(currentTheme);

  const toggleBtn = document.getElementById('theme-toggle-btn');
  if (toggleBtn) {
    if (!toggleBtn.dataset.themeBound) {
      toggleBtn.dataset.themeBound = "true";
      toggleBtn.addEventListener('click', () => {
        const active = document.documentElement.getAttribute('data-theme') || 'light';
        const nextTheme = active === 'dark' ? 'light' : 'dark';
        applyTheme(nextTheme);
        localStorage.setItem('theme_v2', nextTheme);
        window.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme: nextTheme } }));
      });
    }
  }
}

// Auto-run on DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initThemeToggle);
} else {
  initThemeToggle();
}


