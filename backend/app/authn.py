# app/authn.py — in-memory challenge/session stores + cookie helpers.
#
# Deliberately NOT persisted: the DBMS note forbids a cross-request table that
# could link sessions back to content (Minimal schema rule), and challenges are
# short-lived by nature. Restart => users re-verify their passkey, same as the
# local dev API.
import secrets
import time
import uuid

from . import config

_sessions: dict[str, dict] = {}
_challenges: dict[str, dict] = {}


def _purge() -> None:
    now = time.time()
    for store, ttl in ((_sessions, config.SESSION_TTL_S), (_challenges, config.CHALLENGE_TTL_S)):
        for key in [k for k, v in store.items() if v["exp"] < now]:
            store.pop(key, None)


def new_challenge(kind: str, challenge: bytes) -> str:
    _purge()
    cid = uuid.uuid4().hex
    _challenges[cid] = {
        "kind": kind,
        "challenge": challenge,
        "exp": time.time() + config.CHALLENGE_TTL_S,
    }
    return cid


def pop_challenge(cid: str | None, kind: str) -> bytes | None:
    if not cid:
        return None
    rec = _challenges.pop(cid, None)
    if rec is None or rec["kind"] != kind or rec["exp"] < time.time():
        return None
    return rec["challenge"]


def start_session(blind_uid: str, dci: float) -> tuple[str, dict]:
    _purge()
    sid = secrets.token_urlsafe(32)
    sess = {"blindUid": blind_uid, "dci": float(dci), "exp": time.time() + config.SESSION_TTL_S}
    _sessions[sid] = sess
    return sid, sess


def get_session(sid: str | None) -> dict | None:
    if not sid:
        return None
    rec = _sessions.get(sid)
    if rec is None:
        return None
    if rec["exp"] < time.time():
        _sessions.pop(sid, None)
        return None
    return rec


def drop_session(sid: str | None) -> None:
    if sid:
        _sessions.pop(sid, None)


def set_session_cookie(response, sid: str) -> None:
    response.set_cookie(
        "sid", sid, httponly=True, samesite="lax", path="/",
        max_age=config.SESSION_TTL_S,
    )


def set_challenge_cookie(response, cid: str) -> None:
    response.set_cookie(
        "cid", cid, httponly=True, samesite="lax", path="/",
        max_age=config.CHALLENGE_TTL_S,
    )
