// Minimal event-bus toast — any component can call toast.error/warn/success
// without prop-threading. Toast.jsx subscribes and renders.
const listeners = new Set()

export const toast = {
  error:   (msg) => emit('error',   msg),
  warn:    (msg) => emit('warn',    msg),
  success: (msg) => emit('success', msg),
  subscribe: (fn) => { listeners.add(fn); return () => listeners.delete(fn) },
}

function emit(type, msg) {
  listeners.forEach((fn) => fn({ type, msg, id: Math.random() }))
}
