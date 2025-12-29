"""
Vaccination Game - Socket.IO Version
Step-by-step implementation for 150+ participants
"""

import os
import uuid
import random
import string
import datetime
from datetime import timedelta, timezone
from contextlib import contextmanager

from flask import Flask, render_template, session as flask_session, request, redirect, url_for, g
from flask_socketio import SocketIO, emit, join_room, leave_room
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from sqlalchemy.orm import sessionmaker, scoped_session

# ==================== CONFIGURATION ====================

APP_DIR = os.path.dirname(os.path.abspath(__file__))

def must_get_env(name: str) -> str:
    """Read required environment variables (fail fast if missing)."""
    val = os.environ.get(name)
    if not val or not val.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val

# Environment variables
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")  # Default for testing
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "vaccination_user")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "vaccination_pass")
DB_NAME = os.environ.get("DB_NAME", "vaccination_game")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

# Flask App
app = Flask(
    __name__,
    template_folder=os.path.join(APP_DIR, "templates"),
    static_folder=os.path.join(APP_DIR, "static"),
)
app.secret_key = SECRET_KEY
app.config["SESSION_PERMANENT"] = False

# Socket.IO with CORS for PythonAnywhere
socketio = SocketIO(
    app,
    async_mode=None,  # Auto-detect best mode (eventlet/gevent/threading)
    cors_allowed_origins="*",
    logger=True,
    engineio_logger=False
)

DEBUG_MODE = os.environ.get("FLASK_DEBUG", "0") == "1"
app.config["TEMPLATES_AUTO_RELOAD"] = DEBUG_MODE

# ==================== DATABASE SETUP ====================

# SQLAlchemy engine with connection pooling
# CRITICAL: Prevents "too many connections" errors with 150+ participants!
engine = create_engine(
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
    poolclass=QueuePool,
    pool_size=10,           # Max 10 persistent connections
    max_overflow=20,        # Up to 20 additional connections in peaks
    pool_pre_ping=True,     # Check connection health before using
    pool_recycle=3600,      # Recycle connections after 1 hour
    echo=DEBUG_MODE,        # Log SQL in debug mode
)

# Session factory (for manual queries)
SessionLocal = scoped_session(sessionmaker(bind=engine))

@contextmanager
def get_db():
    """
    Context manager for database connections.

    Usage:
        with get_db() as conn:
            result = conn.execute(text("SELECT * FROM sessions"))
    """
    conn = engine.connect()
    try:
        yield conn
    finally:
        conn.close()

# Teardown app context
@app.teardown_appcontext
def shutdown_session(exception=None):
    SessionLocal.remove()

# ==================== GAME CONSTANTS ====================

# Vaccination: Cost types (from original game)
TYPE_COST = {
    1: {"B": [4, 3, 2, 1, 0],  "A": 4},
    2: {"B": [8, 6, 4, 2, 0],  "A": 4},
    3: {"B": [4, 3, 2, 1, 0],  "A": 8},
    4: {"B": [8, 6, 4, 2, 0],  "A": 8},
    5: {"B": [24, 18, 12, 6, 0], "A": 32},
    6: {"B": [64, 48, 32, 16, 0], "A": 32},
}
B_COLS = 5

def a_cost_for(ptype: int) -> float:
    """Get cost for choosing option A."""
    return TYPE_COST.get(ptype, TYPE_COST[1])["A"]

def b_cost_adapt(ptype: int, others_A: int, N: int) -> float:
    """Calculate cost for option B based on how many others chose A."""
    if ptype not in TYPE_COST:
        ptype = 1
    b = TYPE_COST[ptype]["B"]
    N = max(1, int(N))
    others_A = max(0, min(int(others_A), max(0, N-1)))
    if N <= 1:
        return float(b[0])
    frac = others_A / float(N - 1)
    x = frac * B_COLS
    col = int(x + 0.5)
    col = max(1, min(B_COLS, col))
    return float(b[col - 1])

# ==================== UTILITIES ====================

def utc_now():
    """Get current UTC time (timezone-aware)."""
    return datetime.datetime.now(timezone.utc).replace(microsecond=0)

def iso_utc(dt: datetime.datetime) -> str:
    """Convert datetime to ISO string with Z suffix."""
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def parse_iso_utc(s: str) -> datetime.datetime:
    """Parse ISO string to datetime."""
    return datetime.datetime.fromisoformat((s or "").replace("Z", "+00:00"))

def create_code(n=6):
    """Generate unique participant code (no confusing chars)."""
    chars = (string.ascii_uppercase + string.digits).replace("O","").replace("0","").replace("I","").replace("1","")
    return "".join(random.choice(chars) for _ in range(n))

