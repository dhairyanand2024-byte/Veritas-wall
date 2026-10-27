# app/config.py — environment-driven configuration (no secrets hard-coded).
#
# System_Pepper custody: in production the pepper MUST come from a separate
# secrets domain (KMS/Vault with its own IAM role) so a database compromise
# alone cannot reverse blind_uid (DBMS note, Section 3). Locally, export
# VERITAS_PEPPER or accept an ephemeral per-process pepper.
import os
import secrets
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent      # .../veritas-wall-final/backend
PROJECT_DIR = BACKEND_DIR.parent                          # .../veritas-wall-final


def _load_pepper() -> bytes:
    raw = os.environ.get("VERITAS_PEPPER", "").strip()
    if not raw:
        return secrets.token_bytes(32)
    try:
        return bytes.fromhex(raw)
    except ValueError:
        return raw.encode()


_raw_pepper = os.environ.get("VERITAS_PEPPER", "").strip()
PEPPER = _load_pepper()
PEPPER_EPHEMERAL = not _raw_pepper  # True => warn at startup (dev-api parity)

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://veritas:veritas@localhost:5432/veritas"
)

RP_ID = os.environ.get("VERITAS_RP_ID", "localhost")
RP_NAME = os.environ.get("VERITAS_RP_NAME", "Veritas Wall")
VECTOR_DIM = int(os.environ.get("VERITAS_VECTOR_DIM", "128"))
SESSION_TTL_S = int(os.environ.get("VERITAS_SESSION_TTL", str(12 * 3600)))
CHALLENGE_TTL_S = int(os.environ.get("VERITAS_CHALLENGE_TTL", "300"))

# Compiled frontend served by this API (single-origin deployment).
DIST_DIR = Path(os.environ.get("VERITAS_DIST", str(PROJECT_DIR / "dist")))

# Vite dev servers allowed to call this API cross-origin (dev:api proxy mode
# is same-origin, so this list is only a convenience fallback).
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "VERITAS_ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:4173"
    ).split(",")
    if o.strip()
]
