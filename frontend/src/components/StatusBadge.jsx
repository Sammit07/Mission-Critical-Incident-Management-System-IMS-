const COLORS = {
  OPEN:          'bg-red-500/20 text-red-300',
  INVESTIGATING: 'bg-yellow-500/20 text-yellow-300',
  RESOLVED:      'bg-green-500/20 text-green-300',
  CLOSED:        'bg-gray-500/20 text-gray-400',
}

const DOTS = {
  OPEN:          'bg-red-400 animate-pulse',
  INVESTIGATING: 'bg-yellow-400 animate-pulse',
  RESOLVED:      'bg-green-400',
  CLOSED:        'bg-gray-500',
}

export default function StatusBadge({ status }) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs ${COLORS[status] ?? COLORS.CLOSED}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${DOTS[status] ?? DOTS.CLOSED}`} />
      {status}
    </span>
  )
}
