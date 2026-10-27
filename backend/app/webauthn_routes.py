# app/webauthn_routes.py — Stage 1 (passwordless entry) + Stage 2 (blind mapping).
#
# POST /api/webauthn/register/options      -> generate_registration_options()
# POST /api/webauthn/register/verify       -> verify attestation, derive Blind_UID, set session
# POST /api/webauthn/authenticate/options  -> generate_authentication_options()
# POST /api/webauthn/authenticate/verify   -> verify assertion, derive Blind_UID, set session
# GET  /api/session                        -> { blindUid, dci } | { blindUid: null }
# POST /api/logout                         -> clear session cookie
#
# Only a public key ever leaves the device; Blind_UID = HMAC-SHA256(pubkey,
# System_Pepper) is computed server-side and never stored beside the credential.
import base64
import json
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import options_to_json
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorSelectionCriteria,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from . import authn, config
from .blind import derive_blind_uid
from .db import tx

router = APIRouter()

HOST_ERROR = (
    "Open the app at http://localhost:PORT — passkeys do not work on "
    "other hostnames or IPs."
)


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _origin(request: Request) -> str:
    return f"{request.url.scheme}://{request.url.netloc}"


def _host_ok(request: Request) -> bool:
    host = (request.url.netloc or "").split(":")[0]
    if config.RP_ID in ("localhost", "127.0.0.1"):
        return host in ("localhost", "127.0.0.1")
    return host == config.RP_ID or host.endswith("." + config.RP_ID)


def _bad(message: str, code: int = 400) -> JSONResponse:
    return JSONResponse(status_code=code, content={"verified": False, "error": message})


def _touch_profile(conn, blind_uid: str) -> float:
    """Upsert the pseudonym's credibility profile; returns its DCI (default 1.0)."""
    row = conn.execute(
        """
        INSERT INTO dci_profile (blind_uid, dci)
        VALUES (%s, 1.0)
        ON CONFLICT (blind_uid)
        DO UPDATE SET verified_bucket_ts = date_trunc('hour', now())
        RETURNING dci
        """,
        (blind_uid,),
    ).fetchone()
    return float(row["dci"])


@router.post("/api/webauthn/register/options")
async def register_options(request: Request):
    if not _host_ok(request):
        return _bad(HOST_ERROR)
    options = generate_registration_options(
        rp_id=config.RP_ID,
        rp_name=config.RP_NAME,
        user_name="anonymous",
        user_id=os.urandom(16),
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )
    cid = authn.new_challenge("register", options.challenge)
    resp = JSONResponse(content=json.loads(options_to_json(options)))
    authn.set_challenge_cookie(resp, cid)
    return resp


@router.post("/api/webauthn/register/verify")
async def register_verify(request: Request):
    if not _host_ok(request):
        return _bad(HOST_ERROR)
    challenge = authn.pop_challenge(request.cookies.get("cid"), "register")
    if challenge is None:
        return _bad("Challenge expired. Please try again.")
    body = await request.json()
    try:
        verified = verify_registration_response(
            credential=body.get("credential") or {},
            expected_challenge=challenge,
            expected_rp_id=config.RP_ID,
            expected_origin=_origin(request),
        )
    except Exception as exc:  # noqa: BLE001 - surface a readable reason only
        return _bad(f"Passkey could not be verified ({type(exc).__name__}).")

    public_key = bytes(verified.credential_public_key)
    blind_uid = derive_blind_uid(public_key)
    with tx(blind_uid) as conn:
        conn.execute(
            """
            INSERT INTO auth_credentials (credential_id, public_key, sign_count)
            VALUES (%s, %s, %s)
            ON CONFLICT (credential_id)
            DO UPDATE SET public_key = EXCLUDED.public_key,
                          sign_count  = EXCLUDED.sign_count
            """,
            (_b64url(bytes(verified.credential_id)), public_key, verified.sign_count),
        )
        dci = _touch_profile(conn, blind_uid)

    sid, _ = authn.start_session(blind_uid, dci)
    resp = JSONResponse(content={"verified": True, "blindUid": blind_uid, "dci": dci})
    authn.set_session_cookie(resp, sid)
    return resp


@router.post("/api/webauthn/authenticate/options")
async def authenticate_options(request: Request):
    if not _host_ok(request):
        return _bad(HOST_ERROR)
    options = generate_authentication_options(
        rp_id=config.RP_ID,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    cid = authn.new_challenge("authenticate", options.challenge)
    resp = JSONResponse(content=json.loads(options_to_json(options)))
    authn.set_challenge_cookie(resp, cid)
    return resp


@router.post("/api/webauthn/authenticate/verify")
async def authenticate_verify(request: Request):
    if not _host_ok(request):
        return _bad(HOST_ERROR)
    challenge = authn.pop_challenge(request.cookies.get("cid"), "authenticate")
    if challenge is None:
        return _bad("Challenge expired. Please try again.")
    body = await request.json()
    credential = body.get("credential") or {}
    cred_id = credential.get("id")

    with tx() as conn:
        row = conn.execute(
            "SELECT public_key, sign_count FROM auth_credentials WHERE credential_id = %s",
            (cred_id,),
        ).fetchone()
    if row is None:
        return _bad("This passkey is not registered. Create a passkey first.")

    public_key = bytes(row["public_key"])
    try:
        verified = verify_authentication_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=config.RP_ID,
            expected_origin=_origin(request),
            credential_public_key=public_key,
            credential_current_sign_count=row["sign_count"],
        )
    except Exception as exc:  # noqa: BLE001
        return _bad(f"Signature verification failed ({type(exc).__name__}).")

    # Recompute the pseudonym from the stored public key: the mapping is
    # deterministic, so no blind_uid ever needs to sit next to the credential.
    blind_uid = derive_blind_uid(public_key)
    with tx(blind_uid) as conn:
        conn.execute(
            "UPDATE auth_credentials SET sign_count = %s WHERE credential_id = %s",
            (verified.new_sign_count, cred_id),
        )
        dci = _touch_profile(conn, blind_uid)

    sid, _ = authn.start_session(blind_uid, dci)
    resp = JSONResponse(content={"verified": True, "blindUid": blind_uid, "dci": dci})
    authn.set_session_cookie(resp, sid)
    return resp


@router.get("/api/session")
async def session_info(request: Request):
    # 200 either way: no console noise when logged out (dev-api parity).
    sess = authn.get_session(request.cookies.get("sid"))
    if not sess:
        return {"blindUid": None, "dci": None}
    return {"blindUid": sess["blindUid"], "dci": sess["dci"]}


@router.post("/api/logout")
async def logout(request: Request):
    authn.drop_session(request.cookies.get("sid"))
    resp = JSONResponse(content={"ok": True})
    resp.delete_cookie("sid", path="/")
    return resp
