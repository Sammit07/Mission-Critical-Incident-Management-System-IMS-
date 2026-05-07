import { useCallback, useEffect, useState } from 'react'
import { format } from 'date-fns'
import { incidentApi } from '../services/api'
import { wsService } from '../services/websocket'
import { toast } from '../lib/toast'
import RCAForm from './RCAForm'

const STATUS_PILL = {
  OPEN:          'bg-red-100 text-red-700',
  INVESTIGATING: 'bg-amber-100 text-amber-700',
  RESOLVED:      'bg-green-100 text-green-700',
  CLOSED:        'bg-gray-100 text-gray-500',
}

const SEVERITY_LABEL = { P0: 'P0 - Critical', P1: 'P1 - High', P2: 'P2 - Medium', P3: 'P3 - Low' }
const SEVERITY_COLOR  = { P0: 'text-red-600', P1: 'text-orange-500', P2: 'text-amber-600', P3: 'text-blue-600' }

const TRANSITIONS = {
  OPEN:          ['INVESTIGATING'],
  INVESTIGATING: ['RESOLVED', 'OPEN'],
  RESOLVED:      ['CLOSED', 'INVESTIGATING'],
  CLOSED:        [],
}

function shortId(uuid) {
  return 'INC-' + (uuid ?? '').replace(/-/g, '').slice(0, 8).toUpperCase()
}

