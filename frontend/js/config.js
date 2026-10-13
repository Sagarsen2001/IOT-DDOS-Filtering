/**
 * js/config.js
 * ============
 * Central configuration for the frontend dashboard.
 * Edit API_BASE_URL to point to your running Flask backend.
 */

const CONFIG = {
  /**
   * Flask backend base URL — no trailing slash.
   * In Docker (Nginx on port 8080): API requests go to the same origin via reverse proxy → ""
   * In local dev (python -m http.server on port 5500): API requests go to Flask directly → "http://127.0.0.1:5000"
   */
  API_BASE_URL: window.location.port === "8080" ? "" : "http://127.0.0.1:5000",

  /** Default polling interval in milliseconds */
  POLL_INTERVAL: 5000,

  /** API request timeout in milliseconds */
  REQUEST_TIMEOUT: 10000,

  /** Enable verbose console logging */
  DEBUG_MODE: true,

  /** Set true ONLY for UI development without a backend */
  USE_MOCK_DATA: false,

  /** Maximum rows shown in paginated tables */
  TABLE_PAGE_SIZE: 20,

  /** Traffic chart history: number of time-series points to keep */
  CHART_MAX_POINTS: 30,

  /** Available polling intervals (ms) shown in the UI */
  POLL_OPTIONS: [2000, 5000, 10000, 30000],
};

// Freeze so it cannot be accidentally mutated at runtime
Object.freeze(CONFIG);

