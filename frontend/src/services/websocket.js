const RAW_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'
const WS_BASE = RAW_URL.replace(/^http/, 'ws').replace(/^https/, 'wss')

class WebSocketService {
  constructor() {
    this.ws = null
    this.listeners = new Map()
    this._reconnectDelay = 1_000
    this._maxDelay = 30_000
    this._intentionalClose = false
  }

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return
    this._intentionalClose = false
    this.ws = new WebSocket(`${WS_BASE}/ws/dashboard`)

    this.ws.onopen = () => {
      this._reconnectDelay = 1_000
      this._emit('connected', {})
    }

    this.ws.onmessage = ({ data }) => {
      try {
        const msg = JSON.parse(data)
        this._emit(msg.type, msg)
        this._emit('*', msg)
      } catch {}
    }

    this.ws.onclose = () => {
      this._emit('disconnected', {})
      if (!this._intentionalClose) {
        setTimeout(() => this.connect(), this._reconnectDelay)
        this._reconnectDelay = Math.min(this._reconnectDelay * 2, this._maxDelay)
      }
    }

    this.ws.onerror = () => {
      // onclose fires right after onerror, so reconnect is handled there
    }
  }

  disconnect() {
    this._intentionalClose = true
    this.ws?.close()
  }

  on(event, cb) {
    if (!this.listeners.has(event)) this.listeners.set(event, new Set())
    this.listeners.get(event).add(cb)
    return () => this.listeners.get(event)?.delete(cb)
  }

  send(data) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }

  _emit(event, data) {
    this.listeners.get(event)?.forEach((cb) => cb(data))
  }
}

export const wsService = new WebSocketService()
