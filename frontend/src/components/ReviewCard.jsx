import { Link } from 'react-router-dom'

const VERDICT = {
  APPROVE: { color: 'var(--green)', bg: 'rgba(63,185,80,0.1)', border: 'rgba(63,185,80,0.25)', icon: '✓', label: 'Approved' },
  REQUEST_CHANGES: { color: 'var(--red)', bg: 'rgba(248,81,73,0.1)', border: 'rgba(248,81,73,0.25)', icon: '✗', label: 'Changes Requested' },
  COMMENT: { color: 'var(--blue)', bg: 'rgba(88,166,255,0.1)', border: 'rgba(88,166,255,0.25)', icon: '●', label: 'Commented' },
}

export default function ReviewCard({ review, owner, repo }) {
  const v = VERDICT[review.verdict] || VERDICT.COMMENT
  const date = review.created_at
    ? new Date(review.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    : null

  return (
    <Link to={`/repos/${owner}/${repo}/reviews/${review.pr_number}`} style={s.card}>
      <div style={s.top}>
        <div style={s.prInfo}>
          <span style={s.prNum}>#{review.pr_number}</span>
          <span style={s.prTitle}>{review.pr_title || '(no title)'}</span>
        </div>
        <span style={{ ...s.verdict, color: v.color, background: v.bg, border: `1px solid ${v.border}` }}>
          {v.icon} {v.label}
        </span>
      </div>
      <div style={s.meta}>
        <MetaItem icon="💬" value={`${review.comment_count ?? 0} comment${review.comment_count !== 1 ? 's' : ''}`} />
        {review.review_duration_ms > 0 && (
          <MetaItem icon="⏱" value={`${(review.review_duration_ms / 1000).toFixed(1)}s`} />
        )}
        {date && <MetaItem icon="📅" value={date} />}
      </div>
    </Link>
  )
}

function MetaItem({ icon, value }) {
  return (
    <span style={s.metaItem}>
      <span style={s.metaIcon}>{icon}</span>
      {value}
    </span>
  )
}

const s = {
  card: {
    display: 'block', background: 'var(--bg-2)', border: '1px solid var(--border)',
    borderRadius: '10px', padding: '14px 18px', marginBottom: '8px',
    transition: 'border-color 0.15s',
  },
  top: { display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px', marginBottom: '10px' },
  prInfo: { display: 'flex', alignItems: 'center', gap: '8px', flex: 1, minWidth: 0 },
  prNum: { color: 'var(--text-3)', fontWeight: 600, fontSize: '13px', flexShrink: 0 },
  prTitle: { color: 'var(--text)', fontWeight: 500, fontSize: '14px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
  verdict: { padding: '3px 10px', borderRadius: '20px', fontSize: '12px', fontWeight: 600, flexShrink: 0, whiteSpace: 'nowrap' },
  meta: { display: 'flex', gap: '16px', flexWrap: 'wrap' },
  metaItem: { display: 'flex', alignItems: 'center', gap: '5px', fontSize: '12px', color: 'var(--text-3)' },
  metaIcon: { fontSize: '11px' },
}
