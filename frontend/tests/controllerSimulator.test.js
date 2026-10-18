import test from 'node:test'
import assert from 'node:assert/strict'
import { createControllerSimulator } from '../src/services/controllerSimulator.js'

function fixture() {
  let time = 0
  let state
  const sent = []
  const model = createControllerSimulator({
    conId: 'con-sim', lifts: [0, 1, 2], send: message => sent.push(message),
    now: () => time, onChange: next => { state = next },
  })
  model.hello()
  return {
    model, sent, get state() { return state },
    time: value => { time = value },
    arm() {
      model.receive({ case: 'controller_ready', protocol_version: 2 })
      model.receive({ case: 'reset_stop', reset_id: 'reset-1' })
    },
  }
}

const command = { case: 'move_lift', con_id: 'con-sim', lift_id: 0, direction: 0, toggle: 1, command_id: 'first', renew: false }

test('v2 hello starts latched and reset must be explicit and acknowledged with its ID', () => {
  const f = fixture()
  assert.deepEqual(f.sent[0], { case: 'hello', protocol_version: 2, lifts: [0, 1, 2], power_state: 1, stop_latched: true })
  f.model.receive(command)
  assert.equal(f.state.active.size, 0)
  f.arm()
  assert.deepEqual(f.sent.at(-1), { case: 'stop_state', stopped: false, reset_id: 'reset-1' })
  assert.equal(f.state.active.size, 0)
})

test('unknown and stale renewals never start a relay; lease expiry turns it off', () => {
  const f = fixture()
  f.arm()
  f.model.receive({ ...command, renew: true })
  assert.equal(f.state.active.size, 0)
  f.model.receive(command)
  f.time(200)
  f.model.receive({ ...command, renew: true })
  assert.equal(f.sent.at(-1).case, 'lift_moved')
  assert.equal(f.sent.at(-1).toggle, 1)
  assert.equal(f.sent.filter(message => message.case === 'lift_moved' && message.toggle === 1).length, 2)
  f.time(949)
  f.model.tick()
  assert.equal(f.state.active.size, 1)
  f.time(950)
  f.model.tick()
  assert.equal(f.state.active.size, 0)
  assert.equal(f.sent.at(-1).toggle, 0)
  f.model.receive({ ...command, renew: true })
  f.model.receive(command)
  assert.equal(f.state.active.size, 0)
})

test('opposing function and stale release cannot replace or end an active press', () => {
  const f = fixture()
  f.arm()
  f.model.receive(command)
  f.model.receive({ ...command, direction: 1, command_id: 'other' })
  f.model.receive({ ...command, toggle: 0, command_id: 'old' })
  assert.equal(f.state.active.get(0).direction, 0)
  f.model.receive({ ...command, toggle: 0 })
  assert.equal(f.state.active.size, 0)
})

test('STOP and reconnect clear every output without resuming held commands', () => {
  const f = fixture()
  f.arm()
  f.model.receive(command)
  f.model.receive({ ...command, lift_id: 1, command_id: 'second' })
  f.model.receive({ case: 'stop' })
  assert.equal(f.state.active.size, 0)
  assert.equal(f.state.stopped, true)
  assert.deepEqual(f.sent.at(-1), { case: 'stop_state', stopped: true })
  f.model.receive({ ...command, command_id: 'third' })
  assert.equal(f.state.active.size, 0)
  f.model.disconnect()
  f.model.hello()
  assert.equal(f.state.ready, false)
  assert.equal(f.state.stopped, true)
})

test('duplicate reset acknowledgements and unsolicited new resets preserve active movement', () => {
  const f = fixture()
  f.arm()
  f.model.receive(command)
  f.model.receive({ case: 'reset_stop', reset_id: 'reset-1' })
  assert.equal(f.state.active.size, 1)
  assert.deepEqual(f.sent.at(-1), { case: 'stop_state', stopped: false, reset_id: 'reset-1' })
  f.model.receive({ case: 'reset_stop', reset_id: 'reset-2' })
  assert.equal(f.state.active.size, 1)
  assert.equal(f.state.stopped, false)
  assert.equal(f.sent.at(-1).case, 'error')
})

test('a reset ID accepted before STOP or reconnection cannot release the next latch', () => {
  const f = fixture()
  f.arm()
  f.model.receive({ case: 'stop' })
  f.model.receive({ case: 'reset_stop', reset_id: 'reset-1' })
  assert.equal(f.state.stopped, true)
  assert.equal(f.sent.at(-1).case, 'error')
  f.model.receive({ case: 'reset_stop', reset_id: 'reset-2' })
  assert.equal(f.state.stopped, false)
  f.model.disconnect()
  f.model.hello()
  f.model.receive({ case: 'controller_ready', protocol_version: 2 })
  f.model.receive({ case: 'reset_stop', reset_id: 'reset-2' })
  assert.equal(f.state.stopped, true)
  f.model.receive({ case: 'reset_stop', reset_id: 'reset-3' })
  assert.equal(f.state.stopped, false)
  assert.equal(f.state.active.size, 0)
})

test('a deadline crossed before the timer tick expires only that lift and rejects its late renewal', () => {
  const f = fixture()
  f.arm()
  f.model.receive(command)
  f.time(300)
  f.model.receive({ ...command, lift_id: 1, command_id: 'second' })
  f.time(750)
  f.model.receive({ ...command, renew: true })
  assert.equal(f.state.active.has(0), false)
  assert.equal(f.state.active.has(1), true)
  assert.equal(f.state.stopped, false)
  assert.equal(f.sent.at(-1).toggle, 0)
  assert.equal(f.sent.at(-1).command_id, 'first')
})
