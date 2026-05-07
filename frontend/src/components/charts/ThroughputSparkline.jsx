import { LineChart, Line, ResponsiveContainer, Tooltip } from 'recharts'

/**
 * Compact 60-point sparkline for signals/sec throughput.
 * Renders at 100% of parent dimensions when used inside a flex-1/min-h-0 container.
 * Pass explicit width/height (px) for the inline MetricsBar usage.
 */
export default function ThroughputSparkline({ history = [], width, height }) {
  const chartData = history.map((v, i) => ({ i, v }))

  return (
    <ResponsiveContainer width={width ?? '100%'} height={height ?? '100%'}>
      <LineChart data={chartData} margin={{ top: 4, right: 4, left: 4, bottom: 4 }}>
        <Line
          type="monotone"
          dataKey="v"
          dot={false}
          stroke="#4ade80"
          strokeWidth={1.5}
          isAnimationActive={false}
        />
        <Tooltip
          contentStyle={{ background: '#111827', border: '1px solid #374151', fontSize: 10 }}
          formatter={(v) => [v.toFixed(1), 'sig/s']}
          labelFormatter={() => ''}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
