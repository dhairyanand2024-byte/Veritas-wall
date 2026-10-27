// components/PostDetail.jsx
import PollBlock from './PollBlock';

export default function PostDetail({ post, onBack, onSubmitPoll }) {
  return (
    <div>
      <button className="detail-back" onClick={onBack}>
        ← Back to wall
      </button>

      <div className="post-meta" style={{ marginTop: 18 }}>
        <span className="dept-pill">{post.dept}</span>
        <span className="dci">
          <span className="dci-dot" /> DCI {post.dci}
        </span>
        <span>{post.timeBucket}</span>
      </div>

      <h1 className="detail-title">{post.title}</h1>

      <div className="guard-note">
        <GuardIcon />
        <div>
          <b>De-anonymization guard: </b>
          no names, course codes, or targeted references detected. Cleared for publication.
        </div>
      </div>

      <div className="detail-body">
        {post.body.map((paragraph, i) => (
          <p key={i}>{paragraph}</p>
        ))}
      </div>

      <PollBlock
        poll={post.poll}
        postId={post.id}
        onSubmit={onSubmitPoll}
      />

      <div className="post-foot" style={{ borderTop: '1px solid var(--line)', paddingTop: 16 }}>
        <span className="blind-uid">Posted by Blind_UID {post.blindUid}</span>
        <span>{post.lessons} found this useful</span>
      </div>
    </div>
  );
}

function GuardIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path
        d="M8 1.5 13.5 3.5V7.5C13.5 11 11.2 13.6 8 14.5C4.8 13.6 2.5 11 2.5 7.5V3.5L8 1.5Z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
      />
      <path
        d="M5.5 8L7.2 9.7L10.5 6.2"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
