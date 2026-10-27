# app/db.py — thin psycopg 3 helper.
#
# Every write runs inside an explicit transaction with
#   SELECT set_config('app.blind_uid', <pseudonym>, true)
# so the RLS policies see the session's pseudonym for exactly that
# transaction (SET LOCAL semantics: the setting never survives the request,
# so no dump/backup can reveal which session wrote which row).
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from . import config


@contextmanager
def tx(blind_uid: str | None = None):
    """Open a transaction; optionally bind it to a blind_uid for RLS."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        with conn.transaction():
            if blind_uid is not None:
                conn.execute(
                    "SELECT set_config('app.blind_uid', %s, true)", (blind_uid,)
                )
            yield conn


def ping() -> bool:
    try:
        with tx() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


def wait_for_db(attempts: int = 30, delay: float = 1.0) -> bool:
    """Retry until Postgres is reachable (compose start-up race)."""
    import time

    for _ in range(attempts):
        if ping():
            return True
        time.sleep(delay)
    return False
