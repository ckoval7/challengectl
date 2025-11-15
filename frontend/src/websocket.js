import { io } from 'socket.io-client'

class WebSocketManager {
  constructor() {
    this.socket = null
    this.connected = false
    this.listeners = {}
  }

  connect(url = 'http://localhost:8443') {
    if (this.socket) {
      return
    }

    this.socket = io(url, {
      transports: ['websocket', 'polling']
    })

    this.socket.on('connect', () => {
      console.log('WebSocket connected')
      this.connected = true
    })

    this.socket.on('disconnect', () => {
      console.log('WebSocket disconnected')
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
