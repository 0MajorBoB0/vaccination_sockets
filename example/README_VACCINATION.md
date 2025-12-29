# Vaccination Game - Socket.IO Version

Spieltheoretisches Experiment für 150+ Teilnehmer mit Socket.IO statt Polling.

## 🎯 Warum Socket.IO?

**Vorher (Polling):**
- 150 Clients × 0.5 requests/sec = **75 requests/sec**
- **~6.5 Millionen requests/Tag** nur für Status-Abfragen
- Hohe CPU- und DB-Last

**Nachher (Socket.IO):**
- Events nur bei Änderungen
- **~1000x weniger Server-Last**
- Echtzeit-Updates für bessere UX

## 🚀 Quick Start

### 1. Dependencies installieren

```bash
pip install -r requirements_game.txt
```

### 2. Datenbank erstellen

```bash
# MySQL/MariaDB
mysql -u root -p
```

```sql
CREATE DATABASE vaccination_game CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'vaccination_user'@'localhost' IDENTIFIED BY 'vaccination_pass';
GRANT ALL PRIVILEGES ON vaccination_game.* TO 'vaccination_user'@'localhost';
FLUSH PRIVILEGES;
```

### 3. Environment-Variablen setzen

```bash
cp .env.example .env
# Dann .env editieren mit deinen Werten
```

### 4. App starten

```bash
python app_vaccination.py
```

Die App läuft dann auf `http://localhost:5000`

## 📊 Connection Pooling

Die App nutzt SQLAlchemy Connection Pooling:
- **Max 10 persistente Connections**
- **+20 Overflow-Connections** in Spitzen
- **Automatisches Recycling** nach 1 Stunde

→ Kein "too many connections" Error bei 150 Teilnehmern! ✅

## 🏗️ Entwicklungs-Status

- [x] DB-Schema + Connection Pooling
- [ ] Admin-Login
- [ ] Session erstellen
- [ ] Join-Funktion
- [ ] Lobby mit Socket.IO
- [ ] Round/Wait/Reveal mit Socket.IO

## 📝 Migration vom alten Code

Wir bauen **schrittweise** auf, nicht alles auf einmal:

1. **Phase 1:** DB + Admin + Session-Erstellung
2. **Phase 2:** Join + Lobby (mit Socket.IO!)
3. **Phase 3:** Spiel-Loop (Round/Wait/Reveal)

## 🔧 Für PythonAnywhere

```python
# In WSGI file:
from example.app_vaccination import app, socketio

# Socket.IO auf PythonAnywhere:
# - Benötigt "Web Developer" Plan oder höher
# - Max Connections prüfen!
```
