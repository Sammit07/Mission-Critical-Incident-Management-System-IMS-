// Canonical color palette — badges and charts use these so P0 is the same red everywhere.

export const PRIORITY_COLORS = {
  P0: '#ef4444', // red-500
  P1: '#f97316', // orange-500
  P2: '#eab308', // yellow-500
  P3: '#3b82f6', // blue-500
}

export const STATUS_COLORS = {
  OPEN:          '#f87171', // red-400
  INVESTIGATING: '#fbbf24', // yellow-400
  RESOLVED:      '#4ade80', // green-400
  CLOSED:        '#6b7280', // gray-500
}

export const COMPONENT_COLORS = {
  RDBMS:       '#ef4444', // red-500
  API:         '#f97316', // orange-500
  MCP_HOST:    '#8b5cf6', // violet-500
  CACHE:       '#eab308', // yellow-500
  ASYNC_QUEUE: '#06b6d4', // cyan-500
  NOSQL:       '#4ade80', // green-400
}
