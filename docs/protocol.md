# Steuerprotokoll 2

Alle Nachrichten sind JSON-Objekte. WebSockets: `/api/ws/<peer_id>`. IDs haben
maximal 64 Zeichen aus Buchstaben, Ziffern, `_`, `-`; Controller beginnen mit
`con`, Bediener mit `cli`. Doppelte aktive Peer-IDs werden abgewiesen.
Maximal 128 Verbindungen und 4096 Byte pro Backend-Nachricht.

## Registrierung und Freigabe

Controller senden zuerst innerhalb von fünf Sekunden:

```json
{"case":"hello","protocol_version":2,"lifts":[0,1,2,3,4],"power_state":1,"stop_latched":true,"version":"0.06.00"}
```

Optional: `ip`, `rssi`. Alte oder ungültige Hello-Nachrichten schließen die
Verbindung. Backend antwortet:

```json
{"case":"controller_ready","protocol_version":2}
```

Der ESP akzeptiert erst danach Steuerbefehle. Seine Ausgänge bleiben bis zu
einer freigegebenen Bewegung aus. Neustarts des Backends oder Controllers
beginnen mit verriegeltem STOP.

Bediener erhalten `online_lifts`, `power_states` und:

```json
{"case":"control_state","stopped":true,"reset_pending":false,"control_epoch":"opaque-value","controllers":{"con1":{"ready":true,"stopped":true}}}
```

`ready` bedeutet: kompatibler Controller registriert, Transport bereit.
Bedienbar nur bei `stopped:false`, `reset_pending:false` und passendem
Controller. Die opaque `control_epoch` ändert sich bei STOP und erfolgreicher
Freigabe. Alte Tastendrücke werden nicht in eine neue Freigabe übernommen.

## Bewegungen

Neuer Tastendruck:

```json
{"case":"move_lift","con_id":"con1","lift_id":0,"direction":0,"toggle":1,"command_id":"unique-press-id","control_epoch":"opaque-value","renew":false}
```

`direction`: 0 Hoch, 1 Runter, 2 Entriegeln. Alle drei sind pro Lift gegenseitig
verriegelt. `toggle` und Richtung sind strikt ganze Zahlen, keine booleschen
Werte, Zeichenketten oder `null`. `client_id` wird aus der Verbindung bestimmt,
ein übermittelter Wert wird überschrieben.

Während des Haltens erneuert der Browser denselben Befehl alle 200 ms mit
`renew:true`. Backend prüft Besitzer, Lift, Richtung, Kennung und Epoch; ohne
gültige aktive Bewegung darf eine Erneuerung nichts starten. Nach 500 ms ohne
gültige Erneuerung beendet das Backend die Bewegung. Der ESP überprüft dieselbe
Kennung zusätzlich lokal und beendet seine Freigabe nach 750 ms.

Backend sendet an den Controller nur `case`, `lift_id`, `direction`, `toggle`,
`command_id`, `renew`. Loslassen sendet `toggle:0` mit derselben Kennung. Ein
alter oder fremder Ausschaltbefehl darf keinen neueren Tastendruck beenden.

Controller bestätigen mit `lift_moved` und den Feldern `lift_id`, `direction`,
`toggle`, `command_id`. Das Backend ergänzt die `con_id` aus der Verbindung.
Dies ist eine Bestätigung des Relaisbefehls, keine Messung mechanischer
Bewegung. Zeitablauf meldet ebenfalls `toggle:0`.

Die Fristen sind kooperativ und setzen einen laufenden Eventloop voraus.
Blockierende Bibliotheks-/Netzwerkoperationen und die reale Abschaltzeit müssen
am Board gemessen werden. Ein unabhängiger Hardware-Abschaltweg bleibt nötig.

## STOP und Reset

`{"case":"stop"}` verriegelt global. Backend entfernt alle aktiven Befehle
und wechselt die Epoch. ESP deaktiviert OE vor dem Leeren der Register,
verwirft Bewegungen und meldet `{"case":"stop_state","stopped":true}`.
STOP bleibt auf dem Controller bei Wiederverbindungen erhalten.

Der Bediener kann `{"case":"reset_stop"}` anfordern. Das Backend bleibt
gesperrt und sendet allen registrierten Controllern:

```json
{"case":"reset_stop","reset_id":"unique-reset-id"}
```

Jeder Controller leert seine Relais, hebt die Sperre auf und bestätigt:

```json
{"case":"stop_state","stopped":false,"reset_id":"unique-reset-id"}
```

Erst wenn alle passenden Bestätigungen innerhalb von drei Sekunden eingetroffen
sind, gibt das Backend mit neuer Epoch frei. Ein Abbruch oder STOP während des
Resets verwirft die Freigabe. Verspätete Bestätigungen passen nicht zum nächsten
Reset. Kein Reset schaltet selbst ein Relais ein.

## Abbrüche und Fehler

- Bedienerverbindung während einer aktiven Bewegung beendet: globaler STOP.
- Jeder Abbruch einer registrierten Controller-Verbindung: globaler STOP,
  auch ohne aktive Bewegung. So verlieren vor dem Ausfall erzeugte Starts
  ihre Freigabe; nach Wiederverbindung ist ein neuer Reset erforderlich.
- Browser verliert Fokus/Sichtbarkeit oder wird verlassen: lokale Tastendrücke
  beenden, Freigaben nicht mehr erneuern.
- Erneute Verbindung: nie alte Bewegungen nachsenden.
- Fehler: `{"case":"error","detail":"...","command_id":"optional-press-id"}`.

GPIO4/`power_state` ist eine Anzeige. Daraus wird keine neue Hardwarefunktion
oder Freigabeverriegelung abgeleitet.
