import { useCallback, useEffect, useState } from 'react'
import { incidentApi, healthApi } from './services/api'
import { wsService } from './services/websocket'
import IncidentList from './components/IncidentList'
import IncidentDetail from './components/IncidentDetail'
import Toast from './components/Toast'

export default function App() {
  const [incidents, setIncidents] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [isConnected, setIsConnected] = useState(false)
  const [metrics, setMetrics] = useState(null)

  const fetchIncidents = useCallback(async () => {
    try {
      const { data } = await incidentApi.list({ limit: 100 })
      setIncidents(data)
    } catch {}
  }, [])

  useEffect(() => {
    wsService.connect()
    const unConn = wsService.on('connected',    () => setIsConnected(true))
    const unDisc = wsService.on('disconnected', () => setIsConnected(false))
    const unMsg  = wsService.on('*', (msg) => {
      if (['incident_created', 'incident_updated', 'rca_submitted'].includes(msg.type)) fetchIncidents()
    })
    fetchIncidents()
    return () => { unConn(); unDisc(); unMsg(); wsService.disconnect() }
  }, [fetchIncidents])

  useEffect(() => {
    const poll = async () => {
      try { const { data } = await healthApi.metrics(); setMetrics(data) } catch {}
    }
    poll()
    const id = setInterval(poll, 5_000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="h-screen flex flex-col bg-gray-50 overflow-hidden">
      <Toast />
      {/* ── App header ──────────────────────────────────────────────────── */}
      <header className="shrink-0 px-8 pt-7 pb-5 flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 tracking-tight">
            Incident Management System
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Monitor active incidents, inspect raw NoSQL signals, and submit Root Cause Analysis.
          </p>
        </div>

        {/* System health pill */}
        <div className="flex items-center gap-3 bg-white border border-gray-200 rounded-xl px-4 py-3 shadow-sm shrink-0">
          <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${isConnected ? 'bg-green-500' : 'bg-amber-400'}`} />
          <div className="text-right">
            <p className="text-sm font-semibold text-gray-800 leading-tight">
              {isConnected ? 'System Healthy' : 'Reconnecting…'}
            </p>
            {metrics && (
              <p className="text-xs text-gray-500 leading-tight mt-0.5">
                Throughput: {(metrics.signals_per_sec ?? 0).toLocaleString()} signals/sec
              </p>
            )}
          </div>
        </div>
      </header>

      {/* ── Body ────────────────────────────────────────────────────────── */}
      <main className="flex flex-1 min-h-0 gap-6 px-8 pb-8">
        {/* Left — Live Feed */}
        <aside className="w-[340px] shrink-0 flex flex-col bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between shrink-0">
            <h2 className="text-base font-bold text-gray-900">Live Feed</h2>
            <span className="text-xs text-gray-500 bg-gray-100 rounded-full px-3 py-1 font-medium">
              Sorted by Severity
            </span>
          </div>
          <IncidentList
            incidents={incidents}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
        </aside>

        {/* Right — Detail */}
        <section className="flex-1 min-w-0 overflow-y-auto">
          {selectedId ? (
            <IncidentDetail
              key={selectedId}
              incidentId={selectedId}
              onClose={() => setSelectedId(null)}
              onUpdated={fetchIncidents}
            />
          ) : (
            <div className="h-full flex flex-col items-center justify-center gap-3 text-gray-400 select-none">
              <span className="text-5xl">👈</span>
              <p className="text-sm">Select an incident to view details and submit RCA</p>
            </div>
          )}
        </section>
      </main>
    </div>
  )
}
