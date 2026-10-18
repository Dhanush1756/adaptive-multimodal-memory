"""Local account authentication. Session tokens are hashed at rest; never logged.

This is a localhost research profile, not an Internet-facing identity provider.
The registry is separate from each user's memory and transcript database.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from pathlib import Path
from uuid import uuid4


class AuthenticationError(ValueError):
    pass


class Accounts:
    def __init__(self, path, ttl=8 * 3600, clock=time.time):
        if ttl <= 0:
            raise ValueError("session lifetime must be positive")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.ttl, self.clock = ttl, clock
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS accounts (
          user_id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL,
          salt BLOB NOT NULL, password_hash BLOB NOT NULL, created_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS logins (
          login_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
          token_hash TEXT UNIQUE NOT NULL, logged_in_at REAL NOT NULL,
          expires_at REAL NOT NULL, logged_out_at REAL, end_reason TEXT);
        CREATE TABLE IF NOT EXISTS login_attempts (
          username TEXT PRIMARY KEY, failures INTEGER NOT NULL, locked_until REAL NOT NULL);
        """)

    @staticmethod
    def _username(username):
        name = username.strip().lower()
        if not re.fullmatch(r"[a-z0-9_]{3,40}", name):
            raise AuthenticationError("Use 3-40 letters, numbers or underscores.")
        return name

    @staticmethod
    def _hash(password, salt):
        return hashlib.scrypt(password.encode(), salt=salt, n=2**15, r=8, p=3,
                              dklen=32, maxmem=64 * 1024 * 1024)

    def register(self, username, password):
        name = self._username(username)
        if not 12 <= len(password) <= 1024:
            raise AuthenticationError("Use a password of 12-1024 characters.")
        salt, uid = secrets.token_bytes(32), uuid4().hex
        try:
            with self.db:
                self.db.execute("INSERT INTO accounts VALUES (?,?,?,?,?)",
                                (uid, name, salt, self._hash(password, salt), self.clock()))
        except sqlite3.IntegrityError:
            raise AuthenticationError("Registration could not be completed.") from None
        return uid

    def login(self, username, password):
        try:
            name = self._username(username)
        except AuthenticationError:
            name = "invalid"
        now = self.clock()
        row = self.db.execute("SELECT * FROM accounts WHERE username=?", (name,)).fetchone()
        attempt = self.db.execute("SELECT * FROM login_attempts WHERE username=?", (name,)).fetchone()
        if attempt and attempt["locked_until"] > now:
            raise AuthenticationError("Login failed. Try again later.")
        # Do comparable password work for unknown accounts and invalid input.
        supplied = self._hash(password if len(password) <= 1024 else "invalid", row["salt"] if row else b"0" * 32)
        if not row or not hmac.compare_digest(supplied, row["password_hash"]):
            failures = (attempt["failures"] if attempt else 0) + 1
            with self.db:
                self.db.execute("INSERT OR REPLACE INTO login_attempts VALUES (?,?,?)",
                                (name, failures, now + 300 if failures >= 5 else 0))
            raise AuthenticationError("Login failed. Try again later.")
        token = secrets.token_urlsafe(32)
        with self.db:
            self.db.execute("DELETE FROM login_attempts WHERE username=?", (name,))
            self.db.execute("INSERT INTO logins VALUES (?,?,?,?,?,?,?)",
                            (uuid4().hex, row["user_id"], self._token_hash(token), now, now + self.ttl, None, None))
        return token

    @staticmethod
    def _token_hash(token):
        return hashlib.sha256((token or "").encode()).hexdigest()

    def identity(self, token):
        row = self.db.execute("SELECT * FROM logins WHERE token_hash=?", (self._token_hash(token),)).fetchone()
        if not row or row["logged_out_at"] is not None:
            raise AuthenticationError("Please log in again.")
        if row["expires_at"] <= self.clock():
            with self.db:
                self.db.execute("UPDATE logins SET logged_out_at=?,end_reason='expired' WHERE login_id=?",
                                (row["expires_at"], row["login_id"]))
            raise AuthenticationError("Please log in again.")
        return row["user_id"]

    def logout(self, token):
        self.identity(token)
        with self.db:
            self.db.execute("UPDATE logins SET logged_out_at=?,end_reason='logout' WHERE token_hash=?",
                            (self.clock(), self._token_hash(token)))

    def history(self, token):
        uid = self.identity(token)
        # Never return password hashes, salts or session-token digests.
        return [dict(r) for r in self.db.execute(
            "SELECT logged_in_at,expires_at,logged_out_at,end_reason FROM logins WHERE user_id=? ORDER BY logged_in_at", (uid,))]

    def close(self):
        self.db.close()
