// components/Compose.jsx
import { useState } from 'react';

const DEPARTMENTS = [
  'Computer Science',
  'Undergraduate Admin',
  'Graduate Research',
  'Humanities',
  'Career Services',
];

export default function Compose({ onCancel, onSubmit }) {
  const [dept, setDept] = useState(DEPARTMENTS[0]);
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [guardError, setGuardError] = useState(null);
  const [submitError, setSubmitError] = useState(null);

  const handleSubmit = async () => {
    setSubmitting(true);
    setGuardError(null);
    setSubmitError(null);
    try {
      // Expected backend contract:
      // POST /api/posts
      //   body: { dept, body: text }
      //   The server runs the de-anonymization NLP guard synchronously
      //   before persisting. On rejection it should return
      //   422 { reason: "Post may contain identifying details: ..." }
      //   so the compose form can show *why*, without ever storing the draft.
      const result = await onSubmit({ dept, body: text });
      if (result?.rejected) {
        setGuardError(result.reason || 'This submission was flagged by the de-anonymization guard.');
        return;
      }
    } catch (err) {
      // Auth cancelled, expired session, or network/server failure.
      setSubmitError(err?.message || 'Submission failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <button className="detail-back" onClick={onCancel}>
        ← Back to wall
      </button>
      <h2 className="detail-title" style={{ fontSize: 24 }}>
        Submit a post-mortem
      </h2>
      <p style={{ color: 'var(--ink-soft)', fontSize: 13.5, lineHeight: 1.6, marginBottom: 26, maxWidth: '60ch' }}>
        Write from your Blind_UID. Names, course codes, and other identifying details will be
        flagged by the de-anonymization guard before this reaches the wall.
      </p>

      <div className="compose-field">
        <label htmlFor="dept">Department or area</label>
        <select id="dept" value={dept} onChange={(e) => setDept(e.target.value)}>
          {DEPARTMENTS.map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
      </div>

      <div className="compose-field">
        <label htmlFor="body">What happened, and what should change</label>
        <textarea
          id="body"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Describe the structural failure — not just what happened to you, but what would have prevented it."
        />
      </div>

      {guardError && (
        <div className="guard-note" style={{ background: 'var(--redact-soft)', color: 'var(--redact)', marginBottom: 18 }}>
          <span>{guardError}</span>
        </div>
      )}

      {submitError && (
        <div className="guard-note" style={{ background: 'var(--redact-soft)', color: 'var(--redact)', marginBottom: 18 }} role="alert">
          <span>{submitError}</span>
        </div>
      )}

      <div style={{ display: 'flex', gap: 10 }}>
        <button className="btn primary" onClick={handleSubmit} disabled={submitting || !text.trim()}>
          {submitting ? 'Running guard…' : 'Run guard & publish'}
        </button>
        <button className="btn" onClick={onCancel}>Discard</button>
      </div>
    </div>
  );
}
