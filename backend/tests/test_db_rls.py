# tests/test_db_rls.py — Row-Level Security guarantees (Stage 4).
# Requires the Postgres container; skipped automatically when unreachable.
import pytest
import psycopg

from app import db

pytestmark = pytest.mark.skipif(
    not db.ping(), reason="PostgreSQL not reachable (start: docker compose up -d db)"
)


class _Rollback(Exception):
    """Raised inside a transaction to inspect-and-undo without persisting."""


def test_public_read_sees_seed_posts():
    with db.tx() as conn:
        ids = {r["id"] for r in conn.execute("SELECT id FROM posts").fetchall()}
    assert {"p1", "p2", "p3"} <= ids


def test_insert_without_blind_uid_denied():
    with pytest.raises(psycopg.Error) as excinfo:
        with db.tx() as conn:  # no app.blind_uid bound
            conn.execute(
                """
                INSERT INTO posts (id, blind_uid, dept, title, excerpt, body,
                                   time_bucket, poll)
                VALUES ('rls-denied', 'attacker-uid', 'X', 't', 'e', '[]'::jsonb,
                        'now', '{}'::jsonb)
                """
            )
    assert "row-level security" in str(excinfo.value).lower() or \
        getattr(excinfo.value, "sqlstate", None) == "42501"


def test_insert_with_wrong_blind_uid_denied():
    with pytest.raises(psycopg.Error):
        with db.tx("some-other-pseudonym") as conn:
            conn.execute(
                """
                INSERT INTO posts (id, blind_uid, dept, title, excerpt, body,
                                   time_bucket, poll)
                VALUES ('rls-denied-2', 'attacker-uid', 'X', 't', 'e', '[]'::jsonb,
                        'now', '{}'::jsonb)
                """
            )


def test_insert_with_own_blind_uid_allowed():
    with pytest.raises(_Rollback):
        with db.tx("rls-self-test") as conn:
            conn.execute(
                """
                INSERT INTO posts (id, blind_uid, dept, title, excerpt, body,
                                   time_bucket, poll)
                VALUES ('rls-allowed', 'rls-self-test', 'X', 't', 'e', '[]'::jsonb,
                        'Just now', '{}'::jsonb)
                """
            )
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM posts WHERE id = 'rls-allowed'"
            ).fetchone()
            assert row["c"] == 1  # visible in the same transaction
            raise _Rollback  # never persist test rows


def test_app_role_cannot_update_or_delete_posts():
    with db.tx("rls-self-test") as conn:
        with pytest.raises(psycopg.Error):
            conn.execute("UPDATE posts SET title = 'x' WHERE id = 'p1'")
        with pytest.raises(psycopg.Error):
            conn.execute("DELETE FROM posts WHERE id = 'p1'")


def test_vote_upsert_confined_to_own_pseudonym():
    with pytest.raises(_Rollback):
        with db.tx("someone-else") as conn:
            with pytest.raises(psycopg.Error):
                conn.execute(
                    """
                    INSERT INTO poll_votes (post_id, blind_uid, responses, dci_weight)
                    VALUES ('p1', 'rls-self-test', '{"independence": 1}'::jsonb, 1.0)
                    """
                )
            raise _Rollback
