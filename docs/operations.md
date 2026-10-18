# Betrieb und Inbetriebnahme

## Netzwerk und Zugang

Die Standardinstallation ist für ein vertrauenswürdiges LAN oder VPN bestimmt.
Bediener haben keinen Login; jedes Gerät mit Netzzugriff kann prinzipiell
bedienen und STOP zurücksetzen. Browser-Verbindungen fremder Origins werden
abgewiesen; dies ersetzt keine Benutzeranmeldung. Nur das Steuerungsnetz/VPN
darf den veröffentlichten Port erreichen. Keine Internetfreigabe oder
gemeinsam mit fremden Nutzern verwendete WLAN-Zone.

Compose bindet ohne `.env` an `127.0.0.1:8080`. Für reale Controller die feste
LAN-IP des Servers als `SMARTLIFT_BIND_ADDRESS` eintragen und die Firewall auf
das Steuerungsnetz begrenzen. Der Stack liefert HTTP; der bisherige scheinbare
HTTPS-Port ohne Zertifikatskonfiguration wurde entfernt. Bei TLS vor dem Stack
den tatsächlichen TLS-Endpunkt und dessen CA im ESP konfigurieren.

`SMARTLIFT_CONTROLLER_TOKEN` ist optional und muss als `controller_token` in
allen ESPs hinterlegt sein. Es authentifiziert sowohl WebSocket als auch OTA.
Der Browsersimulator sendet dieses Token nicht und ist dann nicht zugelassen.
Token und WLAN-Passwort nicht ins Repository aufnehmen. HTTP verschlüsselt
weder Token noch Firmware; dafür TLS oder ein vollständig geschütztes
Steuerungsnetz verwenden. OTA prüft ohne zusätzliche Signatur die Herkunft
über den gewählten Transport; eine kryptografische Firmware-Signatur ist noch
nicht eingerichtet.

Traefik verwendet feste Dienste aus `deploy/traefik.yml` und benötigt keinen
Docker-Socket. Frontend und Backend laufen ohne Rootrechte, mit begrenzten
Logs und schreibgeschütztem Root-Dateisystem. Schreibbar ist die Namensdatenbank
unter `data/`. Backend und Frontend besitzen Healthchecks. Ein als unhealthy
markierter Container wird durch Compose allein nicht automatisch neu gestartet;
der Prozessneustart greift bei tatsächlichem Beenden.

Bei einem internen Watchdog-Fehler bleibt die Steuerung absichtlich bis zum
Backend-Neustart gesperrt; die Freigabetaste hebt diesen Zustand nicht auf.
Zuerst die Fehlerursache in den Backend-Logs prüfen. Die Health-API liefert
dabei 503, ohne allein einen Compose-Neustart auszulösen.

## Aktualisierung von Protokoll 1

1. Anlage stillsetzen und unbeabsichtigte Bewegung während der Arbeiten
   unabhängig von der Weboberfläche verhindern.
2. `.env`, vorhandene ESP-Konfigurationen, Zertifikate, Firmware und Namen
   sichern. `lift_info.json` nach `data/lift_info.json` übernehmen; `init.sh`
   erledigt dies einmalig ohne bestehende Daten zu überschreiben.
3. Neue Firmware bauen, Konfigurationen prüfen und Backend/Frontend gemeinsam
   aktualisieren. Alte Controller werden bewusst nicht mehr freigegeben.
4. ESP-Firmware und LittleFS aufspielen. Läuft eine alte Firmware noch, kann
   deren OTA-Prüfung beim Neustart das bereitgestellte neue Image laden; das ist
   kein Ersatz für die kontrollierte Inbetriebnahme.
5. Funktionsprüfungen zunächst bei von den Lift-Eingängen getrennten
   Relaisausgängen durchführen. Erst anschließend unter kontrollierten
   Bedingungen an der Anlage prüfen.

## Noch am realen Board zu prüfen

Die folgenden Prüfungen sind durch Softwaretests nicht abgedeckt und wurden in
dieser Entwicklungsumgebung nicht ausgeführt:

- Pin- und Relaiszuordnung für jeden Lift sowie tatsächliche Bedeutung von OE
  HIGH/hochohmigen Ausgängen und vorhandenen Pull-Widerständen prüfen.
- Einschalten, ESP-Reset, Bootloader und Firmware-Update dürfen keinen
  unbeabsichtigten Relaisimpuls erzeugen. Auch GPIO2 beim Booten prüfen.
- Halten und Loslassen jeder Funktion; gleichzeitige Gegenrichtung und ein
  zweiter Bediener dürfen keine konkurrierenden Relais aktivieren.
- Während des Haltens: Browser schließen, Telefon sperren, Tab wechseln,
  WLAN trennen, Access Point neu starten und Backend-Prozess beenden.
  Tatsächliche Abschaltzeiten messen und dokumentieren.
- STOP während mehrerer aktiver Lifte, Reset mit gehaltenem Finger und
  Wiederverbindung testen: kein automatischer Wiederanlauf.
- Einen Controller während Reset ausschalten: globale Freigabe muss ausbleiben.
- Netzwerkpakete verzögern/verlieren: abgelaufene Erneuerungen dürfen nicht neu
  starten; unter Last gemessene Abschaltzeit festhalten.
- Versorgungssignal sowie parallel verdrahtete physische Taster prüfen. Sie
  liegen außerhalb der Softwareverriegelung.
- Mehrstündigen Betrieb mit WLAN-Unterbrechungen durchführen, Speicher,
  Neustarts und Logs beobachten; danach Neustart/Restore wiederholen.

