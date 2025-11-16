import axios from 'axios'
import config from './config'
import { logout } from './auth'

// API client configuration
const api = axios.create({
  baseURL: config.api.baseURL || '/api',
  withCredentials: true  // Required to send httpOnly cookies with requests
})

// Request interceptor for logging
// Note: Session token is now sent automatically via httpOnly cookie (more secure than localStorage)
api.interceptors.request.use(
  config => {
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
    if (error.response?.status === 401) {
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
