import axios from 'axios'
import config from './config'
import { logout } from './auth'

// API client configuration
const api = axios.create({
  baseURL: config.api.baseURL || '/api',
  withCredentials: true  // Required to send httpOnly cookies with requests
})

// Helper function to get CSRF token from cookie
function getCsrfToken() {
  const match = document.cookie.match(/csrf_token=([^;]+)/)
  return match ? match[1] : null
}

// Request interceptor for logging and CSRF token
// Note: Session token is sent automatically via httpOnly cookie (XSS protection)
// CSRF token is read from non-httpOnly cookie and sent in header (CSRF protection)
api.interceptors.request.use(
  config => {
    // Add CSRF token to header for state-changing requests
    if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(config.method.toUpperCase())) {
      const csrfToken = getCsrfToken()
      if (csrfToken) {
        config.headers['X-CSRF-Token'] = csrfToken
      }
    }

    console.log(`API Request: ${config.method.toUpperCase()} ${config.url}`)
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// Response interceptor for error handling
api.interceptors.response.use(
  response => response,
  error => {
    // Handle 401 Unauthorized errors (expired or invalid session)
    // BUT: Don't redirect if we're just checking the session endpoint
    // (the router guard will handle redirects based on validateSession result)
    if (error.response?.status === 401 && !error.config.url.endsWith('/auth/session')) {
      console.warn('Session expired or unauthorized. Logging out...')
      logout()
      // Redirect to login page
      window.location.href = '/login'
    }

    console.error('API Error:', error.response?.data || error.message)
    return Promise.reject(error)
  }
)

export { api }
