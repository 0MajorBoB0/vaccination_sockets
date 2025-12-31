# Datenbank-Last-Analyse: 150 Spieler (25 Gruppen)

## 📊 Connection Pool Konfiguration

```python
pool_size=10           # 10 persistente Connections
max_overflow=20        # +20 bei Spitzen
→ TOTAL: 30 gleichzeitige DB-Connections möglich
```

## 🔍 Query-Last über 2 Stunden (20 Runden)

### Writes (kritisch)

| Operation | Anzahl | Verteilung | Queries/sec |
|-----------|--------|------------|-------------|
| **Join** (UPDATE participants) | 150 | Einmalig (Anfang) | ~5/sec (30 Sek) |
| **Choose** (INSERT decisions) | 3.000 | 20 Runden verteilt | ~0.4/sec |
| **Finalize Round** (siehe unten) | 3.000 UPDATEs | 25 Gruppen × 20 Runden | Peak: 25/sec |
| **Confirm Ready** (UPDATE participants) | 3.000 | Nach jeder Runde | ~0.4/sec |

**TOTAL:** ~9.000 writes über 2h = **~1.25 writes/sec** (Durchschnitt)

### Reads

| Operation | Anzahl | Queries/sec |
|-----------|--------|-------------|
| **get_participant_state()** | Bei jedem Page-Load | ~2-3/sec |
| **finalize_round Reads** | 25 Gruppen × 20 Runden | Peak: 50/sec |
| **Admin Dashboard** | Optional | ~0.1/sec |

---

## 🔴 KRITISCHES Problem: finalize_round()

### Aktueller Code (PROBLEMATISCH):

```python
def finalize_round(session_id, round_number):
    with get_db() as conn:
        # 4 SELECTs zum Vorbereiten
        # ...

        rows = rows_result.fetchall()  # 6 Spieler

        # ⚠️ LOOP über alle 6 Spieler:
        for row in rows:
            # 2 UPDATEs pro Spieler
            conn.execute(text("UPDATE decisions ..."))
            conn.execute(text("UPDATE participants ..."))

        conn.commit()  # Erst am Ende!
```

### Problem bei 25 parallelen Gruppen:

**Wenn alle Gruppen gleichzeitig Runde beenden:**

1. **25 Sessions** rufen `finalize_round()` gleichzeitig
2. Jede braucht **1 DB-Connection**
3. Jede macht **4 SELECTs + 12 UPDATEs** (6 Spieler × 2)
4. **TOTAL Peak:** 25 Connections gleichzeitig, 400 Queries in ~2-3 Sekunden

**→ Connection Pool: 30 verfügbar, 25 benötigt = ✅ OK (knapp!)**

---

## ⚠️ RACE CONDITION RISIKO

### Szenario:
```
Thread 1: finalize_round(session_A, round=5)
Thread 2: finalize_round(session_A, round=5)  # Duplicate!

→ Beide sehen "missing_count > 0"
→ Beide updaten dieselben Rows
→ Doppelte Berechnung!
```

### Aktueller Schutz:
```python
missing_result = conn.execute(text("""
    SELECT COUNT(*) as c
    FROM decisions
    WHERE session_id = :sid AND round_number = :r
    AND total_cost IS NULL  # ← Dieser Check
"""))

# UPDATE mit WHERE Clause:
conn.execute(text("""
    UPDATE decisions
    SET total_cost = :cost, payout = :payout, others_A = :others_A
    WHERE id = :did AND total_cost IS NULL  # ← Idempotent
"""))
```

✅ **Durch `AND total_cost IS NULL` ist es idempotent**
→ Zweiter Aufruf findet nichts zu updaten
→ **KEIN kritisches Problem**, aber ineffizient

---

## 🔍 PythonAnywhere MySQL Limits

### Premium Plan ($12/Monat):
- **Max Connections:** 100-300 (abhängig vom shared Server)
- **Connection Timeout:** 60 Sekunden
- **Query Timeout:** 300 Sekunden
- **Disk Space:** 1 GB

### Dein Pool (30) vs. Limit (100+):
✅ **Kein Problem** - gut unter dem Limit

---

## 📈 Worst-Case Peak-Analyse

