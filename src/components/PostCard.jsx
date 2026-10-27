// components/PostCard.jsx
export default function PostCard({ post, onOpen }) {
  return (
    <article
      className="post"
      role="button"
      tabIndex={0}
      onClick={() => onOpen(post.id)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault(); // stop Space from scrolling the page
          onOpen(post.id);
        }
      }}
    >
      <div className="post-meta">
        <span className="dept-pill">{post.dept}</span>
        <span className="dci">
          <span className="dci-dot" /> DCI {post.dci}
        </span>
        <span>{post.timeBucket}</span>
      </div>
      <h2 className="post-title">{post.title}</h2>
      <p className="post-excerpt">{post.excerpt}</p>
      <div className="post-foot">
        <span className="blind-uid">{post.blindUid}</span>
        <span>{post.lessons} found this useful</span>
      </div>
    </article>
  );
}
