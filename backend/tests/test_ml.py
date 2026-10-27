# tests/test_ml.py — embedding + blind-identity unit tests (no database).
import math

from app.blind import derive_blind_uid
from app import config
from app.ml.embeddings import embed, to_pgvector


def test_embedding_shape_and_norm():
    vec = embed("A canonical policy page would have prevented this entire situation.")
    assert len(vec) == config.VECTOR_DIM
    assert all(math.isfinite(v) for v in vec)
    norm = math.sqrt(sum(v * v for v in vec))
    assert abs(norm - 1.0) < 1e-5  # HashingVectorizer produces unit vectors


def test_embedding_deterministic():
    assert embed("same text") == embed("same text")


def test_similarity_orders_related_text_higher():
    import numpy as np

    def cos(a, b):
        a, b = np.asarray(a), np.asarray(b)
        return float(a @ b)

    base = embed("authorship order was decided without documented criteria")
    related = embed("labs should pre-register authorship criteria before starting")
    unrelated = embed("campus shuttle routes changed during the winter closure")
    assert cos(base, related) > cos(base, unrelated)


def test_pgvector_format():
    s = to_pgvector([0.5, -0.25])
    assert s.startswith("[") and s.endswith("]")
    assert "0.5" in s and "-0.25" in s


def test_blind_uid_format_and_determinism():
    key = b"\x01" * 32
    uid = derive_blind_uid(key)
    assert len(uid) == 9 and uid[4] == "-"
    assert derive_blind_uid(key) == uid
    assert derive_blind_uid(b"\x02" * 32) != uid
    assert all(c in "0123456789abcdef-" for c in uid)
