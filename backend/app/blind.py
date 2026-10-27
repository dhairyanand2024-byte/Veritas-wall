# app/blind.py — Blind_UID = HMAC-SHA256(user_public_key, System_Pepper).
#
# Deterministic and server-side only: the browser never sees the pepper or the
# HMAC step, and the mapping is recomputed from the stored public key at sign-in
# (no blind_uid is ever stored next to the credential).
import hashlib
import hmac

from . import config


def derive_blind_uid(public_key: bytes) -> str:
    digest = hmac.new(config.PEPPER, public_key, hashlib.sha256).hexdigest()
    return f"{digest[0:4]}-{digest[4:8]}"


def pepper_is_ephemeral() -> bool:
    return config.PEPPER_EPHEMERAL
