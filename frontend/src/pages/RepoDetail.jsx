import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getRepoReviews, getMetrics } from '../api/client.js'
import ReviewCard from '../components/ReviewCard.jsx'
import MetricsChart from '../components/MetricsChart.jsx'
import Navbar from '../components/Navbar.jsx'

export default function RepoDetail() {
  const { owner, repo } = useParams()
  const [reviews, setReviews] = useState([])
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getRepoReviews(owner, repo), getMetrics(owner, repo)])
      .then(([r, m]) => { setReviews(r); setMetrics(m) })
      .finally(() => setLoading(false))
  }, [owner, repo])

  return (
    <div style={s.page}>
      <Navbar />
      <div style={s.pageHeader}>
        <div style={s.pageHeaderInner}>
          <Link to="/" style={s.breadcrumb}>
            <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" style={{ marginRight: '4px' }}>
              <path d="M7.78 12.53a.75.75 0 0 1-1.06 0L2.47 8.28a.75.75 0 0 1 0-1.06l4.25-4.25a.751.751 0 0 1 1.042.018.751.751 0 0 1 .018 1.042L4.56 7.25h8.69a.75.75 0 0 1 0 1.5H4.56l3.22 3.22a.75.75 0 0 1 0 1.06Z"/>
            </svg>
            All repos
          </Link>
          <h1 style={s.repoTitle}>
            <span style={s.ownerPart}>{owner}</span>
            <span style={s.slash}>/</span>
            <span>{repo}</span>
          </h1>
        </div>
      </div>
      <main style={s.main}>
        {loading ? (
          <LoadingSkeleton />
        ) : (
          <>
            {metrics && (
              <section style={s.section}>
                <SectionLabel>Overview</SectionLabel>
                <div style={s.statsGrid}>
                  <StatCard label="Total Reviews" value={metrics.total_reviews} color="var(--purple)" />
                  <StatCard label="Avg Comments / PR" value={metrics.avg_comments_per_pr?.toFixed(1) ?? '—'} color="var(--blue)" />
                  <StatCard label="Avg Review Time" value={`${((metrics.avg_review_duration_ms || 0) / 1000).toFixed(1)}s`} color="var(--green)" />
                </div>
                {metrics.issues_by_category?.length > 0 && (
                  <MetricsChart data={metrics.issues_by_category} />
                )}
                {metrics.top_flagged_files?.length > 0 && (
                  <div style={s.flaggedFiles}>
                    <div style={s.flaggedHeader}>
                      <SectionLabel>Most Flagged Files</SectionLabel>
                    </div>
                    {metrics.top_flagged_files.map((f) => (
                      <div key={f.file_path} style={s.fileRow}>
                        <code style={s.filePath}>{f.file_path}</code>
                        <span style={s.fileBadge}>{f.count} issues</span>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            )}
            <section style={s.section}>
              <SectionLabel>PR Reviews</SectionLabel>
              {reviews.length === 0 ? (
                <div style={s.empty}>No reviews yet for this repository.</div>
              ) : (
                reviews.map((r) => (
                  <ReviewCard key={r.pr_number} review={r} owner={owner} repo={repo} />
                ))
              )}
            </section>
          </>
        )}
      </main>
    </div>
  )
}

function SectionLabel({ children }) {
  return <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '12px' }}>{children}</div>
}

function StatCard({ label, value, color }) {
  return (
    <div style={s.stat}>
      <div style={{ ...s.statValue, color }}>{value}</div>
      <div style={s.statLabel}>{label}</div>
    </div>
  )
}

function LoadingSkeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div style={{ height: '120px', background: 'var(--bg-2)', borderRadius: '10px', border: '1px solid var(--border)' }} />
      <div style={{ height: '200px', background: 'var(--bg-2)', borderRadius: '10px', border: '1px solid var(--border)' }} />
    </div>
  )
}

const s = {
  page: { minHeight: '100vh', background: 'var(--bg)' },
  pageHeader: {
    borderBottom: '1px solid var(--border)',
    background: 'var(--bg-2)',
    padding: '0 32px',
  },
  pageHeaderInner: {
    maxWidth: '900px', margin: '0 auto',
    padding: '20px 0',
  },
  breadcrumb: {
    display: 'inline-flex', alignItems: 'center',
    fontSize: '12px', color: 'var(--text-3)',
    marginBottom: '8px',
    transition: 'color 0.15s',
  },
  repoTitle: {
    fontSize: '22px', fontWeight: 700,
    color: 'var(--text)', letterSpacing: '-0.02em',
  },
  ownerPart: { color: 'var(--text-2)' },
  slash: { color: 'var(--text-3)', margin: '0 2px' },
  main: { maxWidth: '900px', margin: '0 auto', padding: '32px 32px 60px' },
  section: { marginBottom: '40px' },
  statsGrid: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginBottom: '12px' },
  stat: {
    background: 'var(--bg-2)', border: '1px solid var(--border)',
    borderRadius: '10px', padding: '20px 24px',
  },
  statValue: { fontSize: '30px', fontWeight: 800, letterSpacing: '-0.03em', marginBottom: '4px' },
  statLabel: { fontSize: '12px', color: 'var(--text-3)', fontWeight: 500 },
  flaggedFiles: { marginTop: '12px' },
  flaggedHeader: { marginBottom: '8px' },
  fileRow: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '10px 14px', background: 'var(--bg-2)', border: '1px solid var(--border)',
    borderRadius: '8px', marginBottom: '4px',
  },
  filePath: { fontSize: '13px', color: 'var(--text-2)', fontFamily: 'ui-monospace, monospace', flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginRight: '12px' },
  fileBadge: {
    background: 'rgba(248,81,73,0.1)', color: 'var(--red)',
    border: '1px solid rgba(248,81,73,0.25)',
    padding: '2px 8px', borderRadius: '10px', fontSize: '11px', fontWeight: 600, flexShrink: 0,
  },
  empty: { color: 'var(--text-3)', fontSize: '14px', padding: '40px 0', textAlign: 'center' },
}
