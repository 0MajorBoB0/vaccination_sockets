# Kapazitätsbewertung: 150 Spieler auf PythonAnywhere Premium

**Szenario:** 150 Spieler in 25 Gruppen à 6 Spieler, 20 Runden über ~2 Stunden

## ✅ SocketIO-Architektur (VIEL BESSER!)

### Connection Pooling ✅
```python
pool_size=10           # 10 persistente DB-Connections
max_overflow=20        # +20 bei Spitzen = 30 max
pool_pre_ping=True     # Health checks
pool_recycle=3600      # 1h Recycling
```
**Bewertung:** Optimal konfiguriert!

### Request-Last mit SocketIO

**HTTP Requests (nur Actions, kein Polling!):**
- Join: 150 × 1 = 150
- Choose (20 Runden): 150 × 20 = 3.000
- Confirm Ready (20 Runden): 150 × 20 = 3.000
- Static Assets: ~1.000
- **TOTAL über 2h:** ~7.000 Requests = **~1 req/sec** ✅

**WebSocket Connections:**
- 150 persistente Connections
- Event-basierte Updates (kein Polling!)

---

## 📊 Ressourcen-Analyse

### 1. Worker-Kapazität ✅
| Metrik | Benötigt | Verfügbar | Status |
|--------|----------|-----------|--------|
| Concurrent Connections | 150 | 500-5.000* | ✅ OK |
| HTTP req/sec | ~1-3 | 20-50 | ✅ OK |
| Workers | 3-4 | 5 | ✅ OK |

*Mit eventlet/gevent: 1.000+ Connections pro Worker möglich

### 2. CPU-Sekunden ⚠️
| Szenario | CPU-Zeit | Verfügbar | Status |
|----------|----------|-----------|--------|
| 2h Session | 8.000-12.000 | 5.000/Tag | ⚠️ KNAPP |
| Mit Pausen | 5.000-8.000 | 5.000/Tag | ⚠️ GRENZWERTIG |

### 3. Datenbank ✅
| Metrik | Benötigt | Verfügbar | Status |
|--------|----------|-----------|--------|
| Peak Connections | 25-30 | 30 (pool) | ✅ OK |
| Writes/sec | 5-10 | 50+ | ✅ OK |

---

## 🔴 Kritische Anforderungen

### MUSS erfüllt sein:

1. **async_mode = 'eventlet'** (aktuell: `None`)
   ```python
   # In app.py Zeile 26 ändern:
   async_mode = 'eventlet'
   ```

2. **eventlet installieren:**
   ```bash
   pip install eventlet
   ```

3. **PythonAnywhere WebSocket Support:**
   - ✅ Premium Plan unterstützt WebSockets
   - URL muss HTTPS sein (ist bei PythonAnywhere Standard)

4. **WSGI-Konfiguration:**
   ```python
   # In WSGI file:
   from app import app, socketio
   application = socketio.run(app)
   ```

---

## 🎯 Gesamtbewertung

### ✅ MACHBAR - mit folgenden Bedingungen:

**JA, es sollte funktionieren wenn:**

1. ✅ `async_mode = 'eventlet'` gesetzt
2. ✅ `eventlet` installiert
3. ✅ WSGI korrekt konfiguriert
4. ⚠️ CPU-Budget im Auge behalten (close call)
5. ✅ Stress-Test vorher durchführen!

**Worst Case Backup:**
- Bei CPU-Limit: Sessions zeitversetzt (3× 50 Spieler)
- Oder: Upgrade auf Hacker Plan ($50/Monat) für 20k CPU-Sekunden

---

## 🧪 Empfohlener Test-Plan

### Phase 1: Kleine Tests (10-30 Spieler)
```bash
# Im Admin-Dashboard:
Stress Test → 5 Sessions (30 Spieler)
```

### Phase 2: Mittlerer Test (60-90 Spieler)
- 15 Gruppen simulieren
- CPU-Verbrauch monitoren

### Phase 3: Full Load Test (150 Spieler)
- 25 Gruppen
- Mindestens 1h vor der echten Studie!

---

## 📝 Checkliste vor der Studie

- [ ] `async_mode = 'eventlet'` in app.py
- [ ] `pip install eventlet` ausgeführt
- [ ] WSGI file updated mit `socketio.run(app)`
- [ ] Stress-Test mit 150 Spielern erfolgreich
- [ ] CPU-Verbrauch unter 5k für Test-Session
- [ ] Backup-Plan bei CPU-Limit (zeitversetzt)
- [ ] Admin-Dashboard getestet
- [ ] Export funktioniert (XLSX Download)

---

## 🔧 Kritische Code-Änderungen

### 1. app.py Zeile 26:
```python
# VORHER:
async_mode = None

# NACHHER:
async_mode = 'eventlet'
```

### 2. WSGI Configuration:
```python
import sys
path = '/home/GameTheoryUDE26/vaccination_sockets/example'
if path not in sys.path:
    sys.path.insert(0, path)

from app import app, socketio

# WICHTIG: socketio.run() statt nur app!
application = socketio
```

### 3. requirements.txt:
```
eventlet>=0.33.0
flask-socketio>=5.3.0
python-socketio>=5.9.0
python-engineio>=4.7.0
...
```

---

## 💡 Fazit

**Mit SocketIO + Connection Pooling: JA, 150 Spieler sind machbar!**

Die Architektur ist solide - nur `async_mode` muss auf `eventlet` gesetzt werden.

**Risiko-Level:** 🟡 MITTEL (CPU-Budget knapp)

**Empfehlung:**
1. Sofort `async_mode = 'eventlet'` setzen
2. Stress-Test mit 150 Spielern durchführen
3. CPU-Verbrauch messen
4. Bei Bedarf auf zeitversetzte Sessions ausweichen
