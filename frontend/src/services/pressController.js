import { randomId } from './urls.js'

const RENEW_INTERVAL_MS = 200
const RETIRED_COMMAND_LIMIT = 1024

export const liftKey = (conId, liftId) => JSON.stringify([conId, liftId])
export const indicatorKey = (conId, liftId, direction) => JSON.stringify([conId, liftId, direction])

// A press owns one immutable ID and control epoch. Only that press may renew it.
export function createPressController({
  send, canStart, getEpoch, onChange = () => {}, newId = randomId,
  every = setInterval, cancelEvery = clearInterval,
}) {
  const presses = new Map()
  const indicators = new Map()
  const retired = new Set()
  let timer = null

  function changed() {
    onChange({
      pressed: new Map(presses),
      indicators: new Set([...indicators.values()].map(p => indicatorKey(p.con_id, p.lift_id, p.direction))),
    })
  }

  function retire(commandId) {
    retired.add(commandId)
    // Bound delayed-ACK history without retaining every press for the page lifetime.
    if (retired.size > RETIRED_COMMAND_LIMIT) retired.delete(retired.values().next().value)
  }

  function finish(press, transmit = true) {
    const key = liftKey(press.con_id, press.lift_id)
    if (presses.get(key) !== press) return
    presses.delete(key)
    retire(press.command_id)
    if (indicators.get(key)?.command_id === press.command_id) indicators.delete(key)
    if (transmit) send({ case: 'move_lift', ...press, toggle: 0, renew: false })
    if (!presses.size && timer !== null) {
      cancelEvery(timer)
      timer = null
    }
  }

  function tick() {
    for (const press of [...presses.values()]) {
      // A failed send can synchronously cancel the entire snapshot via listeners.
      if (presses.get(liftKey(press.con_id, press.lift_id)) !== press) continue
      if (!canStart(press.con_id) || press.control_epoch !== getEpoch() ||
          !send({ case: 'move_lift', ...press, toggle: 1, renew: true })) finish(press)
    }
    changed()
  }

  function start(conId, liftId, direction) {
    const key = liftKey(conId, liftId)
    if (!canStart(conId) || presses.has(key) || ![0, 1, 2].includes(direction) || !getEpoch()) return false
    const press = { con_id: conId, lift_id: liftId, direction, command_id: newId(), control_epoch: getEpoch() }
    presses.set(key, press)
    if (!send({ case: 'move_lift', ...press, toggle: 1, renew: false }) || presses.get(key) !== press) {
      finish(press, false)
      changed()
      return false
    }
    if (timer === null) timer = every(tick, RENEW_INTERVAL_MS)
    changed()
    return true
  }

  function end(conId, liftId, direction) {
    const press = presses.get(liftKey(conId, liftId))
    if (!press || press.direction !== direction) return
    finish(press)
    changed()
  }

  function cancelWhere(predicate = () => true, transmit = true) {
    for (const press of [...presses.values()]) {
      if (predicate(press.con_id)) finish(press, transmit)
    }
    for (const [key, press] of indicators) {
      if (predicate(press.con_id)) {
        retire(press.command_id)
        indicators.delete(key)
      }
    }
    changed()
  }

  function acknowledge(data) {
    if (!data.command_id || !data.con_id || ![0, 1, 2].includes(data.direction)) return
    const key = liftKey(data.con_id, data.lift_id)
    if (data.toggle === 0) {
      retire(data.command_id)
      if (indicators.get(key)?.command_id === data.command_id) indicators.delete(key)
      const press = presses.get(key)
      // An ESP lease expiry is authoritative even while the user still holds a key.
      if (press?.command_id === data.command_id) finish(press, false)
    } else if (data.toggle === 1 && !retired.has(data.command_id) && canStart(data.con_id)) {
      const local = presses.get(key)
      if (!local || local.command_id === data.command_id) indicators.set(key, { ...data })
    }
    changed()
  }

  function reject(commandId) {
    for (const press of [...presses.values()]) {
      if (!commandId || press.command_id === commandId) finish(press)
    }
    changed()
  }

  return { start, end, cancelWhere, acknowledge, reject }
}
