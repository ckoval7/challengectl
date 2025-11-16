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

    this.socket.on('disconnect', (reason) => {
      console.log('WebSocket disconnected. Reason:', reason)
      this.connected = false
    })

    this.socket.on('connect_error', (error) => {
      console.error('WebSocket connection error (may need authentication):', error.message, error)
      this.connected = false
    })

    this.socket.on('error', (error) => {
      console.error('WebSocket error:', error)
    })

    this.socket.on('event', (data) => {
      // Only log non-log events to avoid console spam
      if (data.type !== 'log') {
        console.log('WebSocket event:', data.type, data)
      } else {
        // Temporary debug logging for log events
        console.debug('Log event received, dispatching to', this.listeners['log']?.length || 0, 'listeners')
      }

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
