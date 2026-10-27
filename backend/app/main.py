# app/main.py — Veritas Wall FastAPI service (Phase 2 backend).
#
# One origin serves the API *and* the compiled frontend (dist/), so the React
# app runs unchanged: every fetch('/api/...') lands here. The exact same
# contract the frontend was built against (see README) is preserved, plus
# GET /api/posts/{id}/related for semantic lesson mapping.
#
#   uvicorn app.main:app --host 0.0.0.0 --port 8000
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config, db
from .ml import embeddings
from .ml.guard import ML_THRESHOLD
from .posts_routes import router as posts_router
from .seed import seed_if_empty
from .webauthn_routes import router as webauthn_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("veritas")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not db.wait_for_db(attempts=30, delay=1.0):
        raise RuntimeError(
            "PostgreSQL is unreachable. Start the database first "
            "(docker compose up db) or point DATABASE_URL at a running instance."
        )
    try:
        seed_if_empty()
    except Exception as exc:  # pragma: no cover - startup diagnostics
        raise RuntimeError(
            f"Seeding failed ({exc}). Was backend/sql/001_init.sql applied? "
            "For a fresh stack: docker compose down -v && docker compose up --build."
        ) from exc

    if config.PEPPER_EPHEMERAL:
        log.warning(
            "VERITAS_PEPPER is not set — using an ephemeral pepper; all "
            "Blind_UIDs change on restart. Set it (see .env.example) for stable pseudonyms."
        )
    else:
        log.info("System_Pepper loaded from environment (never stored in the database).")
    log.info("embedder: %s (dim=%d)", embeddings.embedder_name(), config.VECTOR_DIM)
    log.info("rp_id=%s rp_name=%r", config.RP_ID, config.RP_NAME)
    if config.DIST_DIR.is_dir():
        log.info("serving compiled frontend from %s", config.DIST_DIR)
    else:
        log.warning(
            "dist/ not found at %s — API only. Run `npm run build` to serve the UI.",
            config.DIST_DIR,
        )
    yield


app = FastAPI(title="Veritas Wall API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# API routes first; the static mount is registered last so /api/* always wins.
app.include_router(webauthn_router)
app.include_router(posts_router)


@app.get("/api/healthz")
async def healthz():
    return {"ok": db.ping()}


if config.DIST_DIR.is_dir():
    app.mount("/", StaticFiles(directory=config.DIST_DIR, html=True), name="static")
