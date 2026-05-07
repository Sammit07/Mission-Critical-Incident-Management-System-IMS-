const PRIORITY_PILL = {
  P0: 'bg-red-500 text-white',
  P1: 'bg-orange-400 text-white',
  P2: 'bg-green-500 text-white',
  P3: 'bg-blue-500 text-white',
}

const STATUS_COLOR = {
  OPEN:          'text-red-600',
  INVESTIGATING: 'text-amber-600',
  RESOLVED:      'text-green-600',
  CLOSED:        'text-gray-400',
}

export default function IncidentList({ incidents, selectedId, onSelect }) {
  if (incidents.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-2 text-gray-400 py-12">
        <span className="text-3xl">✅</span>
        <p className="text-sm">No active incidents</p>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto divide-y divide-gray-100">
      {incidents.map((inc) => {
        const selected = selectedId === inc.id
        const titleClean = inc.title?.replace(/^\[P\d\]\s*/, '') ?? inc.component_id
        return (
          <button
            key={inc.id}
            onClick={() => onSelect(inc.id)}
            className={`w-full text-left px-5 py-4 transition-colors border-l-[3px] ${
              selected
                ? 'border-l-blue-500 bg-blue-50'
                : 'border-l-transparent hover:bg-gray-50'
            }`}
          >
            <div className="flex items-start justify-between gap-2 mb-2">
              <h3 className="text-sm font-semibold text-gray-900 leading-snug">{titleClean}</h3>
              <span className={`shrink-0 text-[11px] font-bold px-2 py-0.5 rounded-full ${PRIORITY_PILL[inc.priority] ?? PRIORITY_PILL.P3}`}>
                {inc.priority}
              </span>
            </div>
            <div className="space-y-0.5 text-xs text-gray-500">
              <p>Component: <span className="text-gray-700 font-medium">{inc.component_id}</span></p>
              <p>Status: <span className={`font-semibold ${STATUS_COLOR[inc.status]}`}>{inc.status}</span></p>
              <p>Signals: <span className="text-gray-700 font-medium">{inc.signal_count}</span></p>
            </div>
          </button>
        )
      })}
    </div>
  )
}
