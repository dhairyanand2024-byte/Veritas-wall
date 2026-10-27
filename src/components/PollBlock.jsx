// components/PollBlock.jsx
import { useState } from 'react';

export default function PollBlock({ poll, postId, onSubmit }) {
  const [values, setValues] = useState(
    Object.fromEntries(poll.criteria.map((c) => [c.key, c.value]))
  );
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [community, setCommunity] = useState(null); // { aggregate, voters } after submit

  const handleSubmit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      // POST /api/posts/:postId/poll  body: { responses: { [key]: 0-100 } }
      // The voter's Blind_UID is resolved server-side from the session cookie;
      // the client never sends it. onSubmit must return a promise that rejects
      // on auth cancellation or request failure.
      const result = await onSubmit({ postId, responses: values });
      if (result?.aggregate) setCommunity(result);
      setSubmitted(true);
    } catch (err) {
      setError(err?.message || 'Could not submit your response.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="poll-block">
      <p className="poll-eyebrow">Weighted consensus</p>
      <h4 className="poll-title">{poll.title}</h4>

      {poll.criteria.map((c) => (
        <div className="slider-row" key={c.key}>
          <div className="slider-label">
            <span>{c.label}</span>
            <span>{values[c.key]}</span>
          </div>
          <input
            type="range"
            min={0}
            max={100}
            value={values[c.key]}
            aria-label={c.label}
            disabled={submitted}
            onChange={(e) =>
              setValues((v) => ({ ...v, [c.key]: Number(e.target.value) }))
            }
          />
          {community && (
            <div className="poll-community">
              Credibility-weighted community view: <b>{community.aggregate[c.key]}</b>
              {community.voters ? ` (${community.voters} ${community.voters === 1 ? 'response' : 'responses'})` : ''}
            </div>
          )}
        </div>
      ))}

      {error && <div className="poll-error" role="alert">{error}</div>}

      <div className="poll-submit-row">
        <span className="poll-hint">
          {submitted
            ? 'Recorded under your Blind_UID — weighted by your Domain Credibility Index.'
            : 'Your response is weighted by Domain Credibility, not counted 1:1.'}
        </span>
        <button
          className={'btn small' + (submitted ? '' : ' primary')}
          onClick={handleSubmit}
          disabled={submitted || submitting}
        >
          {submitted ? 'Submitted' : submitting ? 'Submitting…' : 'Submit response'}
        </button>
      </div>
    </div>
  );
}
