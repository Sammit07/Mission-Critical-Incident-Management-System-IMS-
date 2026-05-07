import { useEffect, useState } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts'
import { format } from 'date-fns'
import { metricsApi } from '../../services/api'
import { COMPONENT_COLORS } from '../../lib/colors'

const COMPONENT_TYPES = ['RDBMS', 'API', 'MCP_HOST', 'CACHE', 'ASYNC_QUEUE', 'NOSQL']

export default function SignalTimeline() {
  const [data, setData] = useState([])

  useEffect(() => {
    const load = async () => {
      try {
        const { data: raw } = await metricsApi.timeseries()
        const tsMap = {}
        for (const [ctype, points] of Object.entries(raw)) {
          for (const { ts, value } of points) {
            if (!tsMap[ts]) tsMap[ts] = { ts }
            tsMap[ts][ctype] = value
          }
        }
        setData(Object.values(tsMap).sort((a, b) => a.ts - b.ts))
      } catch {}
    }
    load()
    const id = setInterval(load, 30_000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="h-[200px] bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col">
      <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-widest shrink-0 mb-1">
        Signals / min — 60 min
      </p>

      {/* chart fills remaining space */}
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
            <XAxis
              dataKey="ts"
              tickFormatter={(ts) => format(ts, 'HH:mm')}
              tick={{ fill: '#4b5563', fontSize: 9 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              tick={{ fill: '#4b5563', fontSize: 9 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              labelFormatter={(ts) => format(ts, 'HH:mm')}
              contentStyle={{ background: '#111827', border: '1px solid #374151', fontSize: 11 }}
            />
            {COMPONENT_TYPES.map((ct) => (
              <Area
                key={ct}
                type="monotone"
                dataKey={ct}
                stackId="1"
                stroke={COMPONENT_COLORS[ct]}
                fill={COMPONENT_COLORS[ct]}
                fillOpacity={0.4}
                dot={false}
                isAnimationActive={false}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* custom legend — outside chart so it never eats chart space */}
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1.5 shrink-0">
        {COMPONENT_TYPES.map((ct) => (
          <span key={ct} className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-sm shrink-0" style={{ background: COMPONENT_COLORS[ct] }} />
            <span className="text-[9px] text-gray-600">{ct}</span>
          </span>
        ))}
      </div>
    </div>
  )
}
