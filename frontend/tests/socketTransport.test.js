import test from 'node:test'
import assert from 'node:assert/strict'
import { createSocketTransport } from '../src/services/socketTransport.js'
import { apiPath, websocketUrl, randomId } from '../src/services/urls.js'

function fixture(statusChanged = () => {}) {
  const sockets = []
  const statuses = []
  const received = []
  let reconnect
  const scheduled = []
  const cancelled = []
  const transport = createSocketTransport({
    url: 'ws://lift.test/api/ws/cli-test',
    createSocket: () => {
      const socket = {
        readyState: 0, sent: [],
        send(data) { this.sent.push(JSON.parse(data)) },
        close() { this.readyState = 3; this.onclose?.() },
        open() { this.readyState = 1; this.onopen() },
      }
      sockets.push(socket)
      return socket
    },
    onStatus: status => { statuses.push(status); statusChanged(status, transport) },
    onMessage: data => received.push(data),
    later: (callback, wait) => {
      reconnect = callback
      scheduled.push({ callback, wait })
      return scheduled.length
    },
    cancelLater: id => { cancelled.push(id); reconnect = null },
  })
  return { transport, sockets, statuses, received, scheduled, cancelled, reconnect: () => reconnect?.() }
}

test('disconnected sends are dropped and never queued on reconnect', () => {
  const f = fixture()
  assert.equal(f.transport.send({ case: 'move_lift' }), false)
  f.transport.startup()
  f.transport.startup()
  assert.equal(f.sockets.length, 1)
  f.sockets[0].open()
  assert.equal(f.sockets[0].sent.length, 0)
  assert.equal(f.transport.send({ case: 'stop' }), true)
  f.sockets[0].close()
  assert.equal(f.transport.send({ case: 'move_lift' }), false)
  f.reconnect()
  f.sockets[1].open()
  assert.equal(f.sockets[1].sent.length, 0)
})

test('old socket callbacks cannot change a new session; shutdown cancels reconnect', () => {
  const f = fixture()
  f.transport.startup()
  const first = f.sockets[0]
  first.open()
  first.close()
  f.reconnect()
  f.sockets[1].open()
  first.onmessage({ data: '{"case":"stop"}' })
  first.onclose()
  assert.deepEqual(f.received, [])
  assert.equal(f.statuses.at(-1), 'connected')
  f.transport.shutdown()
  f.reconnect()
  assert.equal(f.sockets.length, 2)
})

test('invalid JSON reports an inline error and valid messages still arrive', () => {
  const f = fixture()
  f.transport.startup()
  f.sockets[0].open()
  f.sockets[0].onmessage({ data: 'invalid' })
  f.sockets[0].onmessage({ data: '{"case":"online_lifts","lifts":{}}' })
  assert.equal(f.received[0].case, 'error')
  assert.equal(f.received[1].case, 'online_lifts')
})

test('network backpressure closes the connection instead of growing a movement buffer', () => {
  const f = fixture()
  f.transport.startup()
  f.sockets[0].open()
  f.sockets[0].bufferedAmount = 4097
  assert.equal(f.transport.send({ case: 'move_lift' }), false)
  assert.equal(f.sockets[0].sent.length, 0)
  assert.equal(f.statuses.at(-1), 'disconnected')
  f.reconnect()
  f.sockets[1].open()
  assert.equal(f.sockets[1].sent.length, 0)
})

test('focus-triggered connection cancels an old retry and its queued callback stays stale', () => {
  const f = fixture()
  f.transport.startup()
  f.sockets[0].open()
  f.sockets[0].close()
  const oldRetry = f.scheduled[0].callback
  f.transport.startup()
  assert.deepEqual(f.cancelled, [1])
  f.sockets[1].open()
  f.sockets[1].close()
  oldRetry()
  assert.equal(f.sockets.length, 2)
  assert.equal(f.scheduled.at(-1).wait, 1000)
  f.reconnect()
  assert.equal(f.sockets.length, 3)
})

test('synchronous release callbacks cannot send through a socket whose send just failed', () => {
  let releaseAccepted
  const f = fixture((status, transport) => {
    if (status === 'disconnected') releaseAccepted = transport.send({ case: 'stop' })
  })
  f.transport.startup()
  f.sockets[0].open()
  f.sockets[0].send = data => {
    const payload = JSON.parse(data)
    if (payload.case === 'move_lift') throw new Error('Connection lost during send')
    f.sockets[0].sent.push(payload)
  }
  assert.equal(f.transport.send({ case: 'move_lift' }), false)
  assert.equal(releaseAccepted, false)
  assert.deepEqual(f.sockets[0].sent, [])
  assert.equal(f.scheduled.length, 1)
})

test('same-origin API and socket URLs preserve scheme, host and port', () => {
  assert.equal(apiPath('/admin/lift-rename'), '/api/admin/lift-rename')
  assert.equal(websocketUrl('con-test', { protocol: 'https:', host: 'lift.test:8443' }), 'wss://lift.test:8443/api/ws/con-test')
  assert.equal(websocketUrl('cli-test', { protocol: 'http:', host: '192.168.1.2' }), 'ws://192.168.1.2/api/ws/cli-test')
  assert.match(randomId('cli'), /^cli-[0-9a-f]{32}$/)
  assert.notEqual(randomId(), randomId())
})
