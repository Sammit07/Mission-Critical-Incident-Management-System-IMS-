import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ResponsiveContainer } from 'recharts'
import { metricsApi } from '../../services/api'
import { COMPONENT_COLORS } from '../../lib/colors'

const trunc = (s, n = 15) => (s.length > n ? s.slice(0, n - 1) + '…' : s)

export default function TopComponentsBar({ onFilter }) {
  const [data, setData] = useState([])
  const [active, setActive] = useState(null)

  useEffect(() => {
    const load = async () => {
      try {
        const { data: raw } = await metricsApi.topComponents()
        setData(raw)
      } catch {}
    }
    load()
    const id = setInterval(load, 60_000)
    return () => clearInterval(id)
  }, [])

  const handleClick = (entry) => {
    if (!entry) return
    const next = active === entry.component_id ? null : entry.component_id
    setActive(next)
    onFilter?.(next)
  }

  return (
    <div className="h-[200px] bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col">
      <div className="flex items-center justify-between shrink-0 mb-1">
        <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-widest">
          Noisiest Components — 24 h
        </p>
        {active && (
          <button
            onClick={() => { setActive(null); onFilter?.(null) }}
            className="text-[9px] text-blue-500 hover:text-blue-400 transition-colors"
          >
            ✕ clear
          </button>
        )}
      </div>

      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 0, right: 8, left: 0, bottom: 0 }}
            onClick={(e) => e?.activePayload && handleClick(e.activePayload[0]?.payload)}
          >
            <XAxis
              type="number"
              tick={{ fill: '#4b5563', fontSize: 9 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              type="category"
              dataKey="component_id"
              tick={{ fill: '#6b7280', fontSize: 9 }}
              tickLine={false}
              axisLine={false}
              width={100}
              tickFormatter={(v) => trunc(v)}
            />
            <Tooltip
              contentStyle={{ background: '#111827', border: '1px solid #374151', fontSize: 11 }}
              cursor={{ fill: 'rgba(255,255,255,0.04)' }}
            />
            <Bar dataKey="count" isAnimationActive={false} radius={[0, 2, 2, 0]} cursor="pointer">
              {data.map((entry) => (
                <Cell
                  key={entry.component_id}
                  fill={COMPONENT_COLORS[entry.component_type] ?? '#6b7280'}
                  opacity={active && active !== entry.component_id ? 0.25 : 1}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
