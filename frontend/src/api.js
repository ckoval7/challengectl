import axios from 'axios'

// API client configuration
const api = axios.create({
  baseURL: '/api',
  headers: {
    'Authorization': 'Bearer change-this-admin-key-xyz999'  // TODO: Make configurable
  }
})

// Request interceptor for logging
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
    console.error('API Error:', error.response?.data || error.message)
    return Promise.reject(error)
  }
)

export { api }
