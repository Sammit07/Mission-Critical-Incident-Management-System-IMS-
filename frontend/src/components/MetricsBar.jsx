import { useEffect, useRef, useState } from 'react'
import { healthApi } from '../services/api'
import ThroughputSparkline from './charts/ThroughputSparkline'

const HISTORY_LEN = 60

export default function MetricsBar({ isConnected, onThroughputHistory }) {
  const [metrics, setMetrics] = useState(null)
  const historyRef = useRef([])

  useEffect(() => {
    const poll = async () => {
      try {
        const { data } = await healthApi.metrics()
        setMetrics(data)

        // Maintain a rolling 60-point history of signals/sec for the sparkline
        const val = typeof data.signals_per_sec === 'number' ? data.signals_per_sec : 0
        historyRef.current = [...historyRef.current, val].slice(-HISTORY_LEN)
        onThroughputHistory?.(historyRef.current)
      } catch {}
    }
    poll()
    const id = setInterval(poll, 5_000)
    return () => clearInterval(id)
  }, [onThroughputHistory])

  return (
    <div className="flex items-center gap-6 px-6 py-2 bg-gray-900/80 border-b border-gray-800 text-xs">
      <div className="flex items-center gap-1.5">
        <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-400 animate-pulse' : 'bg-yellow-500'}`} />
        <span className="text-gray-400">{isConnected ? 'Live' : 'Reconnecting...'}</span>
      </div>

      {metrics && (
        <>
          {/* signals/sec + inline sparkline — use items-center, not items-baseline (charts have no baseline) */}
          <div className="flex items-center gap-1.5">
            <span className="font-bold text-green-400">{metrics.signals_per_sec ?? '—'}</span>
            <span className="text-gray-500">signals/sec</span>
            <span className="block" style={{ width: 56, height: 18 }}>
              <ThroughputSparkline history={historyRef.current} width={56} height={18} />
            </span>
          </div>

          <Stat label="total signals" value={metrics.total_signals?.toLocaleString()} color="text-cyan-400" />
          <Stat label="work items" value={metrics.total_work_items?.toLocaleString()} color="text-orange-400" />
          <Stat label="queue depth" value={metrics.queue_depth?.toLocaleString()} color="text-purple-400" />
          <Stat label="ws clients" value={metrics.ws_connections} color="text-gray-300" />
        </>
      )}
    </div>
  )
}

function Stat({ label, value, color }) {
  return (
    <div className="flex items-baseline gap-1">
      <span className={`font-bold ${color}`}>{value ?? '—'}</span>
      <span className="text-gray-500">{label}</span>
    </div>
  )
}
