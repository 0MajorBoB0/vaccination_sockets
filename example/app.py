from threading import Lock
from flask import Flask, render_template, session, request, \
    copy_current_request_context, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room, \
    close_room, rooms, disconnect

# STEP 3: DB imports
import os
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager

# STEP 4: Admin imports
from functools import wraps

# STEP 5: Utility imports
import uuid
import random
import string
import datetime
from datetime import timezone

# Set this variable to "threading", "eventlet" or "gevent" to test the
# different async modes, or leave it set to None for the application to choose
# the best option based on installed packages.
async_mode = None

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode=async_mode, logger=True, engineio_logger=True, cors_allowed_origins="*")
thread = None
thread_lock = Lock()

# STEP 4: Admin configuration
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

# STEP 4: Admin helper functions
def require_admin():
    """Check if current user is logged in as admin."""
    return session.get("admin_ok") is True

def admin_required(f):
    """Decorator to require admin login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not require_admin():
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function


# STEP 5: Database configuration with connection pooling
DB_HOST = os.environ.get("DB_HOST", "GameTheoryUDE26.mysql.eu.pythonanywhere-services.com")
DB_USER = os.environ.get("DB_USER", "GameTheoryUDE26")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "UDE2020EM")
DB_NAME = os.environ.get("DB_NAME", "GameTheoryUDE26$vaccination_game")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))

# Create engine with connection pooling (prevents "too many connections" error)
db_engine = create_engine(
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
    poolclass=QueuePool,
    pool_size=10,           # Max 10 persistent connections
    max_overflow=20,        # Up to 20 additional connections in peaks
    pool_pre_ping=True,     # Check connection health before using
    pool_recycle=3600,      # Recycle connections after 1 hour
    echo=False,             # Don't log SQL queries
)

@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = db_engine.connect()
    try:
        yield conn
    finally:
        conn.close()


# STEP 5: Utility functions
def create_code(n=6):
    """Generate unique participant code (no confusing chars)."""
    chars = (string.ascii_uppercase + string.digits).replace("O","").replace("0","").replace("I","").replace("1","")
    return "".join(random.choice(chars) for _ in range(n))

def utc_now():
    """Get current UTC time (timezone-aware)."""
    return datetime.datetime.now(timezone.utc).replace(microsecond=0)

def iso_utc(dt):
    """Convert datetime to ISO string with Z suffix."""
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# STEP 5: Initialize database schema
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
                starting_balance DECIMAL(10,2) DEFAULT 500,
                created_at VARCHAR(30),
                archived TINYINT DEFAULT 0,
                status VARCHAR(20) DEFAULT 'lobby'
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
                created_at VARCHAR(30),
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
                cost DECIMAL(10,2),
                created_at VARCHAR(30),
                INDEX idx_session_round (session_id, round_number),
                INDEX idx_participant_round (participant_id, round_number),
                UNIQUE KEY ux_participant_round (participant_id, round_number)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """))

        conn.commit()

    print("✅ Database schema initialized successfully!")


def background_thread():
    """Example of how to send server generated events to clients."""
    count = 0
    while True:
        socketio.sleep(10)
        count += 1
        socketio.emit('my_response',
                      {'data': 'Server generated event', 'count': count})


@app.route('/')
def index():
    return render_template('index.html', async_mode=socketio.async_mode)


# STEP 2: Test route to verify app still works after changes
@app.route('/healthz')
def healthz():
    return "OK - Step 2: Test route works!", 200


# STEP 3: Test DB connection
@app.route('/test_db')
def test_db():
    try:
        with get_db() as conn:
            result = conn.execute(text("SELECT 1"))
            return "OK - Step 3: DB connection works!", 200
    except Exception as e:
        return f"ERROR - Step 3: {str(e)}", 500


# STEP 5: Initialize database schema
@app.route('/init_db')
@admin_required
def init_db_route():
    """Initialize database schema (admin only)."""
    try:
        init_db()
        return "OK - Step 5: Database schema initialized!", 200
    except Exception as e:
        return f"ERROR - Step 5: {str(e)}", 500


# STEP 4: Admin routes
@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    """Admin login page."""
    if request.method == "POST":
        password = request.form.get("password", "").strip()
        if password == ADMIN_PASSWORD:
            session["admin_ok"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            return render_template("admin_login.html", error="Falsches Passwort!")
    return render_template("admin_login.html", error=None)

@app.route("/admin_logout")
def admin_logout():
    """Admin logout."""
    session.pop("admin_ok", None)
    return redirect(url_for("admin_login"))

@app.route("/admin")
@admin_required
def admin_dashboard():
    """Admin dashboard - shows all sessions."""
    return render_template("admin_dashboard.html")


@socketio.event
def my_event(message):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my_response',
         {'data': message['data'], 'count': session['receive_count']})


@socketio.event
def my_broadcast_event(message):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my_response',
         {'data': message['data'], 'count': session['receive_count']},
         broadcast=True)


@socketio.event
def join(message):
    join_room(message['room'])
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my_response',
         {'data': 'In rooms: ' + ', '.join(rooms()),
          'count': session['receive_count']})


@socketio.event
def leave(message):
    leave_room(message['room'])
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my_response',
         {'data': 'In rooms: ' + ', '.join(rooms()),
          'count': session['receive_count']})


@socketio.on('close_room')
def on_close_room(message):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my_response', {'data': 'Room ' + message['room'] + ' is closing.',
                         'count': session['receive_count']},
         to=message['room'])
    close_room(message['room'])


@socketio.event
def my_room_event(message):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my_response',
         {'data': message['data'], 'count': session['receive_count']},
         to=message['room'])


@socketio.on('*')
def catch_all(event, data):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my_response',
         {'data': [event, data], 'count': session['receive_count']})


@socketio.event
def disconnect_request():
    @copy_current_request_context
    def can_disconnect():
        disconnect()

    session['receive_count'] = session.get('receive_count', 0) + 1
    # for this emit we use a callback function
    # when the callback function is invoked we know that the message has been
    # received and it is safe to disconnect
    emit('my_response',
         {'data': 'Disconnected!', 'count': session['receive_count']},
         callback=can_disconnect)


@socketio.event
def my_ping():
    emit('my_pong')


@socketio.event
def connect():
    global thread
    with thread_lock:
        if thread is None:
            thread = socketio.start_background_task(background_thread)
    emit('my_response', {'data': 'Connected', 'count': 0})


# STEP 4: Admin Socket.IO events
@socketio.on('admin_connect')
def handle_admin_connect():
    """Admin connects to dashboard - join admin room for broadcasts."""
    if not require_admin():
        return {'error': 'Unauthorized'}

    join_room('admin_room')
    emit('admin_status', {'message': 'Connected to admin live updates'})
    print(f"Admin connected via Socket.IO: {request.sid}")

@socketio.on('admin_get_sessions')
def handle_admin_get_sessions():
    """Get all sessions - for now return empty array."""
    if not require_admin():
        return {'error': 'Unauthorized'}

    # For now, return empty sessions array
    # Later we'll query from database
    emit('admin_sessions_update', {'sessions': []})


@socketio.on('disconnect')
def test_disconnect(reason):
    print('Client disconnected', request.sid, reason)


if __name__ == '__main__':
    socketio.run(app)
