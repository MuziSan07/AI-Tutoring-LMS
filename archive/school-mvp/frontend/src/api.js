const KEY = 'nova_session'

export function loadSession() {
  try {
    return JSON.parse(localStorage.getItem(KEY)) || null
  } catch {
    return null
  }
}

export function saveSession(session) {
  try {
    session ? localStorage.setItem(KEY, JSON.stringify(session)) : localStorage.removeItem(KEY)
  } catch {
    /* storage unavailable - session lasts for this tab only */
  }
}

let token = loadSession()?.token

export function setToken(t) {
  token = t
}

export async function api(path, { method = 'GET', body } = {}) {
  const res = await fetch(`/api${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const err = new Error(data.detail || `Request failed (${res.status})`)
    err.status = res.status
    throw err
  }
  return data
}

export function downloadJson(data, filename) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}