### Szenario: Alle 150 Spieler klicken gleichzeitig

**Runden-Start (alle drücken "Choose" gleichzeitig):**
```
150 × POST /choose
→ 150 × INSERT INTO decisions
→ Verteilt auf 5 Workers
→ ~30 gleichzeitige DB-Connections
→ Pool: 10 + 20 overflow = 30 total
```

**Status:** ✅ Grenzwertig OK, aber kein Puffer!

**Runden-Ende (25 Gruppen finalisieren gleichzeitig):**
```
25 × finalize_round()
→ 25 DB-Connections
→ Je 4 SELECTs + 12 UPDATEs
→ ~2-3 Sekunden Duration
→ Pool: 10 + 15 overflow benötigt
```

**Status:** ✅ OK

---

## 🎯 Datenbank-Risiko-Bewertung

| Risiko | Wahrscheinlichkeit | Impact | Mitigation |
|--------|-------------------|--------|------------|
| **Connection Pool erschöpft** | 🟡 Mittel | 🔴 Hoch | Pool ist OK (30), aber kein Puffer |
| **Race Condition in finalize_round** | 🟢 Niedrig | 🟡 Mittel | Idempotent durch WHERE Clause |
| **MySQL Server Limit** | 🟢 Niedrig | 🔴 Hoch | Premium Plan hat 100+ Limit |
| **Slow Query Timeout** | 🟢 Niedrig | 🟡 Mittel | Queries sind einfach + indexed |
| **Disk Space** | 🟢 Niedrig | 🟡 Mittel | 150 Spieler × 20 Runden = ~50 MB |

---

## ✅ Empfehlungen

### 1. Connection Pool erhöhen (OPTIONAL, aber sicherer):
```python
db_engine = create_engine(
    f"mysql+pymysql://...",
    pool_size=15,        # +5 (war 10)
    max_overflow=25,     # +5 (war 20)
    # → TOTAL: 40 statt 30
)
```

### 2. Transaction in finalize_round() hinzufügen:
```python
def finalize_round(session_id, round_number):
    with get_db() as conn:
        # Explizite Transaction mit LOCK
        trans = conn.begin()
        try:
            # ... existing code ...
            trans.commit()
        except:
            trans.rollback()
            raise
```

### 3. Batch-Updates statt Loop (BESSER):
```python
# Statt Loop mit 12 einzelnen UPDATEs:
for row in rows:
    conn.execute(...)  # 12× pro Runde

# BESSER - 1 Query mit CASE WHEN:
conn.execute(text("""
    UPDATE decisions
    SET total_cost = CASE
        WHEN participant_id = :pid1 THEN :cost1
        WHEN participant_id = :pid2 THEN :cost2
        ...
    END
    WHERE session_id = :sid AND round_number = :r
"""))
```

### 4. Monitoring während Stress-Test:
```python
# Vor dem Test:
SHOW PROCESSLIST;  # Aktive Connections
SHOW STATUS LIKE 'Threads_connected';
```

---

## 🎯 FINALE BEWERTUNG: Datenbank

**Werden Datenbank-Probleme auftreten?**

### ✅ WAHRSCHEINLICH NICHT - ABER KNAPP!

**Pro:**
- ✅ Connection Pool (30) ausreichend für Peak (25-30)
- ✅ Idempotente Queries (kein Duplicate-Problem)
- ✅ Einfache Queries mit Indexes
- ✅ PythonAnywhere Limit (100+) weit über deinem Pool

**Contra:**
- ⚠️ **Kein Puffer** bei Peak-Load (30 Pool vs. 30 benötigt)
- ⚠️ Loop in finalize_round ineffizient (12 UPDATEs)
- ⚠️ Keine expliziten Transactions

### Empfehlung:

1. **Minimale Änderung:** Pool auf 40 erhöhen (5 Min Arbeit)
2. **Optional:** Batch-Updates implementieren (30 Min Arbeit)
3. **WICHTIG:** Stress-Test mit DB-Monitoring durchführen

**Risiko-Level:** 🟡 MITTEL-NIEDRIG (2/5)

Die DB wird wahrscheinlich halten, aber es gibt keinen Sicherheitspuffer.
