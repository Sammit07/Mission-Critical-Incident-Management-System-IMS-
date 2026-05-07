import { useEffect, useState } from 'react'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'
import { incidentApi } from '../../services/api'
import { PRIORITY_COLORS } from '../../lib/colors'
import { wsService } from '../../services/websocket'

const PRIORITIES = ['P0', 'P1', 'P2', 'P3']

export default function PriorityDonut() {
  const [data, setData] = useState([])

  const load = async () => {
    try {
      const { data: incidents } = await incidentApi.list({ status: 'OPEN', limit: 200 })
      const counts = Object.fromEntries(PRIORITIES.map((p) => [p, 0]))
      for (const inc of incidents) {
        if (counts[inc.priority] !== undefined) counts[inc.priority]++
      }
      setData(PRIORITIES.map((p) => ({ name: p, value: counts[p] })).filter((d) => d.value > 0))
    } catch {}
  }

  useEffect(() => {
    load()
    const unsub = wsService.on('*', (msg) => {
      if (['incident_created', 'incident_updated'].includes(msg.type)) load()
    })
    return unsub
  }, [])

  const total = data.reduce((s, d) => s + d.value, 0)

  return (
    <div className="h-[200px] bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col">
      <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-widest shrink-0 mb-1">
        Open by Priority
      </p>

      <div className="flex-1 min-h-0 flex items-center">
        {/* donut */}
        <div className="h-full flex-1 min-w-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                innerRadius="45%"
                outerRadius="70%"
                isAnimationActive={false}
              >
                {data.map((entry) => (
                  <Cell key={entry.name} fill={PRIORITY_COLORS[entry.name]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ background: '#111827', border: '1px solid #374151', fontSize: 11 }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* legend — fixed width column to the right */}
        <div className="flex flex-col gap-1.5 pl-3 shrink-0">
          {PRIORITIES.map((p) => {
            const entry = data.find((d) => d.name === p)
            const count = entry?.value ?? 0
            return (
              <span key={p} className="flex items-center gap-1.5">
                <span
                  className="w-2.5 h-2.5 rounded-sm shrink-0"
                  style={{ background: PRIORITY_COLORS[p], opacity: count === 0 ? 0.2 : 1 }}
                />
                <span className="text-[10px] text-gray-500 w-4">{p}</span>
                <span className="text-[10px] font-semibold text-gray-300 tabular-nums">{count}</span>
              </span>
            )
          })}
          <span className="text-[9px] text-gray-600 mt-0.5">{total} total</span>
        </div>
      </div>
    </div>
  )
}
