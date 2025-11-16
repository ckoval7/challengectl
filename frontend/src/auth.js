import { ref, computed } from 'vue'
import { websocket } from './websocket'

// Authentication state (tracked in-memory, actual session in httpOnly cookie)
// Note: Session token is stored in httpOnly cookie (not accessible to JavaScript)
// This prevents XSS attacks from stealing the session token
const isAuthenticatedFlag = ref(false)
const isAuthenticated = computed(() => isAuthenticatedFlag.value)

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
 * Check if user is authenticated
 * @returns {boolean}
 */
export function checkAuth() {
  return isAuthenticated.value
}

export { isAuthenticated }
