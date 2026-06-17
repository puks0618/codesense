import { Link } from 'react-router-dom'

const VERDICT_STYLE = {
  APPROVE: { bg: '#dafbe1', color: '#1a7f37', label: '✓ Approved' },
  REQUEST_CHANGES: { bg: '#ffebe9', color: '#cf222e', label: '✗ Changes Requested' },
  COMMENT: { bg: '#ddf4ff', color: '#0969da', label: '● Commented' },
}

export default function ReviewCard({ review, owner, repo }) {
  const v = VERDICT_STYLE[review.verdict] || VERDICT_STYLE.COMMENT
  return (
    <Link to={`/repos/${owner}/${repo}/reviews/${review.pr_number}`} style={s.card}>
      <div style={s.row}>
        <span style={s.prNum}>#{review.pr_number}</span>
        <span style={s.title}>{review.pr_title || '(no title)'}</span>
        <span style={{ ...s.verdict, background: v.bg, color: v.color }}>{v.label}</span>
      </div>
      <div style={s.meta}>
        <span>{review.comment_count ?? 0} comment{review.comment_count !== 1 ? 's' : ''}</span>
        {review.review_duration_ms > 0 && (
          <span>· {(review.review_duration_ms / 1000).toFixed(1)}s</span>
        )}
        {review.created_at && (
          <span>· {new Date(review.created_at).toLocaleDateString()}</span>
        )}
      </div>
    </Link>
  )
}

const s = {
  card: {
    display: 'block', background: '#fff', border: '1px solid #d0d7de',
    borderRadius: '8px', padding: '14px 18px', textDecoration: 'none',
    color: 'inherit', marginBottom: '8px',
  },
  row: { display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' },
  prNum: { color: '#57606a', fontWeight: 600, fontSize: '13px', flexShrink: 0 },
  title: { color: '#24292f', fontWeight: 500, fontSize: '14px', flex: 1 },
  verdict: { padding: '2px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 500, flexShrink: 0 },
  meta: { color: '#57606a', fontSize: '12px', display: 'flex', gap: '4px' },
}
