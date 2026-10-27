# app/seed.py — first-boot seeding of the public wall.
#
# Runs as the app role (RLS applies), so each row is inserted with
# SET LOCAL app.blind_uid bound to that seed author's pseudonym — the same
# write path a real submission takes. Embeddings are computed in-process.
from __future__ import annotations

import logging

from .db import tx
from .ml import embeddings
from .seed_data import SEEDS
from psycopg.types.json import Jsonb

log = logging.getLogger("veritas.seed")


def seed_if_empty() -> int:
    """Insert seed posts when the wall is empty. Returns rows inserted."""
    with tx() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM posts").fetchone()["c"]
        if count:
            return 0
        inserted = 0
        for post in SEEDS:
            # Bind RLS context to the seed author's pseudonym for this insert.
            conn.execute(
                "SELECT set_config('app.blind_uid', %s, true)", (post["blindUid"],)
            )
            embedding = embeddings.to_pgvector(
                embeddings.embed(f"{post['title']} {' '.join(post['body'])}")
            )
            conn.execute(
                """
                INSERT INTO posts (id, blind_uid, dept, dci, title, excerpt, body,
                                   time_bucket, lessons, poll, embedding,
                                   created_bucket_ts)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb,
                        %s::vector,
                        date_trunc('hour', now() - make_interval(hours => %s)))
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    post["id"],
                    post["blindUid"],
                    post["dept"],
                    post["dci"],
                    post["title"],
                    post["excerpt"],
                    Jsonb(post["body"]),
                    post["timeBucket"],
                    post["lessons"],
                    Jsonb(post["poll"]),
                    embedding,
                    post["hoursAgo"],
                ),
            )
            inserted += 1
    if inserted:
        log.info("seeded %d posts", inserted)
    return inserted
