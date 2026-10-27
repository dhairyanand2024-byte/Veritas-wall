// App.jsx
import { useState, useCallback, useRef, useEffect } from 'react';
import Feed from './components/Feed';
import PostDetail from './components/PostDetail';
import Compose from './components/Compose';
import PasskeyModal from './components/PasskeyModal';
import { POSTS as MOCK_POSTS } from './lib/mockPosts';

// Hash routing keeps Back/Forward, refresh and shareable post links working.
function parseHash() {
  const h = window.location.hash;
  if (h.startsWith('#/post/')) return { view: 'detail', id: decodeURIComponent(h.slice(7)) };
  if (h === '#/compose') return { view: 'compose', id: null };
  return { view: 'feed', id: null };
}
const go = (hash) => { window.location.hash = hash; };

function authCancelled() {
  const e = new Error('Passkey verification was cancelled.');
  e.code = 'AUTH_CANCELLED';
  return e;
}

export default function App() {
  const [posts, setPosts] = useState([]);
  const [feedState, setFeedState] = useState('loading'); // loading | ready | offline
  const [session, setSession] = useState(null); // { blindUid, dci } | null
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [sessionReady, setSessionReady] = useState(false);
  const [route, setRoute] = useState(parseHash); // { view: 'feed'|'detail'|'compose', id }
  const { view, id: activeId } = route;

  // The action waiting on authentication, with the promise handles of its caller.
  const pendingRef = useRef(null); // { action, resolve, reject } | null

  // Load the feed. If the API is unreachable, fall back to sample data and say so.
  const loadPosts = useCallback(async () => {
    setFeedState('loading');
    try {
      const r = await fetch('/api/posts', { credentials: 'include' });
      if (!r.ok) throw new Error('bad status');
      setPosts(await r.json());
      setFeedState('ready');
    } catch {
      setPosts(MOCK_POSTS);
      setFeedState('offline');
    }
  }, []);

  // On first load: restore the session from the httpOnly cookie, and fetch the feed.
  useEffect(() => {
    loadPosts();
    fetch('/api/session', { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : null))
      .then((s) => { if (s?.blindUid) setSession({ blindUid: s.blindUid, dci: s.dci }); })
      .catch(() => {})
      .finally(() => setSessionReady(true));
  }, [loadPosts]);

  useEffect(() => {
    const onHash = () => { setRoute(parseHash()); window.scrollTo(0, 0); };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  // Compose needs a session: bounce to the feed once we know there isn't one.
  useEffect(() => {
    if (sessionReady && !session && route.view === 'compose') go('#/');
  }, [sessionReady, session, route.view]);

  const signOut = async () => {
    try { await fetch('/api/logout', { method: 'POST', credentials: 'include' }); } catch { /* cookie may linger; server-side expiry applies */ }
    setSession(null);
    if (route.view === 'compose') go('#/');
  };

  const activePost = posts.find((p) => p.id === activeId) || null;

  // Runs `action` once the user is authenticated and returns a promise for its
  // result. Rejects if the user dismisses the modal or the action throws, so
  // callers can show real success/failure state.
  const requireAuth = useCallback(
    (action) => {
      if (session) return Promise.resolve().then(action);
      return new Promise((resolve, reject) => {
        pendingRef.current?.reject(authCancelled()); // supersede any older request
        pendingRef.current = { action, resolve, reject };
        setShowAuthModal(true);
      });
    },
    [session]
  );

  // For fire-and-forget UI actions where a cancel is not an error.
  const runGated = (action) =>
    requireAuth(action).catch((e) => {
      if (e?.code !== 'AUTH_CANCELLED') console.error(e);
    });

  const handleVerified = useCallback(async (newSession) => {
    setSession(newSession);
    setShowAuthModal(false);
    const pending = pendingRef.current;
    pendingRef.current = null;
    if (pending) {
      try {
        pending.resolve(await pending.action());
      } catch (e) {
        pending.reject(e);
      }
    }
  }, []);

  const handleCloseModal = useCallback(() => {
    setShowAuthModal(false);
    pendingRef.current?.reject(authCancelled());
    pendingRef.current = null;
  }, []);

  // Shared fetch wrapper: a 401 means the cookie expired, so drop the session.
  const api = async (path, body) => {
    const res = await fetch(path, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (res.status === 401) {
      setSession(null);
      throw new Error('Your session expired. Please verify your passkey again.');
    }
    return res;
  };

  const submitPoll = async ({ postId, responses }) => {
    const res = await api(`/api/posts/${postId}/poll`, { responses });
    if (!res.ok) throw new Error('Poll submission failed. Please try again.');
    const result = await res.json();
    // Silently refresh counts (e.g. "found this useful") without flashing a loading state.
    fetch('/api/posts', { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : null))
      .then((fresh) => { if (fresh) setPosts(fresh); })
      .catch(() => {});
    return result;
  };

  const submitPost = async ({ dept, body }) => {
    const res = await api('/api/posts', { dept, body });
    if (res.status === 422) {
      const data = await res.json();
      return { rejected: true, reason: data.reason };
    }
    if (!res.ok) throw new Error('Submission failed. Your draft was not saved — please try again.');
    const newPost = await res.json();
    setPosts((prev) => [newPost, ...prev]);
    go('#/');
    return { rejected: false };
  };

  return (
    <div className="wrap">
      <header className="site">
        <div className="site-top">
          <div>
            <div className="wordmark">Veritas Wall</div>
            <div className="tagline">A museum of institutional failure, held anonymously</div>
          </div>
          {session ? (
            <div className="auth-state">
              <div>
                Blind_UID <span className="blind-uid">{session.blindUid}</span>
              </div>
              <div style={{ display: 'flex', gap: 8, marginTop: 8, justifyContent: 'flex-end' }}>
                <button className="btn small" onClick={() => runGated(() => go('#/compose'))}>
                  Submit a post-mortem
                </button>
                <button className="btn small" onClick={signOut}>Sign out</button>
              </div>
            </div>
          ) : (
            <button className="btn" onClick={() => setShowAuthModal(true)}>
              Verify passkey
            </button>
          )}
        </div>
      </header>

      {view === 'feed' && feedState === 'loading' && (
        <p className="feed-note" role="status">Loading the wall…</p>
      )}
      {view === 'feed' && feedState === 'offline' && (
        <div className="feed-note" role="status">
          Couldn't reach the server — showing sample posts. <button className="link-btn" style={{ margin: 0 }} onClick={loadPosts}>Retry</button>
        </div>
      )}
      {view === 'feed' && feedState !== 'loading' && (
        <Feed posts={posts} onOpen={(id) => go(`#/post/${encodeURIComponent(id)}`)} />
      )}

      {view === 'detail' && !activePost && feedState !== 'loading' && (
        <div className="feed-note">
          That post could not be found. <button className="link-btn" style={{ margin: 0 }} onClick={() => go('#/')}>Back to the wall</button>
        </div>
      )}

      {view === 'detail' && activePost && (
        <PostDetail
          key={activePost.id}
          post={activePost}
          onBack={() => go('#/')}
          // Returns the promise so PollBlock only shows "Submitted" on real success.
          onSubmitPoll={(payload) => requireAuth(() => submitPoll(payload))}
        />
      )}

      {view === 'compose' && session && (
        <Compose
          onCancel={() => go('#/')}
          // Re-checks auth at submit time in case the session expired.
          onSubmit={(payload) => requireAuth(() => submitPost(payload))}
        />
      )}

      {showAuthModal && (
        <PasskeyModal onVerified={handleVerified} onClose={handleCloseModal} />
      )}
    </div>
  );
}
