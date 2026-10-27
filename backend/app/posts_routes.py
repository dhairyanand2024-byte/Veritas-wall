# app/posts_routes.py — Stage 3 (submission + guard), Stage 5 (weighted polling,
# semantic lesson mapping) and the public feed read path.
#
# GET  /api/posts                 -> feed (shaped like src/lib/mockPosts.js)
# POST /api/posts                 -> guard first: 422 { reason } / 401 when signed out
# POST /api/posts/{id}/poll       -> one response per Blind_UID, DCI-weighted
# GET  /api/posts/{id}/related    -> pgvector nearest neighbours (semantic mapping)
from __future__ import annotations

import math
import re
import secrets
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from psycopg.types.json import Jsonb

from . import authn
from .db import tx
from .ml import embeddings, semantic
from .ml.guard import sanitize

router = APIRouter()

# Poll attached to user-submitted posts (parity with the local dev API).
USER_POLL = {
    "title": "Does this point to a structural problem?",
    "criteria": [
        {"key": "impact", "label": "Impact on students", "value": 50},
        {"key": "urgency", "label": "Urgency of a fix", "value": 50},
    ],
}

LIST_SQL = """
    SELECT p.*, COALESCE(v.cnt, 0)::int AS vote_cnt
      FROM posts p
      LEFT JOIN (SELECT post_id, COUNT(*)::int AS cnt
                   FROM poll_votes GROUP BY post_id) v ON v.post_id = p.id
     ORDER BY p.created_bucket_ts DESC, p.id DESC
"""


def _unauth() -> JSONResponse:
    return JSONResponse(status_code=401, content={"error": "unauthenticated"})


def _session(request: Request) -> dict | None:
    return authn.get_session(request.cookies.get("sid"))


def _row_to_post(row) -> dict:
    return {
        "id": row["id"],
        "dept": row["dept"],
        "dci": float(row["dci"]),
        "blindUid": row["blind_uid"],
        "title": row["title"],
        "excerpt": row["excerpt"],
        "body": row["body"],
        "timeBucket": row["time_bucket"],
        "lessons": int(row["lessons"]) + int(row["vote_cnt"]),
        "poll": row["poll"],
    }


def _derive_title_and_body(text: str) -> tuple[str, str, list[str]]:
    """Title = first sentence; don't repeat it at the top of the body."""
    paras = [p for p in re.split(r"\n+", text) if p.strip()]
    first = paras[0]
    match = re.match(r"^.{10,120}?[.!?](\s|$)", first)
    raw = match.group(0) if match else first[:90]
    title = raw.strip()
    rest = first[len(raw):].strip()
    body = ([rest] if rest else []) + paras[1:]
    return title, text[:180] + ("…" if len(text) > 180 else ""), body or paras


def _js_round(value: float) -> int:
    """Match JavaScript Math.round (half away from zero, not banker's)."""
    return int(math.floor(value + 0.5))


def _aggregate(criteria: list[dict], votes: list) -> dict:
    """DCI-weighted average per criterion (not a 1:1 count)."""
    weight_sum = sum(float(v["dci_weight"]) for v in votes)
    out = {}
    for c in criteria:
        if weight_sum:
            total = sum(
                float(v["responses"].get(c["key"], 0)) * float(v["dci_weight"])
                for v in votes
            )
            out[c["key"]] = _js_round(total / weight_sum)
        else:
            out[c["key"]] = c["value"]
    return out


@router.get("/api/posts")
async def list_posts():
    with tx() as conn:
        rows = conn.execute(LIST_SQL).fetchall()
    return [_row_to_post(r) for r in rows]


@router.post("/api/posts")
async def create_post(request: Request):
    sess = _session(request)
    if not sess:
        return _unauth()

    data = await request.json()
    text = str(data.get("body") or "").strip()
    reason = sanitize(text)  # de-anonymization guard runs BEFORE any write
    if reason:
        return JSONResponse(status_code=422, content={"reason": reason})

    dept = str(data.get("dept") or "General").strip()[:80] or "General"
    title, excerpt, body = _derive_title_and_body(text)
    embedding = embeddings.to_pgvector(embeddings.embed(f"{title} {text}"))
    post_id = f"u{int(time.time() * 1000)}{secrets.randbelow(100):02d}"

    with tx(sess["blindUid"]) as conn:
        conn.execute(
            """
            INSERT INTO posts (id, blind_uid, dept, dci, title, excerpt, body,
                               time_bucket, lessons, poll, embedding,
                               created_bucket_ts)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, 'Just now', 0, %s::jsonb,
                    %s::vector, date_trunc('hour', now()))
            """,
            (
                post_id,
                sess["blindUid"],
                dept,
                sess["dci"],
                title,
                excerpt,
                Jsonb(body),
                Jsonb(USER_POLL),
                embedding,
            ),
        )

    return {
        "id": post_id,
        "dept": dept,
        "dci": float(sess["dci"]),
        "blindUid": sess["blindUid"],
        "title": title,
        "excerpt": excerpt,
        "body": body,
        "timeBucket": "Just now",
        "lessons": 0,
        "poll": USER_POLL,
    }


@router.post("/api/posts/{post_id}/poll")
async def submit_poll(post_id: str, request: Request):
    sess = _session(request)
    if not sess:
        return _unauth()

    data = await request.json()
    responses = data.get("responses") or {}
    with tx(sess["blindUid"]) as conn:
        post = conn.execute(
            "SELECT id, poll FROM posts WHERE id = %s", (post_id,)
        ).fetchone()
        if post is None:
            return JSONResponse(status_code=404, content={"error": "not found"})

        criteria = post["poll"]["criteria"]
        for c in criteria:
            value = responses.get(c["key"])
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
                or value > 100
            ):
                return JSONResponse(status_code=400, content={"error": "invalid responses"})

        # One row per (post, Blind_UID): resubmitting updates it, never adds.
        conn.execute(
            """
            INSERT INTO poll_votes (post_id, blind_uid, responses, dci_weight)
            VALUES (%s, %s, %s::jsonb, %s)
            ON CONFLICT (post_id, blind_uid)
            DO UPDATE SET responses  = EXCLUDED.responses,
                          dci_weight = EXCLUDED.dci_weight
            """,
            (post_id, sess["blindUid"], Jsonb(dict(responses)), sess["dci"]),
        )
        votes = conn.execute(
            "SELECT responses, dci_weight FROM poll_votes WHERE post_id = %s",
            (post_id,),
        ).fetchall()

    return {
        "ok": True,
        "aggregate": _aggregate(criteria, votes),
        "voters": len(votes),
    }


@router.get("/api/posts/{post_id}/related")
async def related_posts(post_id: str, limit: int = 3):
    limit = max(1, min(limit, 10))
    with tx() as conn:
        row = conn.execute(
            "SELECT id, embedding FROM posts WHERE id = %s", (post_id,)
        ).fetchone()
        if row is None:
            return JSONResponse(status_code=404, content={"error": "not found"})
        if row["embedding"] is None:
            return []
        return semantic.related_posts(conn, post_id, limit)
