"""Password hashing and login sessions.

Passwords are hashed with PBKDF2-SHA256 (200,000 rounds, random salt) from Python's
standard library, so nothing extra needs to install. Session tokens are random and
only their SHA-256 hash is saved in the database.
"""
import hashlib
import hmac
import os
import secrets

from fastapi import Depends, Header, HTTPException

from db import get_db

ROUNDS = 200_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ROUNDS)
    return f"pbkdf2${ROUNDS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, rounds, salt, digest = stored.split("$")
    except ValueError:
        return False
    calc = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
    return hmac.compare_digest(calc.hex(), digest)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db, user_id: int) -> str:
    token = secrets.token_hex(32)
    db.run("INSERT INTO sessions (token_hash, user_id) VALUES (%s, %s)", (_hash_token(token), user_id))
    return token


def end_session(db, token: str):
    db.run("DELETE FROM sessions WHERE token_hash=%s", (_hash_token(token),))


def current_user(authorization: str = Header(None), db=Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Please sign in first.")
    token = authorization[7:]
    user = db.one(
        "SELECT u.id, u.name, u.email, u.role, u.hotel_id FROM sessions s "
        "JOIN users u ON u.id = s.user_id WHERE s.token_hash=%s",
        (_hash_token(token),),
    )
    if not user:
        raise HTTPException(401, "Your session has ended. Please sign in again.")
    user["token"] = token
    return user


def require(role: str):
    """Dependency that only lets one role through, e.g. Depends(require('admin'))."""

    def check(user=Depends(current_user)):
        if user["role"] != role:
            raise HTTPException(403, "You do not have access to this portal.")
        return user

    return check
