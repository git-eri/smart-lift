import test from 'node:test'
import assert from 'node:assert/strict'
import { createPressController, indicatorKey } from '../src/services/pressController.js'

function fixture() {
  const messages = []
  let state
  let tick
  let sequence = 0
  let allowed = true
  let online = true
  let epoch = 'epoch-1'
  const control = createPressController({
    send: data => { if (online) messages.push(data); return online },
    canStart: () => allowed,
    getEpoch: () => epoch,
    newId: () => `command-${++sequence}`,
    onChange: next => { state = next },
    every: (callback, interval) => { assert.equal(interval, 200); tick = callback; return 1 },
    cancelEvery: () => { tick = null },
  })
  return {
    control, messages,
    get state() { return state },
    tick: () => tick?.(),
    hasTimer: () => tick !== null,
    allow: value => { allowed = value },
    online: value => { online = value },
    epoch: value => { epoch = value },
  }
}

test('held press renews immutable identity, release ends timer, no auto-resume', () => {
  const f = fixture()
  assert.equal(f.control.start('con-1', 0, 0), true)
  f.tick()
  assert.equal(f.messages[0].renew, false)
  assert.equal(f.messages[1].renew, true)
  assert.equal(f.messages[0].command_id, f.messages[1].command_id)
  assert.equal(f.messages[1].control_epoch, 'epoch-1')
  f.control.end('con-1', 0, 0)
  assert.equal(f.messages.at(-1).toggle, 0)
  assert.equal(f.hasTimer(), false)
  assert.equal(f.state.pressed.size, 0)
  f.tick()
  assert.equal(f.messages.length, 3)
})

test('all functions of a lift are exclusive; equal lift IDs on other controllers remain independent', () => {
  const f = fixture()
  assert.equal(f.control.start('con-1', 0, 0), true)
  assert.equal(f.control.start('con-1', 0, 1), false)
  assert.equal(f.control.start('con-1', 0, 2), false)
  assert.equal(f.control.start('con-2', 0, 1), true)
  f.control.end('con-1', 0, 1)
  assert.equal(f.state.pressed.size, 2)
  f.control.cancelWhere()
  assert.equal(f.state.pressed.size, 0)
})

test('late off or on acknowledgements cannot alter a new press', () => {
  const f = fixture()
  f.control.start('con-1', 0, 0)
  const first = f.messages[0]
  f.control.acknowledge(first)
  assert.equal(f.state.indicators.size, 1)
  f.control.end('con-1', 0, 0)
  f.control.start('con-1', 0, 1)
  const second = f.messages.at(-1)
  f.control.acknowledge(second)
  f.control.acknowledge({ ...first, toggle: 0 })
  f.control.acknowledge(first)
  assert.equal(f.state.indicators.has(indicatorKey('con-1', 0, 1)), true)
  assert.equal(f.state.indicators.size, 1)
  assert.equal(f.state.pressed.size, 1)
  f.control.cancelWhere()
})

test('STOP, page lifecycle cancellation, and controller removal never replay presses', () => {
  const f = fixture()
  f.control.start('con-1', 0, 0)
  f.control.start('con-2', 5, 2)
  f.control.cancelWhere(conId => conId === 'con-1')
  assert.equal(f.state.pressed.size, 1)
  f.control.cancelWhere()
  f.allow(false)
  assert.equal(f.control.start('con-1', 0, 0), false)
  f.allow(true)
  f.tick()
  assert.equal(f.state.pressed.size, 0)
  assert.equal(f.messages.filter(message => message.renew).length, 0)
})

test('disconnect or epoch change ends renewal; release carries original epoch', () => {
  const f = fixture()
  f.control.start('con-1', 0, 0)
  f.epoch('epoch-2')
  f.tick()
  assert.equal(f.messages.at(-1).toggle, 0)
  assert.equal(f.messages.at(-1).control_epoch, 'epoch-1')
  assert.equal(f.state.pressed.size, 0)
  f.control.start('con-1', 0, 0)
  f.online(false)
  f.tick()
  f.online(true)
  f.tick()
  assert.equal(f.state.pressed.size, 0)
  assert.equal(f.messages.filter(message => message.renew).length, 0)
})

test('server lease expiry and targeted rejection end only the matching press', () => {
  const f = fixture()
  f.control.start('con-1', 0, 0)
  f.control.start('con-2', 5, 2)
  const first = f.messages[0]
  f.control.acknowledge({ ...first, toggle: 0 })
  assert.equal(f.state.pressed.size, 1)
  f.control.reject(first.command_id)
  assert.equal(f.state.pressed.size, 1)
  f.control.reject(f.messages[1].command_id)
  assert.equal(f.state.pressed.size, 0)
})
