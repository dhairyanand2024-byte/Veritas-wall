// components/Feed.jsx
import { useMemo, useState } from 'react';
import PostCard from './PostCard';

const TABS = [
  { key: 'recent', label: 'Recent' },
  { key: 'credible', label: 'By credibility' },
  { key: 'discussed', label: 'Most discussed' },
];

export default function Feed({ posts, onOpen }) {
  const [tab, setTab] = useState('recent');

  const sorted = useMemo(() => {
    const arr = [...posts];
    if (tab === 'credible') arr.sort((a, b) => b.dci - a.dci);
    if (tab === 'discussed') arr.sort((a, b) => b.lessons - a.lessons);
    return arr;
  }, [posts, tab]);

  return (
    <div>
      <nav className="tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={tab === t.key ? 'active' : ''}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </nav>
      {sorted.length === 0 && (
        <p className="feed-note">Nothing on the wall yet. Be the first to submit a post-mortem.</p>
      )}
      <div>
        {sorted.map((post) => (
          <PostCard key={post.id} post={post} onOpen={onOpen} />
        ))}
      </div>
    </div>
  );
}
