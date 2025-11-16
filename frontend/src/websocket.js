import { io } from 'socket.io-client'
import config from './config'

class WebSocketManager {
  constructor() {
    this.socket = null
    this.connected = false
    this.listeners = {}
  }

  connect(url = null) {
    if (this.socket) {
      return
    }

    // Use provided URL, or config, or current origin
    const wsUrl = url || config.websocket.url

    this.socket = io(wsUrl, {
      transports: ['websocket', 'polling'],
      withCredentials: true  // Send cookies (session token) with WebSocket connection
    })

    this.socket.on('connect', () => {
      console.log('WebSocket connected')
      this.connected = true
    })

    this.socket.on('disconnect', () => {
      console.log('WebSocket disconnected')
      this.connected = false
    })

    this.socket.on('connect_error', (error) => {
      console.error('WebSocket connection error (may need authentication):', error.message)
      this.connected = false
    })

    this.socket.on('event', (data) => {
      console.log('WebSocket event:', data.type, data)

      // Emit to listeners
      if (this.listeners[data.type]) {
        this.listeners[data.type].forEach(callback => callback(data))
      }
    })

    this.socket.on('initial_state', (data) => {
      console.log('Initial state received:', data)
    })
  }

  on(eventType, callback) {
    if (!this.listeners[eventType]) {
      this.listeners[eventType] = []
    }
    this.listeners[eventType].push(callback)
  }

  off(eventType, callback) {
    if (this.listeners[eventType]) {
      this.listeners[eventType] = this.listeners[eventType].filter(cb => cb !== callback)
    }
  }

  disconnect() {
    if (this.socket) {
      this.socket.disconnect()
      this.socket = null
      this.connected = false
    }
  }
}

export const websocket = new WebSocketManager()
