# Stress Test für Vaccination Game

## Übersicht

Dieses Script simuliert **echte Spieler** mit vollständigen HTTP-Sessions und Socket.IO-Verbindungen, um das System unter realistischer Last zu testen.

## Features

- ✅ Echte HTTP-Sessions mit Cookies
- ✅ Echte Socket.IO WebSocket-Verbindungen
- ✅ Parallele Sessions mit je 6 Spielern
- ✅ 20 Runden pro Session
- ✅ Realistische Delays und zufällige Entscheidungen
- ✅ Vollständige Simulation des Spielablaufs

## Installation

```bash
# Dependencies installieren (falls noch nicht vorhanden)
pip install requests python-socketio
```

## Verwendung

### 1. Server URL konfigurieren

Öffne `stress_test_real_players.py` und ändere die URL:

```python
# Für lokalen Test:
SERVER_URL = "http://localhost:5000"

# Für PythonAnywhere:
SERVER_URL = "https://deinusername.pythonanywhere.com"
```

### 2. Anzahl Sessions anpassen

```python
SESSIONS_TO_CREATE = 5  # Anzahl paralleler Sessions
PLAYERS_PER_SESSION = 6  # Immer 6
# = 30 Spieler total
```

### 3. Stresstest starten

```bash
cd /home/user/vaccination_sockets
python3 stress_test_real_players.py
```

## Test-Szenarien

### Klein (30 Spieler)
```python
SESSIONS_TO_CREATE = 5
# = 5 Sessions × 6 Spieler = 30 Spieler
```

### Mittel (60 Spieler)
```python
SESSIONS_TO_CREATE = 10
# = 10 Sessions × 6 Spieler = 60 Spieler
```

### Groß (150 Spieler)
```python
SESSIONS_TO_CREATE = 25
# = 25 Sessions × 6 Spieler = 150 Spieler
```

### Sehr Groß (300 Spieler)
```python
SESSIONS_TO_CREATE = 50
# = 50 Sessions × 6 Spieler = 300 Spieler
```

## Was wird getestet?

1. **Session-Erstellung**: Admin erstellt Sessions via HTTP
2. **Player-Joins**: Spieler joinen mit Codes (HTTP + Cookies)
3. **Socket.IO-Verbindungen**: Jeder Spieler etabliert WebSocket
4. **Gameplay**: 20 Runden mit echten HTTP-Requests für Choices
5. **Real-time Updates**: Socket.IO Events für Round Results
6. **Database-Load**: Alle Decisions, Updates, Queries unter Last
7. **Concurrency**: Parallele Sessions und Spieler

## Ausgabe

```
============================================================
VACCINATION GAME STRESS TEST
============================================================
Server URL: http://localhost:5000
Sessions to create: 5
Players per session: 6
Total players: 30
============================================================

⚠️  Press ENTER to start the stress test...

============================================================
Creating Session 1: Stresstest-1
============================================================
✅ Session created with 6 participant codes

[Session 1] Starting player joins...
[20:15:30] Player S1P1: Joined with code ABC123
[20:15:31] Player S1P2: Joined with code DEF456
...
✅ [Session 1] All 6 players joined!
[20:15:35] Player S1P1: Chose A for round 1
[20:15:36] Player S1P1: Round 1 result received
...
🎉 [Session 1] Game completed!

============================================================
Progress: 1/5 sessions completed
============================================================
```

## Performance-Metriken

Nach dem Test kannst du folgendes überprüfen:

1. **Response Times**: Wie schnell antwortet der Server?
2. **Database Load**: MySQL CPU/Memory in PythonAnywhere
3. **Fehlerrate**: Wie viele Requests fehlschlagen?
4. **Socket.IO Stability**: Bleiben Connections stabil?
5. **Memory Usage**: Wächst der Speicher kontinuierlich?

## Troubleshooting

### "Connection refused"
- Server läuft nicht oder falsche URL

### "Admin login failed"
- Admin-Passwort ändern in Zeile 113: `"password": "adminpw"`

### "Not enough codes generated"
- Session-Erstellung fehlgeschlagen, check Server-Logs

### Script hängt
- Ctrl+C zum Abbrechen
- Check Server-Logs für Errors

## Empfehlung

Starte mit **5 Sessions (30 Spieler)** und steigere schrittweise:
- 5 → 10 → 15 → 20 → 25 Sessions

So siehst du ab wann die DB oder der Server Probleme bekommt.
