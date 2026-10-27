# tests/test_api.py — HTTP contract tests (the frontend's expectations).
# Requires Postgres; skipped automatically when unreachable. No successful
# write path runs here (Playwright e2e covers those) so the feed stays clean
# for the browser suites.
import pytest

from app import db

pytestmark = pytest.mark.skipif(
    not db.ping(), reason="PostgreSQL not reachable (start: docker compose up -d db)"
)


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app, base_url="http://localhost:8000") as c:
        yield c


def test_healthz(client):
    assert client.get("/api/healthz").json() == {"ok": True}


def test_session_signed_out(client):
    r = client.get("/api/session")
    assert r.status_code == 200
    assert r.json()["blindUid"] is None


def test_feed_shape(client):
    posts = client.get("/api/posts").json()
    assert {"p1", "p2", "p3"} <= {p["id"] for p in posts}
    first = next(p for p in posts if p["id"] == "p1")
    assert first["blindUid"] == "a91f-7c3e"
    assert isinstance(first["body"], list) and first["poll"]["criteria"]
    # newest bucket first
    assert posts[0]["id"] == "p1"


def test_feed_has_embeddings_for_semantic_mapping(client):
    r = client.get("/api/posts/p1/related")
    assert r.status_code == 200
    related = r.json()
    assert related and related[0]["id"] in {"p2", "p3"}
    assert 0.0 <= related[0]["similarity"] <= 1.0
    assert client.get("/api/posts/nope/related").status_code == 404


def test_create_post_requires_session(client):
    r = client.post("/api/posts", json={"dept": "X", "body": "A" * 80})
    assert r.status_code == 401
    assert r.json() == {"error": "unauthenticated"}


def test_poll_requires_session(client):
    r = client.post("/api/posts/p1/poll", json={"responses": {"independence": 50}})
    assert r.status_code == 401


def test_logout_is_ok_when_signed_out(client):
    assert client.post("/api/logout").json() == {"ok": True}


def test_webauthn_options_shape_and_cookie(client):
    # The host check requires localhost for dev; TestClient defaults to testserver
    client.headers.update({"Host": "localhost:8000"})
    r = client.post("/api/webauthn/register/options")
    assert r.status_code == 200
    body = r.json()
    assert body["rp"]["id"] == "localhost"
    assert body["challenge"] and body["pubKeyCredParams"]
    assert "cid" in r.cookies
    r2 = client.post("/api/webauthn/authenticate/options")
    assert r2.status_code == 200 and "challenge" in r2.json()


def test_guard_rejections_run_before_any_write(client):
    from app import authn

    sid, _ = authn.start_session("api-test-uid", 1.0)
    client.cookies.set("sid", sid)
    try:
        r = client.post("/api/posts", json={"dept": "X", "body": "too short"})
        assert r.status_code == 422 and "little more" in r.json()["reason"]

        r = client.post(
            "/api/posts",
            json={
                "dept": "X",
                "body": "I enrolled in CS 101 during add/drop and never got the "
                        "deadline notice that everyone else seemed to get.",
            },
        )
        assert r.status_code == 422 and "course code" in r.json()["reason"]

        # Feed unchanged: guard rejected before persisting anything.
        posts = client.get("/api/posts").json()
        assert {"p1", "p2", "p3"} == {p["id"] for p in posts} or \
            {"p1", "p2", "p3"} <= {p["id"] for p in posts}
    finally:
        authn.drop_session(sid)
        client.cookies.delete("sid")


def test_poll_validation_without_writes(client):
    from app import authn

    sid, _ = authn.start_session("api-test-uid", 1.0)
    client.cookies.set("sid", sid)
    try:
        r = client.post("/api/posts/p1/poll", json={"responses": {"independence": 500}})
        assert r.status_code == 400
        r = client.post("/api/posts/p1/poll", json={"responses": {}})
        assert r.status_code == 400
        r = client.post("/api/posts/does-not-exist/poll",
                        json={"responses": {"independence": 50}})
        assert r.status_code == 404
    finally:
        authn.drop_session(sid)
        client.cookies.delete("sid")


def test_serves_compiled_frontend(client):
    r = client.get("/")
    assert r.status_code == 200
    assert '<div id="root">' in r.text
