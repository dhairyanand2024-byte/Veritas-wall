-- Veritas Wall — PostgreSQL schema (Blueprint Stage 4: anonymity-preserving write path)
--
-- Design notes (see Veritas_Wall_DBMS_Recommendation.pdf):
--   * No table stores a raw identity column. blind_uid (a one-way HMAC derivation)
--     is the only join key for content, votes and credibility.
--   * The credential store holds public keys but NEVER a blind_uid column, so the
--     identity mapping only ever exists transiently inside the HMAC step in the
--     application layer.
--   * Row Level Security is enabled on every table that carries a blind_uid.
--     The app connects as role `veritas` (not the table owner), so RLS applies
--     to it; the API issues `SET LOCAL app.blind_uid = ...` per transaction.
--   * Timestamps are bucket-rounded (date_trunc('hour')) before they land, so no
--     exact write time is ever stored.
--
-- VECTOR_DIM must match VERITAS_VECTOR_DIM (default 128).

CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------------
-- Application role (non-owner => RLS enforced for it, no FORCE needed).
-- Password is a local-dev default; override with DATABASE_URL in production.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'veritas') THEN
    CREATE ROLE veritas LOGIN PASSWORD 'veritas';
  END IF;
END
$$;

-- ---------------------------------------------------------------------------
-- Auth store: public keys only, no blind_uid (decoupled from persistence).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS auth_credentials (
  credential_id      text PRIMARY KEY,
  public_key         bytea       NOT NULL,
  sign_count         integer     NOT NULL DEFAULT 0,
  created_bucket_ts  timestamptz NOT NULL DEFAULT date_trunc('hour', now())
);
GRANT SELECT, INSERT, UPDATE ON auth_credentials TO veritas;

-- ---------------------------------------------------------------------------
-- Domain Credibility profile, keyed by the pseudonym.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dci_profile (
  blind_uid          text PRIMARY KEY,
  dci                numeric     NOT NULL DEFAULT 1.0,
  verified_bucket_ts timestamptz NOT NULL DEFAULT date_trunc('hour', now())
);
ALTER TABLE dci_profile ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS dci_own_read    ON dci_profile;
DROP POLICY IF EXISTS dci_own_insert  ON dci_profile;
DROP POLICY IF EXISTS dci_own_update  ON dci_profile;
CREATE POLICY dci_own_read   ON dci_profile FOR SELECT
  USING (blind_uid = current_setting('app.blind_uid', true));
CREATE POLICY dci_own_insert ON dci_profile FOR INSERT
  WITH CHECK (blind_uid = current_setting('app.blind_uid', true));
CREATE POLICY dci_own_update ON dci_profile FOR UPDATE
  USING      (blind_uid = current_setting('app.blind_uid', true))
  WITH CHECK (blind_uid = current_setting('app.blind_uid', true));
GRANT SELECT, INSERT, UPDATE ON dci_profile TO veritas;

-- ---------------------------------------------------------------------------
-- Posts: the public wall. Anyone may read; a session may only insert rows
-- tagged with its own blind_uid. The app role gets NO UPDATE/DELETE grant on
-- posts, so published content is immutable from the API's credentials.
-- `lessons` shown in the UI = base count + distinct poll responses (computed
-- at read time, so no UPDATE is needed on this table).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS posts (
  id                text PRIMARY KEY,
  blind_uid         text        NOT NULL,
  dept              text        NOT NULL,
  dci               numeric     NOT NULL DEFAULT 1.0,
  title             text        NOT NULL,
  excerpt           text        NOT NULL,
  body              jsonb       NOT NULL,
  time_bucket       text        NOT NULL,
  lessons           integer     NOT NULL DEFAULT 0,
  poll              jsonb       NOT NULL,
  embedding         vector(128),
  created_bucket_ts timestamptz NOT NULL DEFAULT date_trunc('hour', now())
);
ALTER TABLE posts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS posts_public_read ON posts;
DROP POLICY IF EXISTS posts_insert_own   ON posts;
-- The wall is public by design (a "museum of institutional failure").
CREATE POLICY posts_public_read ON posts FOR SELECT USING (true);
CREATE POLICY posts_insert_own  ON posts FOR INSERT
  WITH CHECK (blind_uid = current_setting('app.blind_uid', true));
GRANT SELECT, INSERT ON posts TO veritas;

CREATE INDEX IF NOT EXISTS posts_embedding_idx
  ON posts USING hnsw (embedding vector_cosine_ops);

-- ---------------------------------------------------------------------------
-- Poll votes: jsonb slider responses + dci weight snapshot. One row per
-- (post, blind_uid); resubmitting updates the row instead of adding one.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS poll_votes (
  post_id           text        NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  blind_uid         text        NOT NULL,
  responses         jsonb       NOT NULL,
  dci_weight        numeric     NOT NULL DEFAULT 1.0,
  created_bucket_ts timestamptz NOT NULL DEFAULT date_trunc('hour', now()),
  PRIMARY KEY (post_id, blind_uid)
);
ALTER TABLE poll_votes ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS poll_votes_public_read ON poll_votes;
DROP POLICY IF EXISTS poll_votes_insert_own   ON poll_votes;
DROP POLICY IF EXISTS poll_votes_update_own   ON poll_votes;
-- Poll aggregates are computed server-side and are public like the wall itself.
CREATE POLICY poll_votes_public_read ON poll_votes FOR SELECT USING (true);
CREATE POLICY poll_votes_insert_own  ON poll_votes FOR INSERT
  WITH CHECK (blind_uid = current_setting('app.blind_uid', true));
CREATE POLICY poll_votes_update_own  ON poll_votes FOR UPDATE
  USING      (blind_uid = current_setting('app.blind_uid', true))
  WITH CHECK (blind_uid = current_setting('app.blind_uid', true));
GRANT SELECT, INSERT, UPDATE ON poll_votes TO veritas;
