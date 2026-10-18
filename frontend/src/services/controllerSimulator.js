const LEASE_MS = 750
const RETIRED_COMMAND_LIMIT = 1024
const validId = value => typeof value === 'string' && /^[A-Za-z0-9_-]{1,64}$/.test(value)

// Uses the same local lease and latched STOP semantics as the ESP firmware.
export function createControllerSimulator({ lifts, conId, send, now = () => performance.now(), onChange = () => {} }) {
  const active = new Map()
  const retired = new Set()
  let ready = false
  let stopped = true
  let lastResetId = null

  function publish() {
    onChange({ ready, stopped, active: new Map(active) })
  }

  function remember(id) {
    retired.add(id)
    if (retired.size > RETIRED_COMMAND_LIMIT) retired.delete(retired.values().next().value)
  }

  function acknowledge(press, toggle) {
    send({ case: 'lift_moved', con_id: conId, lift_id: press.lift_id,
      direction: press.direction, toggle, command_id: press.command_id })
  }

  function finish(press, report = true) {
    active.delete(press.lift_id)
    remember(press.command_id)
    if (report) acknowledge(press, 0)
  }

  function clear(report = true) {
    for (const press of [...active.values()]) finish(press, report)
  }

  function hello() {
    ready = false
    stopped = true
    clear(false)
    send({ case: 'hello', protocol_version: 2, lifts, power_state: 1, stop_latched: true })
    publish()
  }

  function receive(data) {
    expire()
    switch (data.case) {
      case 'controller_ready':
        if (data.protocol_version === 2) ready = true
        break
      case 'stop':
        stopped = true
        clear()
        send({ case: 'stop_state', stopped: true })
        break
      case 'reset_stop':
        if (!validId(data.reset_id)) {
          send({ case: 'error', detail: 'invalid reset ID' })
          break
        }
        if (!ready) {
          send({ case: 'error', detail: 'controller session is not ready' })
          break
        }
        // Retain the last accepted ID across STOP and reconnection. An ACK retry
        // while clear must not interrupt motion; a replay after STOP cannot free it.
        if (data.reset_id === lastResetId) {
          if (stopped) send({ case: 'error', detail: 'stale reset ID' })
          else send({ case: 'stop_state', stopped: false, reset_id: data.reset_id })
          break
        }
        if (!stopped) {
          send({ case: 'error', detail: 'STOP is not latched' })
          break
        }
        clear()
        stopped = false
        lastResetId = data.reset_id
        send({ case: 'stop_state', stopped: false, reset_id: data.reset_id })
        break
      case 'move_lift': {
        if (!ready || !lifts.includes(data.lift_id) || ![0, 1, 2].includes(data.direction) ||
            typeof data.command_id !== 'string' || !data.command_id || data.command_id.length > 64) break
        const current = active.get(data.lift_id)
        const matches = current?.command_id === data.command_id && current?.direction === data.direction
        if (data.toggle === 0) {
          remember(data.command_id)
          if (matches) finish(current)
          break
        }
        if (data.toggle !== 1 || stopped) break
        if (data.renew === true) {
          if (matches && now() - current.renewedAt < LEASE_MS) {
            current.renewedAt = now()
            acknowledge(current, 1)
          }
          // A late renewal can never create or revive a press.
          break
        }
        if (current || retired.has(data.command_id)) break
        const press = { ...data, renewedAt: now() }
        active.set(data.lift_id, press)
        acknowledge(press, 1)
        break
      }
    }
    publish()
  }

  function tick() {
    expire()
    publish()
  }

  function expire() {
    const timestamp = now()
    for (const press of [...active.values()]) {
      if (timestamp - press.renewedAt >= LEASE_MS) finish(press)
    }
  }

  function disconnect() {
    ready = false
    stopped = true
    clear(false)
    publish()
  }

  return { hello, receive, tick, disconnect }
}
