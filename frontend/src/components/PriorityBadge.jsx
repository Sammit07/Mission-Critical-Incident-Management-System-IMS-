const COLORS = {
  P0: 'bg-red-500/20 text-red-400 border border-red-500/50 ring-1 ring-red-500/30',
  P1: 'bg-orange-500/20 text-orange-400 border border-orange-500/50',
  P2: 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/50',
  P3: 'bg-blue-500/20 text-blue-400 border border-blue-500/50',
}

export default function PriorityBadge({ priority }) {
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-bold ${COLORS[priority] ?? COLORS.P3}`}>
      {priority}
    </span>
  )
}
