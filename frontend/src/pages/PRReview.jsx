import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getReview } from '../api/client.js'

const SEV = {
  critical: { color: '#cf222e', label: '🔴 Critical' },
  warning: { color: '#bf5700', label: '🟠 Warning' },
  suggestion: { color: '#0969da', label: '🔵 Suggestion' },
  info: { color: '#57606a', label: 'ℹ️ Info' },
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

  if (loading) return <div style={s.center}>Loading...</div>
  if (!review) return <div style={s.center}>Review not found.</div>

  const grouped = {}
  for (const c of review.comments || []) {
    if (!grouped[c.file_path]) grouped[c.file_path] = []
    grouped[c.file_path].push(c)
  }

  return (
    <div style={s.page}>
      <header style={s.header}>
        <Link to={`/repos/${owner}/${repo}`} style={s.back}>← {owner}/{repo}</Link>
        <h1 style={s.title}>PR #{prNumber}: {review.pr_title}</h1>
      </header>
      <main style={s.main}>
        {review.summary && (
          <div style={s.summaryBox}>
            <button style={s.summaryToggle} onClick={() => setSummaryOpen(!summaryOpen)}>
              {summaryOpen ? '▾' : '▸'} Summary
            </button>
            {summaryOpen && <p style={s.summaryText}>{review.summary}</p>}
          </div>
        )}
        {Object.keys(grouped).length === 0 ? (
          <p style={s.empty}>No inline comments for this review.</p>
        ) : (
          Object.entries(grouped).map(([filePath, comments]) => (
            <div key={filePath} style={s.fileSection}>
              <div style={s.fileName}>{filePath}</div>
              {comments.map((c, i) => {
                const sev = SEV[c.severity] || SEV.info
                return (
                  <div key={i} style={s.comment}>
                    <div style={s.commentMeta}>
                      <span style={{ ...s.sevBadge, color: sev.color }}>{sev.label}</span>
                      {c.category && (
                        <span style={s.catTag}>{c.category.toUpperCase()}</span>
                      )}
                      <span style={s.lineNum}>Line {c.line}</span>
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

const s = {
  page: { fontFamily: 'inherit', minHeight: '100vh', background: '#f6f8fa' },
  header: { background: '#24292f', color: '#fff', padding: '16px 32px' },
  back: { color: '#8b949e', textDecoration: 'none', fontSize: '13px', display: 'block', marginBottom: '8px' },
  title: { margin: 0, fontSize: '18px', fontWeight: 700 },
  main: { maxWidth: '900px', margin: '0 auto', padding: '32px 24px' },
  summaryBox: {
    background: '#fff', border: '1px solid #d0d7de', borderRadius: '8px',
    padding: '12px 16px', marginBottom: '24px',
  },
  summaryToggle: {
    background: 'none', border: 'none', cursor: 'pointer',
    fontWeight: 600, fontSize: '14px', color: '#24292f', padding: 0,
  },
  summaryText: { margin: '10px 0 0', color: '#24292f', fontSize: '14px', lineHeight: 1.6 },
  fileSection: { marginBottom: '20px' },
  fileName: {
    background: '#f0f6ff', border: '1px solid #d0d7de', borderRadius: '6px 6px 0 0',
    padding: '8px 14px', fontFamily: 'monospace', fontSize: '13px', fontWeight: 600, color: '#24292f',
  },
  comment: {
    background: '#fff', border: '1px solid #d0d7de', borderTop: 'none',
    padding: '12px 14px',
  },
  commentMeta: { display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '6px' },
  sevBadge: { fontSize: '12px', fontWeight: 600 },
  catTag: {
    fontSize: '11px', color: '#57606a', background: '#f6f8fa',
    border: '1px solid #d0d7de', padding: '1px 6px', borderRadius: '4px',
  },
  lineNum: { fontSize: '12px', color: '#57606a', marginLeft: 'auto' },
  commentTitle: { fontWeight: 600, fontSize: '14px', color: '#24292f', marginBottom: '6px' },
  commentBody: { fontSize: '13px', color: '#24292f', lineHeight: 1.6 },
  empty: { color: '#57606a', fontSize: '14px' },
  center: { display: 'flex', justifyContent: 'center', alignItems: 'center', height: '80vh', color: '#57606a' },
}
