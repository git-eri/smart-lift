export function apiPath(path) {
  return `/api/${path.replace(/^\/+/, '')}`
}

export function websocketUrl(id, location = window.location) {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${location.host}${apiPath(`ws/${encodeURIComponent(id)}`)}`
}

export function randomId(prefix = 'cmd') {
  const bytes = new Uint8Array(16)
  globalThis.crypto.getRandomValues(bytes)
  return `${prefix}-${Array.from(bytes, value => value.toString(16).padStart(2, '0')).join('')}`
}
