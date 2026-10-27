# Veritas Wall

Anonymous institutional post-mortems with passkey (WebAuthn) sign-in and
credibility-weighted polls. Vite + React frontend with a small **local dev API**
(`dev-api.js`) so the whole app runs with one command. No database or
separate backend needed for local use.

Requires **Node 18+**.

## Run it

```bash
npm install
npm run dev          # development, http://localhost:5173
```

Or run the compiled build:

```bash
npm run build        # outputs ./dist
npm run preview      # serves ./dist (with the dev API) at http://localhost:4173
```

**Always open it at `http://localhost:<port>`**, not `127.0.0.1` or a LAN IP.
WebAuthn only works on `localhost` or https. If you use another hostname the
app tells you so.

You need a device that can create passkeys (Touch ID, Windows Hello, Android
biometrics, a security key, or a password-manager passkey). First time: click
**Verify passkey -> First time here? Create a passkey**. After that, sign in
with the same passkey.

> The `dist/` folder is static files only. It does **not** contain a backend:
> `npm run preview` works because the dev API plugin also attaches to Vite's
> preview server. To deploy `dist/` somewhere else you must provide the API
> endpoints listed below (e.g. your FastAPI service).

## What works

- Feed loaded from the API, sort tabs, keyboard access (Enter/Space)
- Hash routing: Back/Forward, refresh, and shareable links (`#/post/<id>`, `#/compose`)
- Passkey registration and sign-in, session restore on reload, sign-out
- Auth-gated actions queue until you verify, then complete automatically;
  cancelling shows an error instead of faking success
- Credibility-weighted polls (one response per Blind_UID, resubmitting updates it)
- Compose with a de-anonymization guard (course codes, named people, too short -> 422 + reason)
- Light/dark themes, responsive layout

## Layout

```
index.html, vite.config.js    app shell + Vite config
dev-api.js                    local API (Vite plugin; in-memory, resets on restart)
src/
  main.jsx  App.jsx  styles.css
  components/                 Feed, PostCard, PostDetail, PollBlock, Compose, PasskeyModal
  hooks/useWebAuthn.js        sign-in + registration flows
  lib/mockPosts.js            seed posts (also the offline fallback)
dist/                         compiled production build
tests/e2e.py                  browser test (Playwright + Chromium virtual authenticator)
```

## API contract (what `dev-api.js` implements; replace for production)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/webauthn/register/options` | `generate_registration_options()` as JSON |
| `POST` | `/api/webauthn/register/verify` | Verify attestation, derive `Blind_UID`, start session |
| `POST` | `/api/webauthn/authenticate/options` | `generate_authentication_options()` as JSON |
| `POST` | `/api/webauthn/authenticate/verify` | Verify assertion, derive `Blind_UID`, start session |
| `GET` | `/api/session` | `{ blindUid, dci }`, or `{ blindUid: null }` when signed out |
| `POST` | `/api/logout` | Clear the session cookie |
| `GET` | `/api/posts` | Feed (shaped like `lib/mockPosts.js`) |
| `POST` | `/api/posts` | Run the guard; `422 { reason }` on rejection; 401 if signed out |
| `POST` | `/api/posts/:id/poll` | Record `{ responses }`; returns `{ aggregate, voters }` |

`Blind_UID = HMAC-SHA256(public_key, System_Pepper)`. The httpOnly session
cookie carries auth; the client never sends its own Blind_UID.

## Known limits (dev API only)

- State is in memory: restart = all accounts, posts and votes reset, and the
  pepper regenerates (so Blind_UIDs change).
- The guard is a simple regex stand-in, not the real NLP guard.
- Every new passkey is a new identity (Blind_UID derives from the public key),
  so there is no account recovery or multi-device story yet.
- DCI is fixed at 1.0 for everyone; no real credibility scoring.
- Session cookie has no `Secure` flag (needed for plain http on localhost).
- `@simplewebauthn/*` is pinned to v10. v11+ changed several call signatures.

## Test

With the dev server running (`npm run dev`) and Playwright + Chromium installed:

```bash
pip install playwright && playwright install chromium
python tests/e2e.py
```
