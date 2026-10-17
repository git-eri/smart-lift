// Optional end-to-end check against a local backend and an installed headless browser.
// SMART_LIFT_PYTHON and SMART_LIFT_BROWSER select executables; neither is downloaded.
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { mkdtemp, mkdir, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { createServer } from 'node:net'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createControllerSimulator } from '../src/services/controllerSimulator.js'
import { createPressController } from '../src/services/pressController.js'
import { createSocketTransport } from '../src/services/socketTransport.js'
import { websocketUrl } from '../src/services/urls.js'

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const root = resolve(frontend, '..')
const scratch = await mkdtemp(resolve(tmpdir(), 'smart-lift-browser-'))
assert.equal(dirname(scratch), resolve(tmpdir()), 'temporary artifacts stay inside the temporary directory')
const children = []
const delay = ms => new Promise(done => setTimeout(done, ms))
const request = url => fetch(url, { signal: AbortSignal.timeout(1000) })
let browser
let page
let controllerSocket
let watchdog
let client
let logs = ''

function launch(command, args, options = {}) {
  const child = spawn(command, args, { cwd: root, windowsHide: true, ...options, stdio: ['ignore', 'pipe', 'pipe'] })
  child.stdout.on('data', chunk => { logs = (logs + chunk).slice(-10000) })
  child.stderr.on('data', chunk => { logs = (logs + chunk).slice(-10000) })
  child.on('error', error => { logs += error.message })
  children.push(child)
  return child
}

async function requireFreePort(port) {
  const probe = createServer()
  await new Promise((resolve, reject) => {
    probe.once('error', () => reject(new Error(`Test port ${port} is already in use; no existing service will be reused.`)))
    probe.listen(port, '127.0.0.1', () => probe.close(resolve))
  })
}

async function until(predicate, label, timeout = 12000) {
  const deadline = Date.now() + timeout
  while (Date.now() < deadline) {
    try { if (await predicate()) return } catch { /* server or page is still starting */ }
    await delay(50)
  }
  throw new Error(`Timeout: ${label}\n${logs}`)
}

async function cdp(url) {
  const socket = new WebSocket(url)
  const pending = new Map()
  const handlers = new Map()
  let sequence = 0
  await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('DevTools connection timeout')), 5000)
    socket.addEventListener('open', () => { clearTimeout(timeout); resolve() }, { once: true })
    socket.addEventListener('error', error => { clearTimeout(timeout); reject(error) }, { once: true })
  })
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data)
    if (message.id) {
      const request = pending.get(message.id)
      pending.delete(message.id)
      if (request) clearTimeout(request.timeout)
      if (message.error) request?.reject(new Error(message.error.message))
      else request?.resolve(message.result)
    } else handlers.get(message.method)?.(message.params)
  })
  return {
    call(method, params = {}) {
      const id = ++sequence
      return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => { pending.delete(id); reject(new Error(`DevTools command timeout: ${method}`)) }, 5000)
        pending.set(id, { resolve, reject, timeout })
        socket.send(JSON.stringify({ id, method, params }))
      })
    },
    on(method, handler) { handlers.set(method, handler) },
    close() { socket.close() },
  }
}

