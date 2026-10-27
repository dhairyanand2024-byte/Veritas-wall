// hooks/useWebAuthn.js
//
// Passkey flows via @simplewebauthn/browser (v10 API):
//   sign in : POST /api/webauthn/authenticate/options -> startAuthentication -> POST /authenticate/verify
//   register: POST /api/webauthn/register/options     -> startRegistration   -> POST /register/verify
//
// Both verify endpoints return { verified: true, blindUid, dci } and set the
// httpOnly session cookie. The server derives
//   Blind_UID = HMAC-SHA256(user_public_key, System_Pepper)
// so the browser never sees the pepper or the HMAC step.
//
// Neither flow rethrows: failures land in `error` / status === 'error' so
// callers (e.g. a button onClick) never produce unhandled rejections.

import { useState, useCallback } from 'react';
import { startAuthentication, startRegistration } from '@simplewebauthn/browser';

const FLOWS = {
  signin: {
    base: '/api/webauthn/authenticate',
    start: startAuthentication,
    optionsError: 'Could not reach the verification service.',
    verifyError: 'Signature verification failed.',
    unverified: 'Passkey could not be verified.',
    cancelled: 'Passkey verification was cancelled.',
  },
  register: {
    base: '/api/webauthn/register',
    start: startRegistration,
    optionsError: 'Could not reach the enrollment service.',
    verifyError: 'Passkey enrollment failed.',
    unverified: 'Passkey could not be registered.',
    cancelled: 'Passkey creation was cancelled.',
  },
};

// Prefer a human-readable { error } message from the server, else a fallback.
async function errorText(res, fallback) {
  try { const d = await res.json(); if (d?.error && d.error.length < 160) return d.error; } catch { /* not json */ }
  return fallback;
}

export function useWebAuthn() {
  const [status, setStatus] = useState('idle'); // idle | requesting-challenge | awaiting-device | verifying | done | error
  const [error, setError] = useState(null);
  const [session, setSession] = useState(null); // { blindUid, dci }

  const run = useCallback(async (mode) => {
    const flow = FLOWS[mode];
    setError(null);
    try {
      setStatus('requesting-challenge');
      const optionsRes = await fetch(`${flow.base}/options`, {
        method: 'POST',
        credentials: 'include',
      });
      if (!optionsRes.ok) throw new Error(await errorText(optionsRes, flow.optionsError));
      const options = await optionsRes.json();

      // Only the signed result leaves the device; the biometric never does.
      setStatus('awaiting-device');
      const credential = await flow.start(options);

      setStatus('verifying');
      const verifyRes = await fetch(`${flow.base}/verify`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ credential }),
      });
      if (!verifyRes.ok) throw new Error(await errorText(verifyRes, flow.verifyError));
      const result = await verifyRes.json();
      if (!result.verified) throw new Error(flow.unverified);

      const next = { blindUid: result.blindUid, dci: result.dci };
      setSession(next);
      setStatus('done');
      return next;
    } catch (err) {
      // NotAllowedError = user dismissed the biometric prompt.
      setError(
        err?.name === 'NotAllowedError'
          ? flow.cancelled
          : err?.message || 'Something went wrong with your passkey.'
      );
      setStatus('error');
      return null;
    }
  }, []);

  const authenticate = useCallback(() => run('signin'), [run]);
  const register = useCallback(() => run('register'), [run]);

  const reset = useCallback(() => {
    setStatus('idle');
    setError(null);
  }, []);

  return { status, error, session, authenticate, register, reset };
}
