import { useEffect, useRef, useState } from 'react'
import { wsService } from '../services/websocket'
import { formatDistanceToNow } from 'date-fns'

const MAX_EVENTS = 50

const SEVERITY_COLOR = {
  CRITICAL: 'text-red-400',
  HIGH:     'text-orange-400',
  MEDIUM:   'text-yellow-400',
  LOW:      'text-blue-400',
}

export default function LiveFeed() {
  const [events, setEvents] = useState([])
  const bottomRef = useRef(null)

  useEffect(() => {
    const unsub = wsService.on('*', (msg) => {
      if (!['signal_received', 'incident_created', 'incident_updated', 'rca_submitted'].includes(msg.type)) return
      setEvents((prev) => {
        const next = [{ ...msg, _ts: Date.now(), _id: Math.random() }, ...prev]
        return next.slice(0, MAX_EVENTS)
      })
    })
    return unsub
  }, [])

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-2 border-b border-gray-800 text-xs font-semibold text-gray-400 uppercase tracking-widest">
        Live Event Feed
      </div>
      <div className="flex-1 overflow-y-auto">
        {events.length === 0 && (
          <p className="p-4 text-xs text-gray-600 italic">Waiting for events...</p>
        )}
        {events.map((ev) => (
          <div key={ev._id} className="px-4 py-2 border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
            <div className="flex items-center justify-between gap-2 mb-0.5">
              <span className="text-xs font-semibold text-gray-300">{formatType(ev.type)}</span>
              <span className="text-xs text-gray-600">{formatDistanceToNow(ev._ts, { addSuffix: true })}</span>
            </div>
            <div className="text-xs text-gray-500 truncate">
              {ev.component_id && (
                <span className={`mr-1 ${SEVERITY_COLOR[ev.severity] ?? 'text-gray-400'}`}>
                  {ev.component_id}
                </span>
              )}
              {ev.priority && <span className="text-gray-400">[{ev.priority}]</span>}
              {ev.status && <span className="text-gray-400"> → {ev.status}</span>}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

function formatType(type) {
  return {
    signal_received:  '⚡ Signal',
    incident_created: '🔴 New Incident',
    incident_updated: '🔄 Status Change',
    rca_submitted:    '📋 RCA Submitted',
  }[type] ?? type
}
