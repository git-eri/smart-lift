// No send queue: a movement can only originate from a currently connected page.
export function createSocketTransport({
  url, createSocket = address => new WebSocket(address),
  onMessage = () => {}, onStatus = () => {}, later = setTimeout, cancelLater = clearTimeout,
}) {
  let socket = null
  let reconnect = null
  let delay = 1000
  let enabled = false

  function connect() {
    if (!enabled || socket?.readyState === 0 || socket?.readyState === 1) return
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
      delay = 1000
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
      if (socket !== next) return
      socket = null
      onStatus('disconnected')
      scheduleReconnect()
    }
    next.onerror = () => {
      if (socket !== next) return
      onStatus('disconnected')
      next.close()
    }
  }

  function scheduleReconnect() {
    if (!enabled || reconnect !== null) return
    reconnect = later(() => {
      reconnect = null
      delay = Math.min(delay * 2, 10000)
      connect()
    }, delay)
  }

  function startup() {
    enabled = true
    connect()
  }

  function send(payload) {
    if (socket?.readyState !== 1) return false
    if (socket.bufferedAmount > 4096) {
      onStatus('disconnected')
      socket.close()
      return false
    }
    try {
      socket.send(JSON.stringify(payload))
      return true
    } catch {
      onStatus('disconnected')
      socket.close()
      return false
    }
  }

  function shutdown() {
    enabled = false
    if (reconnect !== null) cancelLater(reconnect)
    reconnect = null
    const previous = socket
    socket = null
    previous?.close()
    onStatus('disconnected')
  }

  return { startup, send, shutdown }
}
