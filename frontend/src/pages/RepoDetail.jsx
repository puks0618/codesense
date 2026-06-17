import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getRepoReviews, getMetrics } from '../api/client.js'
import ReviewCard from '../components/ReviewCard.jsx'
import MetricsChart from '../components/MetricsChart.jsx'

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

  if (loading) return <div style={s.center}>Loading...</div>

  return (
    <div style={s.page}>
      <header style={s.header}>
        <Link to="/" style={s.back}>← Dashboard</Link>
        <h1 style={s.title}>{owner}/{repo}</h1>
      </header>
      <main style={s.main}>
        {metrics && (
          <section style={s.section}>
            <h2 style={s.sectionTitle}>Metrics</h2>
            <div style={s.stats}>
              <Stat label="Total Reviews" value={metrics.total_reviews} />
              <Stat label="Avg Comments / PR" value={metrics.avg_comments_per_pr} />
              <Stat label="Avg Review Time" value={`${(metrics.avg_review_duration_ms / 1000).toFixed(1)}s`} />
            </div>
            {metrics.issues_by_category?.length > 0 && (
              <MetricsChart data={metrics.issues_by_category} />
            )}
            {metrics.top_flagged_files?.length > 0 && (
              <div style={{ marginTop: '24px' }}>
                <h3 style={s.subTitle}>Most Flagged Files</h3>
                {metrics.top_flagged_files.map((f) => (
                  <div key={f.file_path} style={s.fileRow}>
                    <code style={s.filePath}>{f.file_path}</code>
                    <span style={s.fileBadge}>{f.count}</span>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}
        <section style={s.section}>
          <h2 style={s.sectionTitle}>PR Reviews</h2>
          {reviews.length === 0 ? (
            <p style={s.empty}>No reviews yet for this repository.</p>
          ) : (
            reviews.map((r) => (
              <ReviewCard key={r.pr_number} review={r} owner={owner} repo={repo} />
            ))
          )}
        </section>
      </main>
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <div style={s.stat}>
      <div style={s.statValue}>{value}</div>
      <div style={s.statLabel}>{label}</div>
    </div>
  )
}

const s = {
  page: { fontFamily: 'inherit', minHeight: '100vh', background: '#f6f8fa' },
  header: { background: '#24292f', color: '#fff', padding: '16px 32px' },
  back: { color: '#8b949e', textDecoration: 'none', fontSize: '13px', display: 'block', marginBottom: '8px' },
  title: { margin: 0, fontSize: '20px', fontWeight: 700 },
  main: { maxWidth: '900px', margin: '0 auto', padding: '32px 24px' },
  section: { marginBottom: '40px' },
  sectionTitle: { fontSize: '18px', fontWeight: 600, color: '#24292f', marginBottom: '16px' },
  subTitle: { fontSize: '14px', fontWeight: 600, color: '#24292f', marginBottom: '10px' },
  stats: { display: 'flex', gap: '20px', marginBottom: '24px', flexWrap: 'wrap' },
  stat: {
    background: '#fff', border: '1px solid #d0d7de', borderRadius: '8px',
    padding: '16px 24px', textAlign: 'center', minWidth: '130px',
  },
  statValue: { fontSize: '28px', fontWeight: 700, color: '#24292f' },
  statLabel: { fontSize: '12px', color: '#57606a', marginTop: '4px' },
  fileRow: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '8px 12px', background: '#fff', border: '1px solid #d0d7de',
    borderRadius: '6px', marginBottom: '4px',
  },
  filePath: { fontSize: '13px', color: '#24292f', fontFamily: 'monospace' },
  fileBadge: {
    background: '#ffebe9', color: '#cf222e', padding: '2px 8px',
    borderRadius: '12px', fontSize: '12px', fontWeight: 500,
  },
  empty: { color: '#57606a', fontSize: '14px' },
  center: { display: 'flex', justifyContent: 'center', alignItems: 'center', height: '80vh', color: '#57606a' },
}
