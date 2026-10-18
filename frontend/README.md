# Smart Lift frontend

The Vue application uses one shared WebSocket connection across routes. HTTP and
WebSocket requests use the same origin under `/api`; hostnames and ports are not
embedded in the build.

## Development

Use Node 22.12 or newer. The Docker builder uses the tested Node 22.23.3 release.

```sh
npm ci
npm test
npm run build
npm run dev
```

Vite proxies `/api`, including WebSockets, to `http://127.0.0.1:8000`.
Set the server-side `SMART_LIFT_API_TARGET` environment variable to use another
backend origin. When opening Vite through a different host, that browser origin
must also be permitted by the backend's origin policy.

## Responsibilities and state

- `src/services/socketTransport.js` owns socket identity, bounded reconnect
  backoff and backpressure handling. It has no application send queue. A failed
  socket is detached before status listeners run, because those listeners may
  synchronously release buttons.
- `src/services/websocket.js` exposes the shared Vue session state. The remembered
  lift catalog preserves offline cards; a separate live-controller set and the
  authoritative control snapshot determine whether a controller can be operated.
- `src/services/pressController.js` owns held commands, their renewal timer and
  acknowledgement correlation. Each press captures its command ID and control
  epoch. Retired command IDs prevent delayed acknowledgements from reviving an
  ended press or clearing a newer one.
- `MainView.vue` connects page lifecycle events to cancellation, sorts all cards
  numerically by lift ID and implements wheel navigation by one card. Equal IDs
  on different controllers remain distinct. `Lift.vue` owns physical pointer and
  keyboard input, including capture loss and cleanup after external cancellation.
- `src/services/controllerSimulator.js` models controller-side leases and STOP.
  Its last accepted reset ID survives STOP and reconnection: an acknowledgement
  retry while already clear preserves movement; replay after STOP is rejected.

## Operation and protocol

Startup and STOP leave control latched. The visible reset button requests a reset
acknowledged by all controllers. Reset never resumes an earlier movement; every
movement requires a fresh press. There is no status hint during normal operation.

Each press receives a random `command_id` and captures the current `control_epoch`.
While held, it renews the same command every 200 ms. Release, pointer cancellation,
focus loss, backgrounding, route changes, STOP and connection loss end local
presses. All three functions of a lift are mutually exclusive. Changing the card
layout or navigating with the wheel also releases held buttons.

Indicators display acknowledged relay commands. Offline cards remain visible,
with disabled controls and cleared indicators. They do not grant control simply
because they remain in the catalog.

The simulator at `/simulator` uses protocol version 2, a local 750 ms lease and the
same STOP/reset handshake. Each accepted renewal is acknowledged, as on the ESP.
Expiry ends only the affected lift and cannot be undone by a late renewal. The
optional URL hash `#0-4` selects up to five lift IDs.

Use the browser simulator only in a development environment without
`SMARTLIFT_CONTROLLER_TOKEN`: browser WebSockets cannot set the required
controller authentication header. Do not disable production controller
authentication to run a test.

## Checks

`npm test` checks lease identity, delayed acknowledgements, exclusive functions,
synchronous disconnect handling, STOP/reset replay, reconnect timers and simulator
expiry using controlled clocks and fake sockets. `npm run build` checks the Vue
production build.

`npm run test:protocol` connects the actual frontend transport and press modules
through Vite to an isolated backend and the simulator. It checks strict message
schemas, renewal, release and STOP/reset. Backend dependencies must be available;
`SMART_LIFT_PYTHON` selects the Python executable.

`npm run test:browser` additionally launches an installed Chromium browser without
a visible window. `SMART_LIFT_BROWSER` selects the executable; the default is
Microsoft Edge on Windows. Backend port 18000, Vite port 15173 and DevTools port
19222 must be free. The test never reuses an existing service. Data and browser
profiles use a temporary directory. It checks pointer/keyboard input, cancellation,
focus loss, STOP, reset without replay and controller disconnection.

## Container

The builder runs `npm ci`, `npm test` and `npm run build`. Nginx runs as user `nginx`
on port 8080; `/healthz` supplies its healthcheck. SPA routing supports direct
requests for `/admin` and `/simulator`. HTML is revalidated before reuse, while
versioned build assets can be cached long term. In Compose, the outer proxy routes
`/api` requests to the backend.
