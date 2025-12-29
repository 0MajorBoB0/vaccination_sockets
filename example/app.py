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


# STEP 5.1: Migrate existing tables (add missing columns)
@app.route('/migrate_db')
@admin_required
def migrate_db():
    """Add missing columns to existing tables."""
    try:
        with get_db() as conn:
            # Check and add 'status' column to sessions table
            try:
                conn.execute(text("SELECT status FROM sessions LIMIT 1"))
            except:
                conn.execute(text("ALTER TABLE sessions ADD COLUMN status VARCHAR(20) DEFAULT 'lobby'"))

            # Check and add 'created_at' column to participants table
            try:
                conn.execute(text("SELECT created_at FROM participants LIMIT 1"))
            except:
                conn.execute(text("ALTER TABLE participants ADD COLUMN created_at VARCHAR(30)"))

            # Check and add 'ready_for_next' column to participants table
            try:
                conn.execute(text("SELECT ready_for_next FROM participants LIMIT 1"))
            except:
                conn.execute(text("ALTER TABLE participants ADD COLUMN ready_for_next TINYINT DEFAULT 0"))

            conn.commit()

        return "OK - Database migrated! Added status, created_at, ready_for_next columns.", 200
    except Exception as e:
        return f"ERROR - Migration failed: {str(e)}", 500


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

@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin_dashboard():
    """Admin dashboard - shows all sessions."""
    with get_db() as conn:
        # POST: Create new session
        if request.method == "POST":
            name = request.form.get("name", f"Session {datetime.datetime.now():%Y-%m-%d %H:%M}")
            group_size = int(request.form.get("group_size", "6"))
            rounds = int(request.form.get("rounds", "20"))
            starting_balance = float(request.form.get("base_payout", "500"))

            # Create session
            session_id = str(uuid.uuid4())
            conn.execute(text("""
                INSERT INTO sessions (id, name, group_size, rounds, starting_balance, created_at, archived, status)
                VALUES (:id, :name, :group_size, :rounds, :starting_balance, :created_at, 0, 'lobby')
            """), {
                "id": session_id,
                "name": name,
                "group_size": group_size,
                "rounds": rounds,
                "starting_balance": starting_balance,
                "created_at": iso_utc(utc_now())
            })

            # Create participants with unique codes
            for i in range(group_size):
                participant_id = str(uuid.uuid4())

                # Generate unique code
                while True:
                    code = create_code(6)
                    existing = conn.execute(text("SELECT 1 FROM participants WHERE code = :code"), {"code": code}).fetchone()
                    if not existing:
                        break

                conn.execute(text("""
                    INSERT INTO participants
                    (id, session_id, code, joined, join_number, current_round, balance, completed, created_at, ready_for_next)
                    VALUES (:id, :session_id, :code, 0, NULL, 1, :balance, 0, :created_at, 0)
                """), {
                    "id": participant_id,
                    "session_id": session_id,
                    "code": code,
                    "balance": starting_balance,
                    "created_at": iso_utc(utc_now())
                })

            conn.commit()

            # Notify all admin clients via Socket.IO
            socketio.emit('session_created', {'session_id': session_id}, room='admin_room')

            return redirect(url_for("admin_dashboard"))

        # GET: Show all sessions
        result = conn.execute(text("""
            SELECT id, name, group_size, rounds, starting_balance, created_at, archived, status
            FROM sessions
            ORDER BY created_at DESC
        """))
        sessions = [dict(row._mapping) for row in result]

        # Get participants for each session
        for s in sessions:
            p_result = conn.execute(text("SELECT code, joined FROM participants WHERE session_id = :sid"), {"sid": s["id"]})
            s["participants"] = [dict(row._mapping) for row in p_result]

    # Separate sessions by status
    sessions_active = [s for s in sessions if not s["archived"] and s["status"] == "lobby"]
    sessions_done = [s for s in sessions if not s["archived"] and s["status"] != "lobby"]
    sessions_arch = [s for s in sessions if s["archived"]]

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    return render_template("admin_dashboard.html",
                         sessions_active=sessions_active,
                         sessions_done=sessions_done,
                         sessions_arch=sessions_arch,
                         now=now)


@app.route("/admin/delete_session", methods=["POST"])
@admin_required
def admin_delete_session():
    """Delete a session and all its participants."""
    session_id = request.form.get("session_id")

    with get_db() as conn:
        # Delete decisions first (if any)
        conn.execute(text("DELETE FROM decisions WHERE session_id = :sid"), {"sid": session_id})

        # Delete participants
        conn.execute(text("DELETE FROM participants WHERE session_id = :sid"), {"sid": session_id})

        # Delete session
        conn.execute(text("DELETE FROM sessions WHERE id = :sid"), {"sid": session_id})

        conn.commit()

    # Notify admin clients
    socketio.emit('session_deleted', {'session_id': session_id}, room='admin_room')

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/archive_session", methods=["POST"])
@admin_required
def admin_archive_session():
    """Archive a session (set archived=1)."""
    session_id = request.form.get("session_id")

    with get_db() as conn:
        conn.execute(text("UPDATE sessions SET archived = 1 WHERE id = :sid"), {"sid": session_id})
        conn.commit()

    # Notify admin clients
    socketio.emit('session_archived', {'session_id': session_id}, room='admin_room')

    return redirect(url_for("admin_dashboard"))


