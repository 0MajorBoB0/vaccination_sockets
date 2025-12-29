"""
Minimaler Test: Nur DB-Verbindung checken
"""
import os
from sqlalchemy import create_engine, text

# DB Config (setze deine Werte als Environment-Variablen)
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "vaccination_user")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "vaccination_pass")
DB_NAME = os.environ.get("DB_NAME", "vaccination_game")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))

print("=" * 60)
print("🧪 TEST 1: DB-VERBINDUNG")
print("=" * 60)
print(f"📊 Host: {DB_HOST}:{DB_PORT}")
print(f"👤 User: {DB_USER}")
print(f"🗄️  Database: {DB_NAME}")
print("=" * 60)

try:
    # Engine erstellen
    print("\n1️⃣ Erstelle Connection Engine...")
    engine = create_engine(
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
        pool_pre_ping=True,
        echo=False
    )
    print("   ✅ Engine erstellt!")

    # Connection testen
    print("\n2️⃣ Teste Connection...")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1 as test"))
        row = result.fetchone()
        assert row[0] == 1
    print("   ✅ Connection funktioniert!")

    # Tabellen erstellen (nur wenn noch nicht existieren)
    print("\n3️⃣ Erstelle Tabellen...")
    with engine.connect() as conn:
        # Sessions table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS sessions (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(255),
                group_size INT,
                rounds INT,
                starting_balance DECIMAL(10,2) DEFAULT 500,
                created_at VARCHAR(30),
                archived TINYINT DEFAULT 0
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """))

        # Participants table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS participants (
                id VARCHAR(36) PRIMARY KEY,
                session_id VARCHAR(36),
                code VARCHAR(10) UNIQUE,
                joined TINYINT DEFAULT 0,
                join_number INT,
                current_round INT DEFAULT 1,
                balance DECIMAL(10,2) DEFAULT 0,
                completed TINYINT DEFAULT 0,
                ptype INT,
                INDEX idx_session (session_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """))

        conn.commit()
    print("   ✅ Tabellen erstellt!")

    # Tabellen überprüfen
    print("\n4️⃣ Überprüfe Tabellen...")
    with engine.connect() as conn:
        result = conn.execute(text("SHOW TABLES"))
        tables = [row[0] for row in result.fetchall()]
        print(f"   📋 Gefundene Tabellen: {tables}")

        if 'sessions' in tables and 'participants' in tables:
            print("   ✅ Alle wichtigen Tabellen existieren!")
        else:
            print("   ⚠️  Einige Tabellen fehlen!")

    print("\n" + "=" * 60)
    print("✅ ALLE TESTS BESTANDEN!")
    print("=" * 60)

except Exception as e:
    print(f"\n❌ FEHLER: {e}")
    print("\n💡 Mögliche Lösungen:")
    print("   1. Prüfe DB-Credentials (User/Password)")
    print("   2. Prüfe ob DB existiert (z.B. 'vaccination_game')")
    print("   3. Prüfe ob MySQL läuft")
    print("   4. Auf PythonAnywhere: DB-Name muss 'username$dbname' sein")
    import traceback
    traceback.print_exc()
