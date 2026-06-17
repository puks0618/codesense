import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getReview } from '../api/client.js'
import Navbar from '../components/Navbar.jsx'

const SEV = {
  critical: { color: 'var(--red)', bg: 'rgba(248,81,73,0.1)', border: 'rgba(248,81,73,0.25)', icon: '🔴', label: 'Critical' },
  warning:  { color: 'var(--orange)', bg: 'rgba(210,153,34,0.1)', border: 'rgba(210,153,34,0.25)', icon: '🟡', label: 'Warning' },
  suggestion: { color: 'var(--blue)', bg: 'rgba(88,166,255,0.1)', border: 'rgba(88,166,255,0.25)', icon: '🔵', label: 'Suggestion' },
  info: { color: 'var(--text-2)', bg: 'var(--bg-3)', border: 'var(--border)', icon: 'ℹ', label: 'Info' },
}

export default function PRReview() {
  const { owner, repo, prNumber } = useParams()
  const [review, setReview] = useState(null)
  const [summaryOpen, setSummaryOpen] = useState(true)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getReview(owner, repo, prNumber)
      .then(setReview)
      .finally(() => setLoading(false))
  }, [owner, repo, prNumber])

  if (loading) return (
    <div style={s.page}>
      <Navbar />
      <div style={s.center}><Spinner /></div>
    </div>
  )

  if (!review) return (
    <div style={s.page}>
      <Navbar />
      <div style={s.center} >
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '32px', marginBottom: '12px' }}>🔍</div>
          <div style={{ color: 'var(--text-2)', fontSize: '15px' }}>Review not found.</div>
        </div>
      </div>
    </div>
  )

  const grouped = {}
  for (const c of review.comments || []) {
    if (!grouped[c.file_path]) grouped[c.file_path] = []
    grouped[c.file_path].push(c)
  }

  const criticalCount = (review.comments || []).filter(c => c.severity === 'critical').length
  const warningCount = (review.comments || []).filter(c => c.severity === 'warning').length

  return (
    <div style={s.page}>
      <Navbar />
      <div style={s.pageHeader}>
        <div style={s.pageHeaderInner}>
          <Link to={`/repos/${owner}/${repo}`} style={s.breadcrumb}>
            <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" style={{ marginRight: '4px' }}>
              <path d="M7.78 12.53a.75.75 0 0 1-1.06 0L2.47 8.28a.75.75 0 0 1 0-1.06l4.25-4.25a.751.751 0 0 1 1.042.018.751.751 0 0 1 .018 1.042L4.56 7.25h8.69a.75.75 0 0 1 0 1.5H4.56l3.22 3.22a.75.75 0 0 1 0 1.06Z"/>
            </svg>
            {owner}/{repo}
          </Link>
          <div style={s.prMeta}>
            <span style={s.prNum}>PR #{prNumber}</span>
            <h1 style={s.prTitle}>{review.pr_title}</h1>
          </div>
          {(criticalCount > 0 || warningCount > 0) && (
            <div style={s.badges}>
              {criticalCount > 0 && (
                <span style={{ ...s.countBadge, color: 'var(--red)', background: 'rgba(248,81,73,0.1)', border: '1px solid rgba(248,81,73,0.25)' }}>
                  🔴 {criticalCount} critical
                </span>
              )}
              {warningCount > 0 && (
                <span style={{ ...s.countBadge, color: 'var(--orange)', background: 'rgba(210,153,34,0.1)', border: '1px solid rgba(210,153,34,0.25)' }}>
                  🟡 {warningCount} warning{warningCount !== 1 ? 's' : ''}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
      <main style={s.main}>
        {review.summary && (
          <div style={s.summaryBox}>
            <button style={s.summaryToggle} onClick={() => setSummaryOpen(!summaryOpen)}>
              <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor" style={{ transition: 'transform 0.15s', transform: summaryOpen ? 'rotate(90deg)' : 'rotate(0deg)' }}>
                <path d="M6.22 3.22a.75.75 0 0 1 1.06 0l4.25 4.25a.75.75 0 0 1 0 1.06l-4.25 4.25a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042L9.94 8 6.22 4.28a.75.75 0 0 1 0-1.06Z"/>
              </svg>
              <span>Summary</span>
            </button>
            {summaryOpen && <p style={s.summaryText}>{review.summary}</p>}
          </div>
        )}

        {Object.keys(grouped).length === 0 ? (
          <div style={s.emptyComments}>
            <div style={{ fontSize: '28px', marginBottom: '10px' }}>✅</div>
            <div style={{ color: 'var(--text-2)', fontSize: '14px' }}>No inline comments for this review.</div>
          </div>
        ) : (
          Object.entries(grouped).map(([filePath, comments]) => (
            <div key={filePath} style={s.fileSection}>
              <div style={s.fileHeader}>
                <svg width="13" height="13" viewBox="0 0 16 16" fill="var(--text-3)" style={{ flexShrink: 0 }}>
                  <path d="M2 1.75C2 .784 2.784 0 3.75 0h6.586c.464 0 .909.184 1.237.513l2.914 2.914c.329.328.513.773.513 1.237v9.586A1.75 1.75 0 0 1 13.25 16h-9.5A1.75 1.75 0 0 1 2 14.25Zm1.75-.25a.25.25 0 0 0-.25.25v12.5c0 .138.112.25.25.25h9.5a.25.25 0 0 0 .25-.25V6h-2.75A1.75 1.75 0 0 1 9 4.25V1.5Zm6.75.062V4.25c0 .138.112.25.25.25h2.688Z"/>
                </svg>
                <code style={s.fileName}>{filePath}</code>
                <span style={s.commentCount}>{comments.length}</span>
              </div>
              {comments.map((c, i) => {
                const sev = SEV[c.severity] || SEV.info
                return (
                  <div key={i} style={{ ...s.comment, borderTop: i > 0 ? '1px solid var(--border)' : 'none' }}>
                    <div style={s.commentHeader}>
                      <span style={{ ...s.sevBadge, color: sev.color, background: sev.bg, border: `1px solid ${sev.border}` }}>
                        {sev.icon} {sev.label}
                      </span>
                      {c.category && (
                        <span style={s.catTag}>{c.category}</span>
                      )}
                      <span style={s.lineTag}>line {c.line}</span>
                    </div>
                    <div style={s.commentTitle}>{c.title}</div>
                    <div style={s.commentBody}>{c.body}</div>
                  </div>
                )
              })}
            </div>
          ))
        )}
      </main>
    </div>
  )
}

function Spinner() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px', color: 'var(--text-3)' }}>
      <div style={{ width: '28px', height: '28px', border: '2px solid var(--border)', borderTopColor: 'var(--purple)', borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} />
      <span style={{ fontSize: '13px' }}>Loading review...</span>
    </div>
  )
}

const s = {
  page: { minHeight: '100vh', background: 'var(--bg)' },
  center: { display: 'flex', justifyContent: 'center', alignItems: 'center', height: 'calc(100vh - 56px)' },
  pageHeader: { background: 'var(--bg-2)', borderBottom: '1px solid var(--border)', padding: '0 32px' },
  pageHeaderInner: { maxWidth: '900px', margin: '0 auto', padding: '20px 0' },
  breadcrumb: {
    display: 'inline-flex', alignItems: 'center',
    fontSize: '12px', color: 'var(--text-3)', marginBottom: '10px',
  },
  prMeta: { display: 'flex', alignItems: 'baseline', gap: '10px', flexWrap: 'wrap' },
  prNum: { fontSize: '14px', color: 'var(--text-3)', fontWeight: 600, flexShrink: 0 },
  prTitle: { fontSize: '20px', fontWeight: 700, color: 'var(--text)', letterSpacing: '-0.01em' },
  badges: { display: 'flex', gap: '8px', marginTop: '10px', flexWrap: 'wrap' },
  countBadge: { padding: '3px 10px', borderRadius: '20px', fontSize: '12px', fontWeight: 600 },
  main: { maxWidth: '900px', margin: '0 auto', padding: '28px 32px 60px' },
  summaryBox: {
    background: 'var(--bg-2)', border: '1px solid var(--border)',
    borderRadius: '10px', padding: '14px 18px', marginBottom: '24px',
  },
  summaryToggle: {
    display: 'flex', alignItems: 'center', gap: '7px',
    fontSize: '13px', fontWeight: 600, color: 'var(--text-2)',
    background: 'none', border: 'none', padding: 0, cursor: 'pointer',
  },
  summaryText: { color: 'var(--text-2)', fontSize: '14px', lineHeight: 1.7, marginTop: '12px' },
  emptyComments: { textAlign: 'center', padding: '60px 0', color: 'var(--text-3)' },
  fileSection: {
    marginBottom: '16px',
    border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden',
  },
  fileHeader: {
    display: 'flex', alignItems: 'center', gap: '8px',
    background: 'var(--bg-3)', padding: '10px 16px',
    borderBottom: '1px solid var(--border)',
  },
  fileName: { fontSize: '13px', color: 'var(--text-2)', fontFamily: 'ui-monospace, monospace', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
  commentCount: {
    background: 'var(--bg-2)', border: '1px solid var(--border)',
    color: 'var(--text-3)', borderRadius: '10px',
    padding: '1px 7px', fontSize: '11px', fontWeight: 600, flexShrink: 0,
  },
  comment: { padding: '14px 16px', background: 'var(--bg-2)' },
  commentHeader: { display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', flexWrap: 'wrap' },
  sevBadge: { padding: '2px 8px', borderRadius: '10px', fontSize: '11px', fontWeight: 700 },
  catTag: {
    fontSize: '11px', color: 'var(--text-3)', background: 'var(--bg-3)',
    border: '1px solid var(--border)', padding: '2px 7px', borderRadius: '6px', textTransform: 'uppercase', letterSpacing: '0.04em',
  },
  lineTag: { marginLeft: 'auto', fontSize: '11px', color: 'var(--text-3)', fontFamily: 'ui-monospace, monospace' },
  commentTitle: { fontWeight: 600, fontSize: '14px', color: 'var(--text)', marginBottom: '6px' },
  commentBody: { fontSize: '13px', color: 'var(--text-2)', lineHeight: 1.7 },
}