Die 500-/750-ms-Fristen sind Softwaregrenzen innerhalb kooperativer Schleifen,
keine zugesicherte mechanische Stoppzeit. Die Abhängigkeit vom ESP, seinen
Bibliotheken und dessen Stromversorgung bleibt bestehen. Ein Web-STOP ist kein
unabhängiger Not-Halt; die bestehende Anlagensteuerung und ein geeigneter
Hardware-Abschaltweg müssen separat wirksam bleiben.

## Alltag, Diagnose und Sicherungen

### ESP verbindet sich nicht

`docker compose ps` zeigt den veröffentlichten Port. Bei
`127.0.0.1:8080->8080/tcp` können Controller aus dem LAN den Server nicht
erreichen. In `.env` `SMARTLIFT_BIND_ADDRESS` auf die LAN-IP setzen; wenn auch
`http://localhost:8080/` erreichbar bleiben soll, kann auf einem durch Firewall
geschützten LAN-/VPN-Host ausdrücklich `0.0.0.0` verwendet werden. Danach den
Proxy mit `docker compose up -d traefik` neu erstellen. Im ESP muss `server`
die LAN-IP/DNS-Adresse dieses Hosts enthalten, niemals `localhost`.

arduinoWebSockets 2.6.1 sendet ohne Anpassung `Origin: file://`. Firmware ab
`0.06.01` entfernt diesen künstlichen Header. Das Backend akzeptiert ihn zur
Kompatibilität ausschließlich bei Controller-IDs; Browser-Origins werden
weiter geprüft und ein konfiguriertes Controller-Token bleibt erforderlich.
Bei Origin- oder Token-Ablehnung protokolliert das Backend jetzt die Ursache.
Eine unpassende `con_id`, ein falscher Pfad oder inkompatibles Hello wird nicht
durch Lockerung dieser Prüfungen behoben.

### Browser meldet einen blockierten file-Zugriff

Die Oberfläche wird über HTTP/HTTPS geöffnet. Ihre gebauten Assets und API-URLs
enthalten keine `file://`-Ziele. Die genaue Datei-/Zeilenangabe aus der
Browserkonsole sowie der fehlgeschlagene Request im Netzwerktab helfen, den
Auslöser einzugrenzen. Ein frisches Browserprofil ohne Erweiterungen kann
zwischen Anwendung und Browser-Erweiterung unterscheiden. Lokale Dateizugriffe
nicht als Umgehung im Browser freischalten.

### Laufenden Zustand prüfen

```bash
docker compose ps
docker compose logs --tail=100 backend
docker compose logs --tail=100 traefik
curl --fail http://<LAN-IP>:8080/api/health
```

`/api/health` bestätigt auch den laufenden Bewegungs-Watchdog, nicht die
Verfügbarkeit jedes Controllers. Die Oberfläche zeigt Controller getrennt als
bereit/gesperrt/offline. Offline-Karten bleiben stehen, damit sich die
Bedienoberfläche nicht unter einem gehaltenen Finger verschiebt. Der grüne
Versorgungsindikator zeigt Spannung und misst keine Bewegung.

Die Liste bekannter Controller ist aktuell nicht persistent. Nach Neuladen des
Browsers werden nur seitdem registrierte Controller angezeigt; für eine
vollständige Anlagenüberwachung wäre ein festes Soll-Inventar erforderlich.

Nach Neustart oder STOP alle Tasten loslassen und bewusst freigeben.
Fehlgeschlagene Freigabe: Controller-Verbindung/Logs prüfen, danach erneut
anfordern. Nicht durch wiederholtes Neustarten versuchen, STOP zu umgehen.

`data/lift_info.json`, `.env` sowie ESP-Konfigurationen/Zertifikate und das
zugehörige Firmwareimage sichern. Namen werden über eine temporäre Datei im
gleichen Verzeichnis atomar ersetzt. `data/` deshalb als Verzeichnis mounten;
kein einzelnes `lift_info.json` binden. Linux-UID/GID müssen Schreibzugriff auf
das Verzeichnis erlauben. Bei Schreibfehlern meldet die API einen Fehler und
behauptet keine erfolgreiche Speicherung.

Genau ein Backend-Prozess/Worker betreiben. Für horizontale Skalierung müssten
Verbindungsführung, Eigentümerschaft und STOP-Zustand zuerst gemeinsam
koordiniert werden. Host-Ruhezustand deaktivieren und nach Stromausfall
kontrollierten Neustart vorsehen. Die aktuelle Software führt nach jedem
Backend-Neustart bewusst keine Bewegung automatisch fort.

## Nachgewiesener Softwarestand

Die automatisierten Prüfungen umfassen Python-Backendtests einschließlich
WebSocket-Integration, Node-Frontendtests, den Frontend-Produktionsbuild,
NodeMCUv2-Firmwarebuilds und native Tests der C++-Relaiszustandsmaschine.
Der isolierte Protokolltest verwendet einen eigenen Backendprozess, temporäre
Daten und simulierte Controller. Nach einem Update müssen der laufende Stack
und die angeschlossenen Controller gesondert geprüft werden. Die oben genannten
Hardware-/Abschaltprüfungen bleiben erforderlich.
GitHub Actions ist vorbereitet und
wird erst nach einem Push auf GitHub ausgeführt.

Die tatsächlichen Frontend-Transport-/Tastendruckmodule wurden zusätzlich über
Vite mit einem laufenden Backend und Simulator verbunden. Der grafische
Browsertest ist vorhanden, konnte hier aber wegen eines nicht antwortenden
Headless-Edge-Renderers nicht abgeschlossen werden. Pointer-, Touch- und
Tastaturbedienung deshalb auch auf den vorgesehenen Endgeräten prüfen.