export default function IncidentDetail({ incidentId, onClose, onUpdated }) {
  const [incident, setIncident] = useState(null)
  const [signals,  setSignals]  = useState([])
  const [transitioning, setTransitioning] = useState(false)

  const loadIncident = useCallback(async () => {
    try { const { data } = await incidentApi.get(incidentId); setIncident(data) } catch {}
  }, [incidentId])

  const loadSignals = useCallback(async () => {
    try { const { data } = await incidentApi.getSignals(incidentId, { limit: 50 }); setSignals(data.signals) } catch {}
  }, [incidentId])

  useEffect(() => { loadIncident(); loadSignals() }, [loadIncident, loadSignals])

  useEffect(() => {
    const unsub = wsService.on('*', (msg) => {
      if (msg.work_item_id === incidentId) {
        loadIncident()
        if (msg.type === 'signal_received') loadSignals()
      }
    })
    return unsub
  }, [incidentId, loadIncident, loadSignals])

  const transition = async (newStatus) => {
    setTransitioning(true)
    try {
      const { data } = await incidentApi.updateStatus(incidentId, newStatus)
      setIncident(data)
      onUpdated?.()
    } catch (err) {
      const detail = err.response?.data?.detail ?? 'Transition failed'
      toast.error(typeof detail === 'string' ? detail : JSON.stringify(detail))
    } finally {
      setTransitioning(false)
    }
  }

  // Walk through any intermediate states automatically so the user
  // never has to manually click INVESTIGATING → RESOLVED before closing.
  const closeWithAutoChain = async () => {
    setTransitioning(true)
    try {
      let status = incident.status

      if (status === 'OPEN') {
        const { data } = await incidentApi.updateStatus(incidentId, 'INVESTIGATING')
        status = data.status
        setIncident(data)
      }
      if (status === 'INVESTIGATING') {
        const { data } = await incidentApi.updateStatus(incidentId, 'RESOLVED')
        status = data.status
        setIncident(data)
      }
      if (status === 'RESOLVED') {
        const { data } = await incidentApi.updateStatus(incidentId, 'CLOSED')
        setIncident(data)
        onUpdated?.()
        toast.success('Incident closed successfully.')
      }
    } catch (err) {
      const detail = err.response?.data?.detail ?? 'Could not close incident.'
      toast.error(typeof detail === 'string' ? detail : JSON.stringify(detail))
    } finally {
      setTransitioning(false)
    }
  }

  if (!incident) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-400 text-sm">Loading…</div>
    )
  }

  const allowed = TRANSITIONS[incident.status] ?? []

  return (
    <div className="flex flex-col gap-6">
      {/* ── Incident Detail card ─────────────────────────────────────────── */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
        {/* Card header */}
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-base font-bold text-gray-900">Incident Detail</h2>
          <div className="flex items-center gap-2">
            <span className={`text-xs font-semibold px-3 py-1 rounded-full ${STATUS_PILL[incident.status]}`}>
              {incident.status}
            </span>
            <button
              onClick={onClose}
              className="ml-1 text-gray-400 hover:text-gray-600 transition-colors text-lg leading-none"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Two-column body */}
        <div className="flex min-h-0">
          {/* Left — info table */}
          <div className="flex-1 min-w-0 px-6 py-5">
            <h3 className="text-lg font-bold text-gray-900 mb-5 leading-snug">
              {incident.title?.replace(/^\[P\d\]\s*/, '')}
            </h3>

            <table className="w-full text-sm">
              <tbody className="divide-y divide-gray-50">
                {[
                  ['Incident ID',  <span key="id" className="text-orange-500 font-medium">{shortId(incident.id)}</span>],
                  ['Component',    <span key="cmp" className="text-orange-500 font-medium">{incident.component_id}</span>],
                  ['Severity',     <span key="sev" className={`font-semibold ${SEVERITY_COLOR[incident.priority]}`}>{SEVERITY_LABEL[incident.priority]}</span>],
                  ['Status',       incident.status],
                  ['First Signal', incident.start_time ? format(new Date(incident.start_time), 'yyyy-MM-dd hh:mm a') : '—'],
                  ['Signal Count', `${incident.signal_count} linked raw signals`],
                  ['MTTR',         incident.mttr_seconds != null
                    ? <span key="mttr" className="font-semibold text-green-600">{formatMttr(incident.mttr_seconds)}</span>
                    : <span key="mttr" className="text-gray-400 italic">Calculated on close</span>],
                ].map(([label, value]) => (
                  <tr key={label}>
                    <td className="py-2 pr-6 font-semibold text-gray-700 w-36 align-top">{label}</td>
                    <td className="py-2 text-gray-600">{value}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* State transition buttons */}
            {allowed.length > 0 && (
              <div className="mt-5 flex items-center gap-2 flex-wrap">
                <span className="text-xs text-gray-400">Transition to:</span>
                {allowed.map((s) => (
                  <button
                    key={s}
                    onClick={() => transition(s)}
                    disabled={transitioning}
                    className="px-3 py-1.5 text-xs font-medium rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 disabled:opacity-40 transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}

          </div>

          {/* Right — Raw Signals */}
          <div className="w-[380px] shrink-0 bg-gray-900 flex flex-col">
            <p className="px-5 py-4 text-sm font-semibold text-gray-200 border-b border-gray-700">
              Raw Signals from NoSQL
            </p>
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {signals.length === 0 && (
                <p className="text-xs text-gray-500 italic">No signals yet…</p>
              )}
              {signals.map((sig, i) => (
                <div
                  key={sig.signal_id ?? i}
                  className="bg-gray-800 rounded-lg px-4 py-3 font-mono text-[11px] text-gray-300 break-all leading-relaxed"
                >
                  {JSON.stringify({
                    component_id: sig.component_id,
                    error:        sig.error_type ?? sig.message,
                    ...(sig.metadata ?? {}),
                    timestamp:    sig.timestamp,
                  })}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ── RCA Form card ────────────────────────────────────────────────── */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-base font-bold text-gray-900">Root Cause Analysis Form</h2>
          <span className="text-xs font-medium text-blue-600 bg-blue-50 border border-blue-100 rounded-full px-3 py-1">
            Required before Closing
          </span>
        </div>
        <div className="px-6 py-5">
          <RCAForm
            incident={incident}
            onSubmitted={() => { loadIncident(); onUpdated?.() }}
            onClose={closeWithAutoChain}
            closing={transitioning}
          />
        </div>
      </div>
    </div>
  )
}

function formatMttr(seconds) {
  if (seconds == null) return '—'
  if (seconds < 60)   return `${seconds}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ${seconds % 60}s`
  const h = Math.floor(seconds / 3600)
  const m = Math.round((seconds % 3600) / 60)
  return `${h}h ${m}m`
}
