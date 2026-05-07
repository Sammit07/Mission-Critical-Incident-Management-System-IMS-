import { useEffect, useState } from 'react'
import { toast } from '../lib/toast'

const STYLES = {
  error:   'bg-red-600   text-white',
  warn:    'bg-amber-500 text-white',
  success: 'bg-green-600 text-white',
}

const ICONS = { error: '✕', warn: '⚠', success: '✓' }

const TTL = 4500

export default function Toast() {
  const [items, setItems] = useState([])

  useEffect(() => {
    return toast.subscribe((notification) => {
      setItems((prev) => [...prev, notification])
      setTimeout(() => {
        setItems((prev) => prev.filter((i) => i.id !== notification.id))
      }, TTL)
    })
  }, [])

  if (items.length === 0) return null

  return (
    <div className="fixed top-5 right-5 z-50 flex flex-col gap-2 max-w-sm">
      {items.map((item) => (
        <div
          key={item.id}
          className={`flex items-start gap-3 px-4 py-3 rounded-xl shadow-lg text-sm font-medium ${STYLES[item.type]}`}
        >
          <span className="shrink-0 font-bold">{ICONS[item.type]}</span>
          <span className="leading-snug">{typeof item.msg === 'string' ? item.msg : JSON.stringify(item.msg)}</span>
        </div>
      ))}
    </div>
  )
}
