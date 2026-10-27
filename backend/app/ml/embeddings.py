# app/ml/embeddings.py — dense vectors for cleared posts (Stage 3 -> Stage 4).
#
# Default embedder: scikit-learn HashingVectorizer — stateless, deterministic,
# no fitting step, so every cleared post is embedded synchronously at insert
# time and stored in the same transactional store as the row itself (pgvector).
#
# Optional: set VERITAS_EMBEDDER=sentence-transformers to use
# all-MiniLM-L6-v2 (384 dims) and VERITAS_VECTOR_DIM=384 in both the
# environment and sql/001_init.sql. The rest of the pipeline is agnostic.
from __future__ import annotations

import os

import numpy as np

from .. import config

_embedder = None
_impl = "hashing"


def _build():
    global _embedder, _impl
    if _embedder is not None:
        return _embedder
    if os.environ.get("VERITAS_EMBEDDER", "").strip() == "sentence-transformers":
        try:
            from sentence_transformers import SentenceTransformer

            _embedder = SentenceTransformer("all-MiniLM-L6-v2")
            _impl = "sentence-transformers"
            return _embedder
        except Exception:
            pass  # fall through to the sklearn default
    from sklearn.feature_extraction.text import HashingVectorizer

    _embedder = HashingVectorizer(
        n_features=config.VECTOR_DIM,
        alternate_sign=False,
        norm="l2",
        ngram_range=(1, 2),
        stop_words="english",
        lowercase=True,
    )
    _impl = "hashing"
    return _embedder


def embedder_name() -> str:
    _build()
    return _impl


def embed(text: str) -> list[float]:
    """Return a unit-norm VECTOR_DIM vector for one document."""
    model = _build()
    if _impl == "sentence-transformers":
        vec = model.encode([text], normalize_embeddings=True)[0]
        return np.asarray(vec, dtype=float).tolist()
    vec = model.transform([text]).toarray()[0]
    return vec.astype(float).tolist()


def embed_documents(texts: list[str]) -> list[list[float]]:
    return [embed(t) for t in texts]


def to_pgvector(vec: list[float]) -> str:
    """Format for `%s::vector` binds (psycopg has no native vector adapter)."""
    return "[" + ",".join(f"{v:.7g}" for v in vec) + "]"
