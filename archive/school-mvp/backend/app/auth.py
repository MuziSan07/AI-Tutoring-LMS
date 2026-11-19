"""Password hashing and signed bearer tokens.

MVP stand-in for the OIDC / OAuth 2.0 provider described in the SOW: tokens are
HMAC-signed and short-lived, and every endpoint resolves the caller's role.
"""
import base64
import hashlib
import hmac
import os
import secrets
import time

import bcrypt
from fastapi import Header, HTTPException

from . import db

_SECRET_FILE = os.path.join(os.path.dirname(__file__), "..", ".secret_key")
TOKEN_TTL_SECONDS = 12 * 3600


def _secret() -> bytes:
    env = os.environ.get("TUTOR_SECRET")
    if env:
        return env.encode()
    if not os.path.exists(_SECRET_FILE):
        with open(_SECRET_FILE, "w") as f:
            f.write(secrets.token_hex(32))
    with open(_SECRET_FILE) as f:
        return f.read().strip().encode()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=10)).decode()


def check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def make_token(user_id: int) -> str:
    payload = f"{user_id}:{int(time.time()) + TOKEN_TTL_SECONDS}"
    sig = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}:{sig}".encode()).decode()


def read_token(token: str) -> int | None:
    try:
        user_id, expiry, sig = base64.urlsafe_b64decode(token.encode()).decode().split(":")
    except Exception:
        return None
    expected = hmac.new(_secret(), f"{user_id}:{expiry}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected) or int(expiry) < time.time():
        return None
    return int(user_id)


def current_user(authorization: str = Header(default="")) -> dict:
    token = authorization.removeprefix("Bearer ").strip()
    user_id = read_token(token) if token else None
    user = db.one("SELECT * FROM users WHERE id = ?", (user_id,)) if user_id else None
    if not user:
        raise HTTPException(401, "Not signed in")
    user.pop("password_hash", None)
    return user


def require_role(user: dict, *roles: str) -> None:
    if user["role"] not in roles:
        raise HTTPException(403, "Your role does not have access to this")


def can_view_student(user: dict, student_id: int) -> bool:
    """Role-based access to an individual student's learning record."""
    role = user["role"]
    if role == "student":
        return user["id"] == student_id
    if role == "parent":
        return bool(db.one("SELECT 1 FROM parent_links WHERE parent_id=? AND student_id=?", (user["id"], student_id)))
    if role == "teacher":
        return bool(db.one(
            "SELECT 1 FROM class_members cm JOIN classes c ON c.id = cm.class_id "
            "WHERE c.teacher_id=? AND cm.student_id=?", (user["id"], student_id)))
    if role == "school_admin":
        student = db.one("SELECT org_id FROM users WHERE id=?", (student_id,))
        return bool(student and student["org_id"] == user["org_id"])  # tenant isolation
    return role == "super_admin"


def ensure_can_view_student(user: dict, student_id: int) -> None:
    if not can_view_student(user, student_id):
        db.audit(user["id"], "access_denied", f"student:{student_id}")
        raise HTTPException(403, "You are not authorised to view this student's records")
    if user["id"] != student_id:
        db.audit(user["id"], "viewed_student_record", f"student:{student_id}")
