/**
 * js/state.js
 * ===========
 * Central application state store.
 *
 * All modules read from and write to this object.
 * No state is scattered in individual page scripts.
 *
 * Usage:
 *   State.set('devices', [...]);
 *   const devs = State.get('devices');
 *   State.subscribe('devices', callback);
 */

const State = (() => {
  const _data = {
    systemStatus: null,
    health: null,
    devices: [],
    traffic: [],
    detections: [],
    alerts: [],
    mitigations: [],
    metrics: null,
    demoRunning: false,
    demoMode: true,
    lastUpdated: null,
    pollInterval: CONFIG.POLL_INTERVAL,
    backendOnline: false,
    mlModelLoaded: false,
  };

  // Subscribers: { key: [callback, ...] }
  const _subs = {};

  function get(key) {
    return _data[key];
  }

  function set(key, value) {
    _data[key] = value;
    if (_subs[key]) {
      _subs[key].forEach(cb => {
        try { cb(value); } catch (e) { console.error("[State] subscriber error:", e); }
      });
    }
    // Always update lastUpdated when any state changes
    _data.lastUpdated = new Date();
  }

  function subscribe(key, callback) {
    if (!_subs[key]) _subs[key] = [];
    _subs[key].push(callback);
  }

  function unsubscribe(key, callback) {
    if (_subs[key]) {
      _subs[key] = _subs[key].filter(cb => cb !== callback);
    }
  }

  /** Batch update multiple keys at once */
  function patch(updates) {
    Object.entries(updates).forEach(([k, v]) => set(k, v));
  }

  return { get, set, subscribe, unsubscribe, patch };
})();

