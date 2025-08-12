from threading import Thread
from dotenv import load_dotenv
import time
import os


load_dotenv("quin.env")

class SessionHistoryManager:
    def __init__(self):
        self.sessions = {}  # In-memory storage: {token: {"entries": [...], "last_updated": timestamp}}
        self.cleanup_interval =300 # 300  # Run cleanup every 1 minutes
        self.expiry_time =float(os.getenv("JWT_TOKEN_EXPIRE_MINUTES")*60)  # seconds
        self._start_cleanup_thread()

    def _start_cleanup_thread(self):
        """Starts a background thread to clean up expired sessions."""
        def cleanup_worker():
            while True:
                time.sleep(self.cleanup_interval)
                self.cleanup_expired_sessions()

        Thread(target=cleanup_worker, daemon=True).start()

    def add_entry(self, token, entry):
        """
        Add an entry to the session history for the given JWT token.
        :param token: The JWT token (used as a session identifier)
        :param entry: The entry to add to the history
        """
        current_time = time.time()
        if token not in self.sessions:
            self.sessions[token] = {"entries": [], "last_updated": current_time}
        self.sessions[token]["entries"].append(entry)
        self.sessions[token]["last_updated"] = current_time

    def get_history(self, token):
        """
        Retrieve the session history for the given JWT token.
        :param token: The JWT token (used as a session identifier)
        :return: A list of session history entries
        """
        return self.sessions.get(token, {}).get("entries", [])

    def clear_history(self, token):
        """
        Clear the session history for the given JWT token.
        :param token: The JWT token (used as a session identifier)
        """
        if token in self.sessions:
            del self.sessions[token]

    def cleanup_expired_sessions(self):
        """
        Removes session histories that haven't been updated in the last 30 minutes.
        """
        current_time = time.time()
        expired_tokens = [
            token for token, data in self.sessions.items()
            if current_time - data["last_updated"] > self.expiry_time
        ]
        for token in expired_tokens:
            self.clear_history(token)


