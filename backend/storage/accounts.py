"""Local accounts and revocable server-side sessions."""

import hashlib
import re
import secrets
import sqlite3
import time
from contextlib import closing

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

from backend.storage.predictions import DB_PATH


SESSION_COOKIE = "risk_session"
SESSION_MAX_AGE = 30 * 24 * 60 * 60
SESSION_IDLE_AGE = 7 * 24 * 60 * 60
LOGIN_WINDOW = 15 * 60
LOGIN_MAX_FAILURES = 5
PASSWORD_HASHER = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
_DUMMY_HASH = PASSWORD_HASHER.hash("a password that no account uses")
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class DuplicateEmailError(ValueError):
    pass


class InvalidCredentialsError(ValueError):
    pass


class RateLimitedError(ValueError):
    pass


def normalize_email(email):
    value = email.strip().lower()
    if len(value) > 254 or not _EMAIL.fullmatch(value):
        raise ValueError("请输入有效的邮箱地址。")
    return value


def validate_password(password):
    if not 12 <= len(password) <= 128:
        raise ValueError("密码须为 12 至 128 个字符。")


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            created_at INTEGER NOT NULL,
            last_seen_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS login_attempts (
            email TEXT NOT NULL,
            address TEXT NOT NULL,
            failures INTEGER NOT NULL,
            started_at INTEGER NOT NULL,
            PRIMARY KEY (email, address)
        )
    """)
    return connection


def create_user(email, password):
    email = normalize_email(email)
    validate_password(password)
    password_hash = PASSWORD_HASHER.hash(password)
    with closing(_connect()) as connection, connection:
        try:
            cursor = connection.execute(
                "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
                (email, password_hash, int(time.time())),
            )
        except sqlite3.IntegrityError as error:
            raise DuplicateEmailError("这个邮箱已注册。") from error
        return {"id": cursor.lastrowid, "email": email}


def authenticate(email, password, address):
    email = normalize_email(email)
    now = int(time.time())
    with closing(_connect()) as connection, connection:
        attempt = connection.execute(
            "SELECT failures, started_at FROM login_attempts WHERE email = ? AND address = ?",
            (email, address),
        ).fetchone()
        if attempt and attempt["started_at"] + LOGIN_WINDOW > now and attempt["failures"] >= LOGIN_MAX_FAILURES:
            raise RateLimitedError("尝试次数过多，请 15 分钟后再试。")
        row = connection.execute(
            "SELECT id, email, password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()
        try:
            PASSWORD_HASHER.verify(row["password_hash"] if row else _DUMMY_HASH, password)
            valid_password = True
        except VerificationError:
            valid_password = False
        if row is None or not valid_password:
            if not attempt or attempt["started_at"] + LOGIN_WINDOW <= now:
                connection.execute(
                    "INSERT OR REPLACE INTO login_attempts VALUES (?, ?, 1, ?)",
                    (email, address, now),
                )
            else:
                connection.execute(
                    "UPDATE login_attempts SET failures = failures + 1 WHERE email = ? AND address = ?",
                    (email, address),
                )
            connection.commit()
            raise InvalidCredentialsError("邮箱或密码错误。")
        connection.execute(
            "DELETE FROM login_attempts WHERE email = ? AND address = ?", (email, address)
        )
        if PASSWORD_HASHER.check_needs_rehash(row["password_hash"]):
            connection.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (PASSWORD_HASHER.hash(password), row["id"]),
            )
        return {"id": row["id"], "email": row["email"]}


def create_session(user_id):
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    with closing(_connect()) as connection, connection:
        connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
        connection.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
            (_token_hash(token), user_id, now, now, now + SESSION_MAX_AGE),
        )
    return token


def read_session(token):
    if not token or len(token) > 128:
        return None
    now = int(time.time())
    token_hash = _token_hash(token)
    with closing(_connect()) as connection, connection:
        row = connection.execute("""
            SELECT users.id, users.email, sessions.last_seen_at, sessions.expires_at
            FROM sessions JOIN users ON users.id = sessions.user_id
            WHERE sessions.token_hash = ?
        """, (token_hash,)).fetchone()
        if row is None:
            return None
        if row["expires_at"] <= now or row["last_seen_at"] + SESSION_IDLE_AGE <= now:
            connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
            return None
        if now - row["last_seen_at"] >= 60 * 60:
            connection.execute(
                "UPDATE sessions SET last_seen_at = ? WHERE token_hash = ?", (now, token_hash)
            )
        return {"id": row["id"], "email": row["email"]}


def revoke_session(token):
    if not token:
        return
    with closing(_connect()) as connection, connection:
        connection.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))


def _token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