try {
  await Promise.all([18000, 15173, ...(process.argv.includes('--protocol-only') ? [] : [19222])].map(requireFreePort))
  await mkdir(resolve(scratch, 'data'))
  launch(process.env.SMART_LIFT_PYTHON || 'python', [
    '-m', 'uvicorn', 'app.main:app', '--app-dir', 'backend', '--host', '127.0.0.1', '--port', '18000',
    '--ws-ping-interval', '1', '--ws-ping-timeout', '2', '--ws-max-size', '4096',
  ], { env: { ...process.env, SMARTLIFT_DATA_DIR: resolve(scratch, 'data'), SMARTLIFT_CONTROLLER_TOKEN: '' } })
  launch(process.execPath, [resolve(frontend, 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '15173', '--strictPort'], {
    cwd: frontend, env: { ...process.env, SMART_LIFT_API_TARGET: 'http://127.0.0.1:18000' },
  })
  await until(async () => (await request('http://127.0.0.1:18000/health')).ok, 'backend startup')
  await until(async () => (await request('http://127.0.0.1:15173/')).ok, 'frontend startup')
  console.log('Backend and Vite ready.')

  let controllerState = { ready: false, stopped: true, active: new Map() }
  controllerSocket = new WebSocket('ws://127.0.0.1:18000/ws/con-browser-smoke')
  const model = createControllerSimulator({
    conId: 'con-browser-smoke', lifts: [0, 1, 2, 3, 4],
    send: message => controllerSocket.send(JSON.stringify(message)),
    onChange: state => { controllerState = state },
  })
  controllerSocket.addEventListener('message', event => model.receive(JSON.parse(event.data)))
  await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('Controller connection timeout')), 5000)
    controllerSocket.addEventListener('open', () => { clearTimeout(timeout); resolve() }, { once: true })
    controllerSocket.addEventListener('error', error => { clearTimeout(timeout); reject(error) }, { once: true })
  })
  model.hello()
  watchdog = setInterval(model.tick, 50)
  await until(() => controllerState.ready, 'controller handshake')
  console.log('Controller handshake complete.')

  let connection = false
  let control = null
  let pressState
  const clientErrors = []
  const press = createPressController({
    send: data => client.send({ ...data, client_id: 'cli-protocol-smoke' }),
    canStart: () => connection && control?.stopped === false && !control?.reset_pending &&
      control?.controllers['con-browser-smoke']?.ready === true,
    getEpoch: () => control?.control_epoch,
    onChange: state => { pressState = state },
  })
  client = createSocketTransport({
    url: websocketUrl('cli-protocol-smoke', { protocol: 'http:', host: '127.0.0.1:15173' }),
    onStatus: status => { connection = status === 'connected'; if (!connection) press.cancelWhere() },
    onMessage: data => {
      if (data.case === 'control_state') {
        if (control?.control_epoch !== data.control_epoch || data.stopped || data.reset_pending) press.cancelWhere()
        control = data
      }
      if (data.case === 'lift_moved') press.acknowledge(data)
      if (data.case === 'error') { clientErrors.push(data); press.reject(data.command_id) }
    },
  })
  client.startup()
  await until(() => connection && control, 'frontend transport initial state')
  assert.equal(control.stopped, true)
  client.send({ case: 'reset_stop' })
  await until(() => control.stopped === false && !control.reset_pending, 'protocol reset acknowledgement')
  assert.equal(press.start('con-browser-smoke', 0, 0), true)
  await until(() => controllerState.active.size === 1, 'frontend press reaches controller')
  await delay(900)
  assert.equal(controllerState.active.size, 1, 'frontend renewals preserve the controller lease')
  press.end('con-browser-smoke', 0, 0)
  await until(() => controllerState.active.size === 0 && pressState.indicators.size === 0, 'frontend release acknowledgement')
  assert.equal(press.start('con-browser-smoke', 0, 1), true)
  await until(() => controllerState.active.size === 1, 'second frontend press')
  client.send({ case: 'stop' })
  await until(() => control.stopped && controllerState.stopped && controllerState.active.size === 0, 'protocol STOP')
  client.send({ case: 'reset_stop' })
  await until(() => !control.stopped && !control.reset_pending, 'protocol second reset')
  await delay(300)
  assert.equal(controllerState.active.size, 0, 'protocol reset does not replay presses')
  assert.equal(pressState.pressed.size, 0)
  assert.deepEqual(clientErrors, [], 'frontend messages satisfy the strict backend schema')
  client.send({ case: 'stop' })
  await until(() => control.stopped && controllerState.stopped, 'restore initial STOP')
  client.shutdown()
  client = null
  console.log('Protocol smoke passed: real frontend transport/press modules → backend → simulator, reset, renewal, release, STOP and no replay.')

  if (!process.argv.includes('--protocol-only')) {

  const executable = process.env.SMART_LIFT_BROWSER || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
  launch(executable, [
    '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--remote-debugging-port=19222', `--user-data-dir=${resolve(scratch, 'browser')}`, 'about:blank',
  ])
  let version
  await until(async () => { version = await (await request('http://127.0.0.1:19222/json/version')).json(); return !!version.webSocketDebuggerUrl }, 'headless browser startup')
  browser = await cdp(version.webSocketDebuggerUrl)
  console.log('Headless browser ready.')
  const target = await browser.call('Target.createTarget', { url: 'http://127.0.0.1:15173/' })
  const tabs = await (await request('http://127.0.0.1:19222/json/list')).json()
  page = await cdp(tabs.find(tab => tab.id === target.targetId).webSocketDebuggerUrl)
  const exceptions = []
  page.on('Runtime.exceptionThrown', event => exceptions.push(event.exceptionDetails.text))
  await page.call('Runtime.enable')
  await page.call('Page.enable')
  await page.call('Page.bringToFront')
  async function evaluate(expression) {
    const result = await page.call('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text)
    return result.result.value
  }
  const enabledCount = () => evaluate("document.querySelectorAll('.motion-button:not(:disabled)').length")
  await until(async () => await evaluate("document.querySelectorAll('.lift').length") === 5, 'lift cards')
  assert.equal(await enabledCount(), 0, 'initial STOP disables motion')
  await evaluate("document.querySelector('.reset-button').click()")
  await until(async () => await enabledCount() === 15, 'explicit reset handshake')
  assert.equal(controllerState.active.size, 0, 'reset never starts motion')

  async function mouse(type) {
    const rect = await evaluate("(() => { const r = document.querySelector('.motion-button').getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2} })()")
    await page.call('Input.dispatchMouseEvent', { type, ...rect, button: 'left', clickCount: 1 })
  }
  await mouse('mousePressed')
  await until(() => controllerState.active.get(0)?.direction === 0, 'pointer hold starts motion')
  await delay(900)
  assert.equal(controllerState.active.size, 1, '200 ms renewals maintain a held press')
  assert.equal(await evaluate("document.querySelectorAll('.lift')[0].querySelectorAll('.motion-button:disabled').length"), 2, 'other functions are blocked')
  await mouse('mouseReleased')
  await until(() => controllerState.active.size === 0, 'pointer release')

  await evaluate("document.querySelector('.motion-button').focus()")
  await page.call('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: ' ', code: 'Space', windowsVirtualKeyCode: 32 })
  await until(() => controllerState.active.size === 1, 'keyboard hold')
  await page.call('Input.dispatchKeyEvent', { type: 'keyUp', key: ' ', code: 'Space', windowsVirtualKeyCode: 32 })
  await until(() => controllerState.active.size === 0, 'keyboard release')

  await mouse('mousePressed')
  await until(() => controllerState.active.size === 1, 'hold before pointercancel')
  await evaluate("document.querySelector('.motion-button').dispatchEvent(new PointerEvent('pointercancel', {pointerId:1,bubbles:true}))")
  await until(() => controllerState.active.size === 0, 'pointercancel')
  await mouse('mouseReleased')

  await mouse('mousePressed')
  await until(() => controllerState.active.size === 1, 'hold before blur')
  await evaluate("window.dispatchEvent(new Event('blur'))")
  await until(() => controllerState.active.size === 0, 'window blur releases motion')
  await mouse('mouseReleased')

  await mouse('mousePressed')
  await until(() => controllerState.active.size === 1, 'hold before STOP')
  await evaluate("document.querySelector('.e-stop').click()")
  await until(() => controllerState.stopped && controllerState.active.size === 0, 'STOP latch')
  assert.equal(await enabledCount(), 0)
  await mouse('mouseReleased')
  await evaluate("document.querySelector('.reset-button').click()")
  await until(async () => await enabledCount() === 15, 'reset after STOP')
  await delay(300)
  assert.equal(controllerState.active.size, 0, 'reset does not replay an old press')

  controllerSocket.close()
  clearInterval(watchdog)
  watchdog = null
  await until(async () => await enabledCount() === 0, 'controller disconnect disables buttons')
  assert.equal(await evaluate("document.querySelectorAll('.lift').length"), 5, 'offline cards keep their layout')
  assert.equal(await evaluate("document.querySelectorAll('.indicator.active').length"), 0)
  assert.deepEqual(exceptions, [], 'no browser JavaScript exceptions')
  console.log('Browser smoke passed: reset, held renewal, release, keyboard, pointercancel, blur, STOP, no replay, controller disconnect.')
  }
} finally {
  client?.shutdown()
  if (watchdog) clearInterval(watchdog)
  controllerSocket?.close()
  page?.close()
  if (browser) {
    await Promise.race([browser.call('Browser.close').catch(() => {}), delay(1000)])
    browser.close()
  }
  for (const child of children.reverse()) if (child.exitCode === null) child.kill()
  await delay(250)
  assert.equal(dirname(scratch), resolve(tmpdir()))
  await rm(scratch, { recursive: true, force: true }).catch(() => {})
}
