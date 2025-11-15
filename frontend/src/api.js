import axios from 'axios'
import config from './config'

// API client configuration
const api = axios.create({
  baseURL: config.api.baseURL || '/api',
  headers: {
    'Authorization': `Bearer ${config.api.apiKey}`
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
