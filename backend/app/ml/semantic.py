# app/ml/semantic.py — semantic lesson mapping over pgvector (Stage 5).
#
# Nearest-neighbour search happens entirely inside Postgres (cosine distance),
# so embeddings never leave the transactional store. Served by
# GET /api/posts/{id}/related.
from __future__ import annotations

import psycopg

RELATED_SQL = """
    SELECT p2.id, p2.title, p2.excerpt,
           1 - (p2.embedding <=> p1.embedding) AS similarity
      FROM posts p1
      JOIN posts p2 ON p2.id <> p1.id AND p2.embedding IS NOT NULL
     WHERE p1.id = %s
     ORDER BY p2.embedding <=> p1.embedding
     LIMIT %s
"""


def related_posts(conn: psycopg.Connection, post_id: str, limit: int = 3) -> list[dict]:
    rows = conn.execute(RELATED_SQL, (post_id, limit)).fetchall()
    return [
        {
            "id": r["id"],
            "title": r["title"],
            "excerpt": r["excerpt"],
            "similarity": round(float(r["similarity"]), 4),
        }
        for r in rows
    ]
