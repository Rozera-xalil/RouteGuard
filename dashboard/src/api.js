const BASE = import.meta.env.VITE_API_URL ?? '/api'

function readableError(body, status) {
  const d = body && body.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) {
    return d
      .map((e) => `${(e.loc || []).filter((p) => p !== 'body').join(' > ')}: ${e.msg}`)
      .join(' | ')
  }
  return `Request failed (${status})`
}

async function request(path, options = {}) {
  let res
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
  } catch {
    const err = new Error('network')
    err.code = 'network'
    throw err
  }
  let body = null
  try {
    body = await res.json()
  } catch {
    /* empty body */
  }
  if (!res.ok) {
    const err = new Error(readableError(body, res.status))
    err.code = res.status
    throw err
  }
  return body
}

export const api = {
  health: () => request('/health'),
  info: () => request('/info'),
  summary: () => request('/monitoring/summary'),
  recent: (limit = 8) => request(`/predictions/recent?limit=${limit}`),
  predict: (order) => request('/predict', { method: 'POST', body: JSON.stringify(order) }),
  feedback: (prediction_id, actual_late) =>
    request('/feedback', { method: 'POST', body: JSON.stringify({ prediction_id, actual_late }) }),
}
