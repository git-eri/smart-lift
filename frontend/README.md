# Smart Lift Frontend

Vue-Oberfläche mit gemeinsamem WebSocket-Dienst. HTTP und WebSockets laufen über
denselben Ursprung unter `/api`; Hostnamen und Ports werden nicht in den Build eingebaut.

## Lokal entwickeln

Node ab 22.12 verwenden. Der Docker-Build verwendet die getestete Version 22.23.3.

```sh
npm ci
npm test
npm run build
npm run dev
```

Vite leitet `/api` einschließlich WebSockets an `http://127.0.0.1:8000` weiter.
Ein anderer Backend-Ursprung kann serverseitig mit `SMART_LIFT_API_TARGET` gesetzt
werden. Beim Öffnen über einen anderen Host muss dieser auch in der
Origin-Konfiguration des Backends zulässig sein.

## Bedienung und Protokoll

Nach einem Neustart und nach STOP bleibt die Steuerung gesperrt. Die sichtbare
Freigabe-Taste startet einen bestätigten Reset über alle Controller. Eine Freigabe
führt keine vorherige Bewegung fort; jede Bewegung benötigt einen neuen Tastendruck.

Jeder Tastendruck erhält eine zufällige `command_id` und die aktuelle
`control_epoch`. Während des Haltens sendet die Oberfläche alle 200 ms eine
Erneuerung derselben Freigabe. Loslassen, Pointer-Abbruch, Fokusverlust,
Hintergrundwechsel, Seitenwechsel, STOP und Verbindungsverlust beenden lokale
Bedienungen. Der WebSocket-Dienst puffert keine Fahrbefehle. Alle drei Funktionen
eines Lifts schließen sich gegenseitig aus.

Die Anzeigen stellen bestätigte Relaisbefehle dar. Offline-Controller behalten
ihren Platz in der Oberfläche; ihre Tasten sind gesperrt und die Anzeigen aus.

Der Simulator unter `/simulator` verwendet Protokollversion 2, eine eigene
750-ms-Freigabeüberwachung und denselben STOP-/Reset-Ablauf. Optional wählt der
URL-Hash `#0-4` bis zu fünf Lift-IDs. Nur in einer Entwicklungsumgebung ohne
`SMARTLIFT_CONTROLLER_TOKEN` verwenden: Browser-WebSockets können den erforderlichen
Controller-Authentifizierungsheader nicht setzen. Für Tests keine produktive
Controller-Authentifizierung abschalten.

## Prüfungen

`npm test` prüft Freigabeidentitäten, verzögerte Bestätigungen, gegenseitige
Verriegelung, STOP-/Abbruchfälle, Wiederverbindungen und das Simulatorprotokoll mit
kontrollierter Zeit und Fake-Sockets. `npm run build` prüft den Vue-Produktionsbuild.

`npm run test:protocol` verbindet die tatsächlichen Frontend-Transport- und
Tastendruckmodule über Vite mit einem isolierten Backend und dem Simulator. Der
Test prüft die strikten Nachrichtenschemata, Erneuerung, Loslassen und STOP/Reset.
Die Backend-Abhängigkeiten müssen vorhanden sein; `SMART_LIFT_PYTHON` wählt Python.

`npm run test:browser` startet zusätzlich ein isoliertes Backend auf Port 18000,
Vite auf Port 15173 und einen installierten Browser ohne sichtbares Fenster. Dafür
müssen die Backend-Abhängigkeiten und ein Chromium-Browser vorhanden sein.
`SMART_LIFT_PYTHON` wählt den Python-Pfad, `SMART_LIFT_BROWSER` den Browser-Pfad
(Standard: Microsoft Edge unter Windows). Port 19222 wird für DevTools verwendet.
Der Test prüft Halten, Erneuern, Loslassen, Tastatur, Pointer-Abbruch, Fokusverlust,
STOP, Freigabe ohne Wiederanlauf und einen Controller-Abbruch. Daten und
Browserprofil liegen in einem temporären Verzeichnis.

## Container

Der Build führt `npm ci`, `npm test` und `npm run build` aus. Nginx läuft als
Benutzer `nginx` auf Port 8080; `/healthz` liefert den Containerstatus. Die
SPA-Konfiguration unterstützt direkte Aufrufe von `/admin` und `/simulator`.
HTML wird vor jeder Wiederverwendung validiert, versionierte Build-Assets dürfen
langfristig zwischengespeichert werden. In der Compose-Installation übernimmt der
äußere Proxy die Weiterleitung von `/api` zum Backend.
