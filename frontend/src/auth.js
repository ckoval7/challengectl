import { ref, computed } from 'vue'
import { websocket } from './websocket'
import { api } from './api'

// Authentication state (tracked in-memory, actual session in httpOnly cookie)
// Note: Session token is stored in httpOnly cookie (not accessible to JavaScript)
// This prevents XSS attacks from stealing the session token
const isAuthenticatedFlag = ref(false)
const isAuthenticated = computed(() => isAuthenticatedFlag.value)

// Track if we've checked the session on this page load
let sessionChecked = false

/**
 * Mark user as authenticated (called after successful login)
 * Note: Actual session token is in httpOnly cookie, not localStorage
 */
export function login() {
  isAuthenticatedFlag.value = true
}

/**
 * Logout and clear authentication
 * Note: Backend will clear the httpOnly cookie
 */
export function logout() {
  isAuthenticatedFlag.value = false

  // Disconnect WebSocket
  websocket.disconnect()
}

/**
 * Validate session with backend (called on page refresh and router guards)
 * Checks if the session cookie is still valid and updates auth state
 * @returns {Promise<boolean>} True if session is valid
 */
export async function validateSession() {
  try {
    const response = await api.get('/auth/session')
    if (response.data.authenticated) {
      isAuthenticatedFlag.value = true
      sessionChecked = true
      return true
    }
  } catch (error) {
    // Session is invalid or expired
    isAuthenticatedFlag.value = false
    sessionChecked = true
  }
  return false
}

/**
 * Check if user is authenticated
 * For synchronous checks (like computed properties)
 * @returns {boolean}
 */
export function checkAuth() {
  return isAuthenticated.value
}

/**
 * Check if session has been validated on this page load
 * @returns {boolean}
 */
export function isSessionChecked() {
  return sessionChecked
}

export { isAuthenticated }
