// components/PasskeyModal.jsx
import { useEffect, useRef, useState } from 'react';
import { useWebAuthn } from '../hooks/useWebAuthn';

const STATUS_COPY = {
  idle: '\u00A0',
  'requesting-challenge': 'Requesting a signed challenge from the server…',
  'awaiting-device': 'Waiting for your device…',
  verifying: 'Verifying signature and deriving Blind_UID…',
  done: 'Verified — session ready.',
  error: null, // rendered separately, in red
};

const COPY = {
  signin: {
    title: 'Verify institutional passkey',
    body: 'Your device will sign a one-time challenge. No password, email, or name is ever sent — only a public key, which the server maps to a one-way pseudonym before anything touches the database.',
    cta: 'Continue with Face ID / Touch ID',
    switch: 'First time here? Create a passkey',
  },
  register: {
    title: 'Create your passkey',
    body: 'Your device will generate a new key pair. Only the public key is sent; the server turns it into a one-way pseudonym (your Blind_UID). No name or email is collected.',
    cta: 'Create passkey',
    switch: 'Already have a passkey? Sign in',
  },
};

export default function PasskeyModal({ onVerified, onClose }) {
  const { status, error, session, authenticate, register, reset } = useWebAuthn();
  const [mode, setMode] = useState('signin');

  // Keep the latest callback in a ref so a parent re-render can't restart the timer.
  const onVerifiedRef = useRef(onVerified);
  useEffect(() => { onVerifiedRef.current = onVerified; }, [onVerified]);

  useEffect(() => {
    if (status === 'done' && session) {
      const t = setTimeout(() => onVerifiedRef.current(session), 500);
      return () => clearTimeout(t);
    }
  }, [status, session]);

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const busy = status === 'requesting-challenge' || status === 'awaiting-device' || status === 'verifying';
  const start = mode === 'register' ? register : authenticate;
  const copy = COPY[mode];

  return (
    <div
      className="modal-overlay"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="modal" role="dialog" aria-modal="true" aria-label={copy.title}>
        <div className="modal-icon">
          <PasskeyIcon />
        </div>
        <h3>{copy.title}</h3>
        <p>{copy.body}</p>

        {status !== 'error' && (
          <button
            className="btn primary"
            onClick={start}
            disabled={busy || status === 'done'}
            style={busy || status === 'done' ? { opacity: 0.6, cursor: 'default' } : undefined}
          >
            {status === 'done' ? 'Verified' : busy ? 'Waiting…' : copy.cta}
          </button>
        )}

        {status === 'error' && (
          <>
            <button className="btn primary" onClick={() => { reset(); start(); }}>
              Try again
            </button>
            <div className="modal-status" style={{ color: 'var(--redact)' }} role="alert">{error}</div>
          </>
        )}

        {status !== 'error' && (
          <div className="modal-status" aria-live="polite">{STATUS_COPY[status]}</div>
        )}

        <button
          className="link-btn"
          disabled={busy || status === 'done'}
          onClick={() => { reset(); setMode(mode === 'signin' ? 'register' : 'signin'); }}
        >
          {copy.switch}
        </button>
      </div>
    </div>
  );
}

function PasskeyIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
      <circle cx="9" cy="8" r="3.4" stroke="currentColor" strokeWidth="1.3" />
      <path d="M9 11.4V21M9 15H12.5M9 18H11.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      <path d="M14 6.5C15.5 5.2 17.8 5.4 19 7" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" />
    </svg>
  );
}
