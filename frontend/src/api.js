import axios from 'axios'
import config from './config'
import { getApiKey } from './auth'

// API client configuration
const api = axios.create({
  baseURL: config.api.baseURL || '/api'
})

// Request interceptor to add auth header and logging
api.interceptors.request.use(
  config => {
    // Add Authorization header if API key is available
    const apiKey = getApiKey()
    if (apiKey) {
      config.headers['Authorization'] = `Bearer ${apiKey}`
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
    console.error('API Error:', error.response?.data || error.message)
    return Promise.reject(error)
  }
)

export { api }
