/**
 * js/api.js
 * =========
 * Centralised API client. All fetch() calls live here.
 * UI components MUST NOT call fetch() directly.
 *
 * Every function returns a normalised result object:
 *   { ok: true,  data: {...} }
 *   { ok: false, error: "message" }
 *
 * This shields UI components from raw HTTP/network errors.
 */

/* ---------------------------------------------------------------
 * Internal helpers
 * --------------------------------------------------------------- */

async function _request(path, options = {}) {
  const url = `${CONFIG.API_BASE_URL}${path}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), CONFIG.REQUEST_TIMEOUT);

  try {
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      ...options,
    });
    clearTimeout(timer);

    const json = await res.json().catch(() => null);

    if (CONFIG.DEBUG_MODE) {
      console.debug(`[API] ${options.method || "GET"} ${path}`, res.status, json);
    }

    if (!res.ok || (json && json.success === false)) {
      const msg = json?.error?.message || json?.message || `HTTP ${res.status}`;
      return { ok: false, error: msg, raw: json };
    }

    // Backend wraps data in { success, data, timestamp }
    const payload = json?.data !== undefined ? json.data : json;
    return { ok: true, data: payload, timestamp: json?.timestamp };
  } catch (err) {
    clearTimeout(timer);
    if (err.name === "AbortError") {
      return { ok: false, error: "Request timed out" };
    }
    if (err instanceof TypeError) {
      return { ok: false, error: "Backend unreachable — check if Flask is running" };
    }
    return { ok: false, error: err.message };
  }
}

function _get(path, params = {}) {
  const qs = new URLSearchParams(params).toString();
  return _request(qs ? `${path}?${qs}` : path);
}

function _post(path, body = {}) {
  return _request(path, { method: "POST", body: JSON.stringify(body) });
}

/* ---------------------------------------------------------------
 * Public API functions
 * --------------------------------------------------------------- */

/** GET /api/health */
async function getHealth() {
  return _get("/api/health");
}

/** GET /api/system/status */
async function getSystemStatus() {
  return _get("/api/system/status");
}

/** GET /api/devices */
async function getDevices() {
  const res = await _get("/api/devices");
  return normalizeDevicesResponse(res);
}

/** GET /api/devices/<device_id> */
async function getDevice(deviceId) {
  return _get(`/api/devices/${encodeURIComponent(deviceId)}`);
}

/** POST /api/devices/register */
async function registerDevice(data) {
  return _post("/api/devices/register", data);
}

/**
 * GET /api/traffic
 * @param {Object} params - { start_time, end_time, source_ip, prediction, label, limit }
 */
async function getTraffic(params = {}) {
  const res = await _get("/api/traffic", params);
  return normalizeTrafficResponse(res);
}

/** GET /api/detections */
async function getDetections(params = {}) {
  const res = await _get("/api/detections", params);
  return normalizeDetectionsResponse(res);
}

/** GET /api/alerts */
async function getAlerts(params = {}) {
  const res = await _get("/api/alerts", params);
  return normalizeAlertsResponse(res);
}

/** GET /api/mitigations */
async function getMitigations(params = {}) {
  const res = await _get("/api/mitigations", params);
  return normalizeMitigationsResponse(res);
}

/** GET /api/metrics */
async function getMetrics() {
  const res = await _get("/api/metrics");
  return normalizeMetricsResponse(res);
}

/** POST /api/predict */
async function predictFlow(flowData) {
  return _post("/api/predict", flowData);
}

/**
 * POST /api/mitigate
 * @param {string} sourceIp
 */
async function mitigateSource(sourceIp) {
  return _post("/api/mitigate", { source_ip: sourceIp });
}

/** POST /api/demo/start */
async function startDemo() {
  return _post("/api/demo/start");
}

/** POST /api/demo/stop */
async function stopDemo() {
  return _post("/api/demo/stop");
}

/* ---------------------------------------------------------------
 * Response normalizers
 * Translate raw backend shapes → consistent internal shapes.
 * --------------------------------------------------------------- */

function normalizeDevicesResponse(res) {
  if (!res.ok) return res;
  const devices = res.data?.devices ?? (Array.isArray(res.data) ? res.data : []);
  return { ...res, data: { devices, count: devices.length } };
}

function normalizeTrafficResponse(res) {
  if (!res.ok) return res;
  const flows = res.data?.flows ?? (Array.isArray(res.data) ? res.data : []);
  return { ...res, data: { flows, count: flows.length } };
}

function normalizeDetectionsResponse(res) {
  if (!res.ok) return res;
  const detections = res.data?.detections ?? (Array.isArray(res.data) ? res.data : []);
  return { ...res, data: { detections, count: detections.length } };
}

function normalizeAlertsResponse(res) {
  if (!res.ok) return res;
  const alerts = res.data?.alerts ?? (Array.isArray(res.data) ? res.data : []);
  return { ...res, data: { alerts, count: alerts.length } };
}

function normalizeMitigationsResponse(res) {
  if (!res.ok) return res;
  const mitigations = res.data?.mitigations ?? (Array.isArray(res.data) ? res.data : []);
  return { ...res, data: { mitigations, count: mitigations.length } };
}

function normalizeMetricsResponse(res) {
  if (!res.ok) return res;
  // Metrics come back as { ml: {...}, network: {...}, security: {...}, timestamp }
  const data = res.data ?? {};
  return {
    ...res,
    data: {
      ml: data.ml ?? {},
      network: data.network ?? {},
      security: data.security ?? {},
      timestamp: data.timestamp ?? res.timestamp,
    },
  };
}

