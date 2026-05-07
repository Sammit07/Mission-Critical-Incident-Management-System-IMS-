import { useCallback, useEffect, useState } from 'react'
import { incidentApi } from '../services/api'
import { wsService } from '../services/websocket'
import IncidentList from './IncidentList'
import LiveFeed from './LiveFeed'
import SignalTimeline from './charts/SignalTimeline'
import PriorityDonut from './charts/PriorityDonut'
import TopComponentsBar from './charts/TopComponentsBar'
import ThroughputSparkline from './charts/ThroughputSparkline'

const STATUS_FILTERS = ['ALL', 'OPEN', 'INVESTIGATING', 'RESOLVED', 'CLOSED']
const PRIORITY_FILTERS = ['ALL', 'P0', 'P1', 'P2', 'P3']

export default function Dashboard({ onSelectIncident, selectedIncidentId, throughputHistory }) {
  const [incidents, setIncidents] = useState([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [priorityFilter, setPriorityFilter] = useState('ALL')
  const [componentFilter, setComponentFilter] = useState(null)
  const [chartsOpen, setChartsOpen] = useState(true)

  const fetchIncidents = useCallback(async () => {
    try {
      const params = {}
      if (statusFilter !== 'ALL') params.status = statusFilter
      if (priorityFilter !== 'ALL') params.priority = priorityFilter
      const { data } = await incidentApi.list(params)
      setIncidents(data)
    } catch {
      // silent — will retry on next WS event
    } finally {
      setLoading(false)
    }
  }, [statusFilter, priorityFilter])

  useEffect(() => {
    fetchIncidents()
  }, [fetchIncidents])

  useEffect(() => {
    const unsub = wsService.on('*', (msg) => {
      if (['incident_created', 'incident_updated', 'rca_submitted'].includes(msg.type)) {
        fetchIncidents()
      }
    })
    return unsub
  }, [fetchIncidents])

  // Client-side component filter applied on top of API results
  const visibleIncidents = componentFilter
    ? incidents.filter((inc) => inc.component_id === componentFilter)
    : incidents

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {/* ── Charts row ─────────────────────────────────────────────────────── */}
      <div className="border-b border-gray-800">
        <button
          onClick={() => setChartsOpen((o) => !o)}
          className="w-full flex items-center gap-2 px-4 py-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors"
        >
          <span className={`transition-transform ${chartsOpen ? 'rotate-90' : ''}`}>▶</span>
          {chartsOpen ? 'Hide charts' : 'Show charts'}
        </button>

        {chartsOpen && (
          <div className="grid grid-cols-4 gap-3 px-4 pb-4">
            <SignalTimeline />
            <PriorityDonut />
            <TopComponentsBar onFilter={setComponentFilter} />
            <div className="h-[200px] bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col">
              <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-widest shrink-0 mb-1">
                Throughput — 60 s
              </p>
              <div className="flex-1 min-h-0">
                <ThroughputSparkline history={throughputHistory ?? []} />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Incident list + feed ────────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {/* Incident list panel */}
        <div className="w-[380px] border-r border-gray-800 flex flex-col">
          {/* Filters */}
          <div className="px-4 py-3 border-b border-gray-800 space-y-2">
            <div className="flex items-center gap-1 flex-wrap">
              {STATUS_FILTERS.map((f) => (
                <FilterChip key={f} label={f} active={statusFilter === f} onClick={() => setStatusFilter(f)} />
              ))}
            </div>
            <div className="flex items-center gap-1 flex-wrap">
              {PRIORITY_FILTERS.map((f) => (
                <FilterChip key={f} label={f} active={priorityFilter === f} onClick={() => setPriorityFilter(f)} />
              ))}
            </div>
          </div>

          <div className="px-4 py-2 border-b border-gray-800 flex items-center justify-between">
            <span className="text-xs text-gray-500 uppercase tracking-wider">
              {visibleIncidents.length} incident{visibleIncidents.length !== 1 ? 's' : ''}
              {componentFilter && (
                <span className="ml-1 text-blue-400">· {componentFilter}</span>
              )}
            </span>
            <button
              onClick={fetchIncidents}
              className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
            >
              ↺ Refresh
            </button>
          </div>

          <IncidentList
            incidents={visibleIncidents}
            selectedId={selectedIncidentId}
            onSelect={onSelectIncident}
            loading={loading}
          />
        </div>

        {/* Live feed panel */}
        <div className="w-[260px] border-r border-gray-800 flex flex-col">
          <LiveFeed />
        </div>
      </div>
    </div>
  )
}

function FilterChip({ label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`px-2 py-0.5 rounded text-xs transition-colors ${
        active
          ? 'bg-blue-500/20 text-blue-400 border border-blue-500/40'
          : 'bg-gray-800 text-gray-500 hover:text-gray-300 border border-transparent'
      }`}
    >
      {label}
    </button>
  )
}
