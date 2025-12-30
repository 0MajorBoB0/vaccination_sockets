#!/usr/bin/env python3
"""
Realistic stress test for vaccination game.
Simulates real players with HTTP sessions and Socket.IO connections.
"""

import requests
import socketio
import time
import random
import threading
import string
from queue import Queue
from datetime import datetime

# Configuration
SERVER_URL = "http://localhost:5000"  # Change to your PythonAnywhere URL for real test
SESSIONS_TO_CREATE = 5  # Number of game sessions
PLAYERS_PER_SESSION = 6
TOTAL_PLAYERS = SESSIONS_TO_CREATE * PLAYERS_PER_SESSION

# Progress tracking
progress_lock = threading.Lock()
completed_sessions = 0
total_sessions = SESSIONS_TO_CREATE


class SimulatedPlayer:
    """Simulates a real player with HTTP session and Socket.IO connection."""

    def __init__(self, player_id, session_name, base_url):
        self.player_id = player_id
        self.session_name = session_name
        self.base_url = base_url
        self.http_session = requests.Session()
        self.sio = socketio.Client(logger=False, engineio_logger=False)
        self.participant_code = None
        self.participant_id = None
        self.current_round = 0
        self.session_id = None
        self.ready = False

    def log(self, message):
        """Thread-safe logging."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Player {self.player_id}: {message}")

    def generate_code(self):
        """Generate random participant code."""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    def setup_socketio_handlers(self):
        """Set up Socket.IO event handlers."""

        @self.sio.on('connect')
        def on_connect():
            self.log("Socket.IO connected")

        @self.sio.on('disconnect')
        def on_disconnect():
            self.log("Socket.IO disconnected")

        @self.sio.on('game_started')
        def on_game_started(data):
            self.log(f"Game started! Round 1/{data.get('total_rounds', 20)}")

        @self.sio.on('round_result')
        def on_round_result(data):
            round_num = data.get('round_number', 0)
            self.current_round = round_num
            self.log(f"Round {round_num} result received")
            # Mark ready for next round after short delay
            time.sleep(random.uniform(0.5, 1.5))
            self.mark_ready()

        @self.sio.on('game_finished')
        def on_game_finished(data):
            self.log("Game finished!")
            self.ready = True

    def create_session_as_admin(self):
        """Create a new game session (admin action)."""
        try:
            # Login as admin first
            resp = self.http_session.post(
                f"{self.base_url}/admin/login",
                data={"password": "adminpw"},  # Default admin password
                allow_redirects=True
            )

            if resp.status_code != 200:
                self.log(f"Admin login failed: {resp.status_code}")
                return None

            # Create session
            resp = self.http_session.post(
                f"{self.base_url}/admin/session/create",
                data={
                    "name": self.session_name,
                    "group_size": PLAYERS_PER_SESSION,
                    "rounds": 20,
                    "starting_balance": 500
                },
                allow_redirects=False
            )

            if resp.status_code in [200, 302]:
                self.log(f"Session '{self.session_name}' created")
                return True
            else:
                self.log(f"Session creation failed: {resp.status_code}")
                return None

        except Exception as e:
            self.log(f"Error creating session: {e}")
            return None

    def get_participant_codes(self):
        """Get participant codes from admin panel."""
        try:
            resp = self.http_session.get(f"{self.base_url}/admin/sessions")
            if resp.status_code == 200:
                # Parse HTML to extract codes (simple approach)
                # In production, you might want to add an API endpoint for this
                self.log("Retrieved session list")
                return True
            return None
        except Exception as e:
            self.log(f"Error getting codes: {e}")
            return None

    def join_with_code(self, code):
        """Join a session with participant code."""
        try:
            self.participant_code = code

            # Generate browser token
            browser_token = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32))

            # Join via HTTP POST
            resp = self.http_session.post(
                f"{self.base_url}/join",
                data={
                    "code": code,
                    "browser_token": browser_token
                },
                allow_redirects=False
            )

            if resp.status_code in [200, 302]:
                self.log(f"Joined with code {code}")

                # Connect Socket.IO with session cookies
                cookies = self.http_session.cookies.get_dict()
                cookie_string = "; ".join([f"{k}={v}" for k, v in cookies.items()])

                self.sio.connect(
                    self.base_url,
                    headers={"Cookie": cookie_string},
                    transports=['websocket', 'polling']
                )

                return True
            else:
                self.log(f"Join failed: {resp.status_code}")
                return None

        except Exception as e:
            self.log(f"Error joining: {e}")
            return None

    def make_choice(self, choice):
        """Submit a choice for the current round."""
        try:
            resp = self.http_session.post(
                f"{self.base_url}/choice",
                json={"choice": choice}
            )

            if resp.status_code == 200:
                self.log(f"Chose {choice} for round {self.current_round + 1}")
                return True
            else:
                self.log(f"Choice failed: {resp.status_code}")
                return None

        except Exception as e:
            self.log(f"Error making choice: {e}")
            return None

    def mark_ready(self):
        """Mark ready for next round."""
        try:
            resp = self.http_session.post(f"{self.base_url}/ready")
            if resp.status_code == 200:
                self.log(f"Ready for next round")
                return True
            return None
        except Exception as e:
            self.log(f"Error marking ready: {e}")
            return None

    def play_game(self):
        """Play through all rounds of the game."""
        try:
            # Wait for game to start
            time.sleep(2)

            # Play 20 rounds
            for round_num in range(1, 21):
                # Wait a bit, then make a choice
                time.sleep(random.uniform(1, 3))

                choice = random.choice(['A', 'B'])
                if not self.make_choice(choice):
                    self.log(f"Failed to make choice in round {round_num}")
                    break

                # Wait for round result (handled by Socket.IO handler)
                time.sleep(random.uniform(0.5, 1.5))

            self.log("Finished all rounds!")

        except Exception as e:
            self.log(f"Error during gameplay: {e}")

    def cleanup(self):
        """Disconnect and cleanup."""
        try:
            if self.sio.connected:
                self.sio.disconnect()
            self.http_session.close()
        except Exception as e:
            self.log(f"Error during cleanup: {e}")


def create_session_and_get_codes(session_num, base_url):
    """Create a session as admin and return participant codes."""
    print(f"\n{'='*60}")
    print(f"Creating Session {session_num}: Stresstest-{session_num}")
    print(f"{'='*60}")

    # Create a temporary admin session
    admin_session = requests.Session()

    try:
        # Login as admin
        resp = admin_session.post(
            f"{base_url}/admin/login",
            data={"password": "adminpw"}
        )

        if resp.status_code != 200:
            print(f"❌ Admin login failed: {resp.status_code}")
            return None

        # Create session
        resp = admin_session.post(
            f"{base_url}/admin/session/create",
            data={
                "name": f"Stresstest-{session_num}",
                "group_size": PLAYERS_PER_SESSION,
                "rounds": 20,
                "starting_balance": 500
            },
            allow_redirects=True
        )

        if resp.status_code != 200:
            print(f"❌ Session creation failed: {resp.status_code}")
            return None

        # Get the codes from the response
        # Find all participant codes in the HTML
        import re
        codes = re.findall(r'<code>([A-Z0-9]{6})</code>', resp.text)

        if len(codes) >= PLAYERS_PER_SESSION:
            print(f"✅ Session created with {len(codes)} participant codes")
            return codes[:PLAYERS_PER_SESSION]
        else:
            print(f"❌ Not enough codes generated: {len(codes)}")
            return None

    except Exception as e:
        print(f"❌ Error creating session: {e}")
        return None
    finally:
        admin_session.close()


def simulate_game_session(session_num, codes, base_url):
    """Simulate one complete game session with real players."""
    global completed_sessions

    players = []

    try:
        print(f"\n[Session {session_num}] Starting player joins...")

        # Create and join all players
        for i, code in enumerate(codes):
            player = SimulatedPlayer(
                player_id=f"S{session_num}P{i+1}",
                session_name=f"Stresstest-{session_num}",
                base_url=base_url
            )
            player.setup_socketio_handlers()
            players.append(player)

            # Join with slight delay
            time.sleep(random.uniform(0.2, 0.5))
            if not player.join_with_code(code):
                print(f"❌ [Session {session_num}] Player {i+1} failed to join")
                return

        print(f"✅ [Session {session_num}] All {PLAYERS_PER_SESSION} players joined!")

        # Wait for game to start
        time.sleep(2)

        # All players play the game
        threads = []
        for player in players:
            t = threading.Thread(target=player.play_game)
            t.start()
            threads.append(t)

        # Wait for all players to finish
        for t in threads:
            t.join()

        print(f"🎉 [Session {session_num}] Game completed!")

    except Exception as e:
        print(f"❌ [Session {session_num}] Error: {e}")

    finally:
        # Cleanup all players
        for player in players:
            player.cleanup()

        with progress_lock:
            completed_sessions += 1
            print(f"\n{'='*60}")
            print(f"Progress: {completed_sessions}/{total_sessions} sessions completed")
            print(f"{'='*60}\n")


def main():
    """Main stress test orchestrator."""
    print("="*60)
    print("VACCINATION GAME STRESS TEST")
    print("="*60)
    print(f"Server URL: {SERVER_URL}")
    print(f"Sessions to create: {SESSIONS_TO_CREATE}")
    print(f"Players per session: {PLAYERS_PER_SESSION}")
    print(f"Total players: {TOTAL_PLAYERS}")
    print("="*60)

    input("\n⚠️  Press ENTER to start the stress test...")

    start_time = time.time()

    # Create all sessions first and collect codes
    all_session_codes = []
    for session_num in range(1, SESSIONS_TO_CREATE + 1):
        codes = create_session_and_get_codes(session_num, SERVER_URL)
        if codes:
            all_session_codes.append((session_num, codes))
            time.sleep(0.5)  # Brief pause between session creations
        else:
            print(f"❌ Failed to create session {session_num}, stopping")
            return

    print(f"\n✅ All {SESSIONS_TO_CREATE} sessions created successfully!")
    print("\n" + "="*60)
    print("Starting gameplay simulation...")
    print("="*60 + "\n")

    time.sleep(2)

    # Now simulate all games in parallel
    session_threads = []
    for session_num, codes in all_session_codes:
        t = threading.Thread(
            target=simulate_game_session,
            args=(session_num, codes, SERVER_URL)
        )
        t.start()
        session_threads.append(t)
        time.sleep(0.5)  # Stagger the starts slightly

    # Wait for all sessions to complete
    for t in session_threads:
        t.join()

    elapsed = time.time() - start_time

    print("\n" + "="*60)
    print("STRESS TEST COMPLETED!")
    print("="*60)
    print(f"Total time: {elapsed:.1f} seconds")
    print(f"Sessions completed: {completed_sessions}/{SESSIONS_TO_CREATE}")
    print(f"Total players simulated: {TOTAL_PLAYERS}")
    print("="*60)


if __name__ == "__main__":
    main()
