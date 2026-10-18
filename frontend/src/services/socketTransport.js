const INITIAL_RECONNECT_MS = 1000
const MAX_RECONNECT_MS = 10000
const MAX_BUFFERED_BYTES = 4096

// There is no application send queue: reconnecting never replays a movement.
export function createSocketTransport({
  url, createSocket = address => new WebSocket(address),
  onMessage = () => {}, onStatus = () => {}, later = setTimeout, cancelLater = clearTimeout,
}) {
  let socket = null
  let reconnect = null
  let delay = INITIAL_RECONNECT_MS
  let enabled = false
  let retryGeneration = 0

  function cancelReconnect() {
    // A cancelled callback may already be queued; its generation also expires.
    retryGeneration += 1
    if (reconnect !== null) cancelLater(reconnect)
    reconnect = null
  }

  function discard(next, close = true) {
    if (socket !== next) return
    // Status listeners synchronously release held buttons. Detach first so those
    // releases cannot send through the socket that just failed.
    socket = null
    if (close) {
      try { next.close() } catch { /* The failed socket is already detached. */ }
    }
    onStatus('disconnected')
    scheduleReconnect()
  }

  function connect() {
    if (!enabled || socket?.readyState === 0 || socket?.readyState === 1) return
    cancelReconnect()
    onStatus('connecting')
    let next
    try {
      next = createSocket(url)
    } catch {
      onStatus('disconnected')
      scheduleReconnect()
      return
    }
    socket = next
    next.onopen = () => {
      if (socket !== next) return
      cancelReconnect()
      delay = INITIAL_RECONNECT_MS
      onStatus('connected')
    }
    next.onmessage = event => {
      if (socket !== next) return
      let data
      try {
        data = JSON.parse(event.data)
      } catch {
        onMessage({ case: 'error', detail: 'Ungültige Nachricht vom Server.' })
        return
      }
      if (data && typeof data === 'object' && typeof data.case === 'string') onMessage(data)
    }
    next.onclose = () => {
      discard(next, false)
    }
    next.onerror = () => {
      discard(next)
    }
  }

  function scheduleReconnect() {
    if (!enabled || socket !== null || reconnect !== null) return
    const generation = retryGeneration
    reconnect = later(() => {
      if (generation !== retryGeneration) return
      reconnect = null
      delay = Math.min(delay * 2, MAX_RECONNECT_MS)
      connect()
    }, delay)
  }

  function startup() {
    enabled = true
    connect()
  }

  function send(payload) {
    const current = socket
    if (current?.readyState !== 1) return false
    if (current.bufferedAmount > MAX_BUFFERED_BYTES) {
      discard(current)
      return false
    }
    try {
      current.send(JSON.stringify(payload))
      return true
    } catch {
      discard(current)
      return false
    }
  }

  function shutdown() {
    enabled = false
    cancelReconnect()
    const previous = socket
    socket = null
    previous?.close()
    onStatus('disconnected')
  }

  return { startup, send, shutdown }
}
