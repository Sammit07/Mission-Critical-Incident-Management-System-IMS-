import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const http = axios.create({ baseURL: BASE, timeout: 15_000 })

export const incidentApi = {
  list: (params = {}) => http.get('/api/incidents', { params }),
  get: (id) => http.get(`/api/incidents/${id}`),
  updateStatus: (id, status) => http.patch(`/api/incidents/${id}/status`, { status }),
  submitRca: (id, rca) => http.post(`/api/incidents/${id}/rca`, rca),
  getSignals: (id, params = {}) => http.get(`/api/incidents/${id}/signals`, { params }),
}

export const signalApi = {
  ingest: (signal) => http.post('/api/signals', signal),
  ingestBatch: (signals) => http.post('/api/signals/batch', { signals }),
}

export const healthApi = {
  check: () => http.get('/health'),
  metrics: () => http.get('/metrics'),
}

export const metricsApi = {
  timeseries: (minutes = 60) => http.get('/api/metrics/timeseries', { params: { minutes } }),
  topComponents: (hours = 24, limit = 10) =>
    http.get('/api/metrics/top-components', { params: { hours, limit } }),
}
