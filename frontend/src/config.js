/**
 * Configuration for the frontend application.
 *
 * For development: Copy this to config.local.js and customize
 * For production: Set via environment variables or build-time config
 */

const config = {
  // API configuration
  api: {
    // Base URL for API (empty string uses same host)
    baseURL: '',

    // API key for authentication
    // In production, this should be set via environment variable or secure config
    apiKey: import.meta.env.VITE_API_KEY || 'change-this-admin-key-xyz999'
  },

  // WebSocket configuration
  websocket: {
    // WebSocket server URL (defaults to current host)
    url: import.meta.env.VITE_WS_URL || window.location.origin
  },

  // UI configuration
  ui: {
    // Dashboard refresh interval (milliseconds)
    dashboardRefreshInterval: 30000,

    // Runners refresh interval (milliseconds)
    runnersRefreshInterval: 10000,

    // Challenges refresh interval (milliseconds)
    challengesRefreshInterval: 15000,

    // Max log entries to keep
    maxLogEntries: 500
  }
}

export default config