# STEP 7: Participant routes
@app.route("/join", methods=["GET", "POST"])
def join():
    """Join a session with participant code."""
    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()

        with get_db() as conn:
            # Find participant by code
            result = conn.execute(text("""
                SELECT p.id, p.session_id, p.joined, p.join_number, s.status, s.archived
                FROM participants p
                JOIN sessions s ON p.session_id = s.id
                WHERE p.code = :code
            """), {"code": code})

            participant = result.fetchone()

            if not participant:
                return render_template("join.html", error="Ungültiger Code!")

            participant = dict(participant._mapping)

            # Check if session is archived
            if participant["archived"]:
                return render_template("join.html", error="Diese Session ist archiviert!")

            # Check if session is not in lobby (already started or finished)
            if participant["status"] != "lobby":
                return render_template("join.html", error="Diese Session ist bereits gestartet oder beendet!")

            # Store participant data in session
            session["participant_id"] = participant["id"]
            session["session_id"] = participant["session_id"]
            session["code"] = code

            # If not yet joined, mark as joined and assign join_number
            if not participant["joined"]:
                # Get max join_number for this session
                max_result = conn.execute(text("""
                    SELECT COALESCE(MAX(join_number), 0) as max_num
                    FROM participants
                    WHERE session_id = :sid AND joined = 1
                """), {"sid": participant["session_id"]})
                max_num = max_result.fetchone()[0]

                # Assign next join_number
                new_join_number = max_num + 1

                conn.execute(text("""
                    UPDATE participants
                    SET joined = 1, join_number = :join_num
                    WHERE id = :pid
                """), {"join_num": new_join_number, "pid": participant["id"]})

                conn.commit()

                # Notify all participants in this session's lobby via Socket.IO
                socketio.emit('lobby_update', {
                    'joined': new_join_number
                }, room=f"session_{participant['session_id']}")

            return redirect(url_for("lobby"))

    return render_template("join.html", error=None)


@app.route("/lobby")
def lobby():
    """Lobby - wait for all participants to join."""
    participant_id = session.get("participant_id")
    session_id = session.get("session_id")

    if not participant_id or not session_id:
        return redirect(url_for("join"))

    with get_db() as conn:
        # Get session info
        s_result = conn.execute(text("""
            SELECT id, name, group_size, rounds, starting_balance, status
            FROM sessions
            WHERE id = :sid
        """), {"sid": session_id})

        session_data = s_result.fetchone()

        if not session_data:
            return redirect(url_for("join"))

        session_data = dict(session_data._mapping)

        # Get participant info
        p_result = conn.execute(text("""
            SELECT id, code, joined, join_number
            FROM participants
            WHERE id = :pid
        """), {"pid": participant_id})

        participant = p_result.fetchone()

        if not participant:
            return redirect(url_for("join"))

        participant = dict(participant._mapping)

        # Count joined participants
        count_result = conn.execute(text("""
            SELECT COUNT(*) as joined_count
            FROM participants
            WHERE session_id = :sid AND joined = 1
        """), {"sid": session_id})

        joined_count = count_result.fetchone()[0]

    return render_template("lobby.html",
                         session=session_data,
                         participant=participant,
                         joined=joined_count)


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
    """Get all sessions from database."""
    if not require_admin():
        return {'error': 'Unauthorized'}

    with get_db() as conn:
        result = conn.execute(text("""
            SELECT id, name, group_size, rounds, starting_balance, created_at, archived, status
            FROM sessions
            ORDER BY created_at DESC
        """))
        sessions = []
        for row in result:
            s = dict(row._mapping)
            # Get participants for this session
            p_result = conn.execute(text("SELECT code, joined FROM participants WHERE session_id = :sid"), {"sid": s["id"]})
            s["participants"] = [dict(p._mapping) for p in p_result]
            sessions.append(s)

    emit('admin_sessions_update', {'sessions': sessions})


# STEP 7: Participant Socket.IO events
@socketio.on('join_lobby')
def handle_join_lobby(data):
    """Participant joins lobby room for real-time updates."""
    session_id = session.get("session_id")
    participant_id = session.get("participant_id")

    if not session_id or not participant_id:
        return {'error': 'Not authenticated'}

    # Join the session-specific room
    room = f"session_{session_id}"
    join_room(room)

    # Send current lobby status to this participant
    with get_db() as conn:
        # Count joined participants
        count_result = conn.execute(text("""
            SELECT COUNT(*) as joined_count
            FROM participants
            WHERE session_id = :sid AND joined = 1
        """), {"sid": session_id})

        joined_count = count_result.fetchone()[0]

        # Get session info
        s_result = conn.execute(text("""
            SELECT group_size, status
            FROM sessions
            WHERE id = :sid
        """), {"sid": session_id})

        session_data = s_result.fetchone()

        if session_data:
            session_dict = dict(session_data._mapping)
            emit('lobby_status', {
                'joined': joined_count,
                'group_size': session_dict['group_size'],
                'ready': joined_count >= session_dict['group_size']
            })

    print(f"Participant {participant_id} joined lobby room: {room}")


@socketio.on('disconnect')
def test_disconnect(reason):
    print('Client disconnected', request.sid, reason)


if __name__ == '__main__':
    socketio.run(app)
