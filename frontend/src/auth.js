import { ref, computed } from 'vue'
import { websocket } from './websocket'

// Authentication state
const apiKey = ref(localStorage.getItem('apiKey') || null)
const isAuthenticated = computed(() => !!apiKey.value)

/**
 * Login with API key
 * @param {string} key - Admin API key
 */
export function login(key) {
  apiKey.value = key
  localStorage.setItem('apiKey', key)
}

/**
 * Logout and clear authentication
 */
export function logout() {
  apiKey.value = null
  localStorage.removeItem('apiKey')

  // Disconnect WebSocket
  websocket.disconnect()
}

/**
 * Get current API key
 * @returns {string|null}
 */
export function getApiKey() {
  return apiKey.value
}

/**
 * Check if user is authenticated
 * @returns {boolean}
 */
export function checkAuth() {
  return isAuthenticated.value
}

export { isAuthenticated }