# ==================== DATABASE SCHEMA ====================

def init_db():
    """Initialize database schema with all required tables."""
    print("🔧 Initializing database schema...")

    with get_db() as conn:
        # Sessions table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS sessions (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(255),
                group_size INT,
                rounds INT,
                cvac DECIMAL(10,2),
                alpha DECIMAL(10,2),
                cinf DECIMAL(10,2),
                subsidy TINYINT DEFAULT 0,
                subsidy_amount DECIMAL(10,2) DEFAULT 0,
                regime VARCHAR(50),
                starting_balance DECIMAL(10,2) DEFAULT 500,
                created_at VARCHAR(30),
                archived TINYINT DEFAULT 0,
                reveal_window INT DEFAULT 5,
                watch_time INT DEFAULT 15,
                cost_mode VARCHAR(50) DEFAULT 'type_table'
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """))

        # Participants table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS participants (
                id VARCHAR(36) PRIMARY KEY,
                session_id VARCHAR(36),
                code VARCHAR(10) UNIQUE,
                theta DECIMAL(10,2),
                lambda DECIMAL(10,2),
                joined TINYINT DEFAULT 0,
                join_number INT,
                current_round INT DEFAULT 1,
                balance DECIMAL(10,2) DEFAULT 0,
                completed TINYINT DEFAULT 0,
                created_at VARCHAR(30),
                ptype INT,
                ready_for_next TINYINT DEFAULT 0,
                INDEX idx_session (session_id),
                INDEX idx_session_code (session_id, code)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """))

        # Decisions table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS decisions (
                id INT PRIMARY KEY AUTO_INCREMENT,
                session_id VARCHAR(36),
                participant_id VARCHAR(36),
                round_number INT,
                choice VARCHAR(1),
                a_cost DECIMAL(10,2),
                b_cost DECIMAL(10,2),
                total_cost DECIMAL(10,2),
                created_at VARCHAR(30),
                reveal TINYINT,
                payout DECIMAL(10,2),
                others_A INT,
                b_cost_round DECIMAL(10,2),
                base_payout DECIMAL(10,2),
                INDEX idx_session_round (session_id, round_number),
                INDEX idx_participant_round (participant_id, round_number),
                UNIQUE KEY ux_participant_round (participant_id, round_number)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """))

        # Round phases table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS round_phases (
                session_id VARCHAR(36),
                round_number INT,
                decision_ends_at VARCHAR(30),
                watch_ends_at VARCHAR(30),
                created_at VARCHAR(30),
                PRIMARY KEY (session_id, round_number)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """))

        conn.commit()

    print("✅ Database schema initialized successfully!")

# ==================== ADMIN HELPERS ====================

def require_admin():
    """Check if current user is logged in as admin."""
    return flask_session.get("admin_ok") is True

def admin_required(f):
    """Decorator to require admin login."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not require_admin():
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function

# ==================== ROUTES ====================

@app.route("/")
def index():
    """Landing page."""
    return "<h1>Vaccination Game - Socket.IO Version</h1><p>Admin: <a href='/admin_login'>Login</a></p>"

@app.route("/healthz")
def healthz():
    """Health check endpoint."""
    return "ok", 200

# ==================== ADMIN ROUTES ====================

@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    """Admin login page."""
    if request.method == "POST":
        password = request.form.get("password", "").strip()
        if password == ADMIN_PASSWORD:
            flask_session["admin_ok"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            return render_template("admin_login.html", error="Falsches Passwort!")
    return render_template("admin_login.html", error=None)

@app.route("/admin_logout")
def admin_logout():
    """Admin logout."""
    flask_session.pop("admin_ok", None)
    return redirect(url_for("admin_login"))

@app.route("/admin")
@admin_required
def admin_dashboard():
    """Admin dashboard - shows all sessions."""
    with get_db() as conn:
        # Get all sessions
        result = conn.execute(text("""
            SELECT id, name, group_size, rounds, starting_balance, created_at, archived
            FROM sessions
            ORDER BY created_at DESC
        """))
        sessions = [dict(row._mapping) for row in result]

    return render_template("admin_dashboard.html", sessions=sessions)

# ==================== MAIN ====================

if __name__ == "__main__":
    print("=" * 60)
    print("🎮 VACCINATION GAME - SOCKET.IO VERSION")
    print("=" * 60)
    print(f"📊 DB: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f"🔒 Admin Password: {ADMIN_PASSWORD}")
    print(f"🐛 Debug Mode: {DEBUG_MODE}")
    print("=" * 60)

    # Initialize database
    init_db()

    # Run with Socket.IO
    socketio.run(
        app,
        host="0.0.0.0",
        port=5000,
        debug=DEBUG_MODE
    )
