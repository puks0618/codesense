import { useEffect, useState } from 'react'
import { getRepos } from '../api/client.js'
import RepoList from '../components/RepoList.jsx'
import Navbar from '../components/Navbar.jsx'

export default function Dashboard() {
  const [repos, setRepos] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    getRepos()
      .then(setRepos)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div style={s.page}>
      <Navbar />
      <div style={s.hero}>
        <div style={s.heroBadge}>AI-Powered Code Review</div>
        <h1 style={s.heroTitle}>Your Repositories</h1>
        <p style={s.heroSub}>CodeSense automatically reviews every pull request and learns your team's style over time.</p>
      </div>
      <main style={s.main}>
        {loading ? (
          <Skeleton />
        ) : error ? (
          <div style={s.errorBox}>
            <span style={s.errorIcon}>⚠</span>
            <span>Failed to load repositories: {error}</span>
          </div>
        ) : repos.length === 0 ? (
          <EmptyState />
        ) : (
          <RepoList repos={repos} />
        )}
      </main>
    </div>
  )
}

function EmptyState() {
  return (
    <div style={s.empty}>
      <div style={s.emptyIcon}>⚡</div>
      <h3 style={s.emptyTitle}>No repositories yet</h3>
      <p style={s.emptySub}>Install the GitHub App on a repository to start getting AI code reviews.</p>
    </div>
  )
}

function Skeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {[1, 2, 3].map((i) => (
        <div key={i} style={s.skeletonCard} />
      ))}
    </div>
  )
}

const s = {
  page: { minHeight: '100vh', background: 'var(--bg)' },
  hero: {
    padding: '60px 32px 40px',
    maxWidth: '900px',
    margin: '0 auto',
    textAlign: 'center',
  },
  heroBadge: {
    display: 'inline-block',
    background: 'var(--accent-glow)',
    color: 'var(--purple)',
    border: '1px solid rgba(124,58,237,0.3)',
    borderRadius: '20px',
    padding: '4px 14px',
    fontSize: '12px',
    fontWeight: 600,
    letterSpacing: '0.04em',
    textTransform: 'uppercase',
    marginBottom: '16px',
  },
  heroTitle: {
    fontSize: '36px',
    fontWeight: 700,
    color: 'var(--text)',
    marginBottom: '12px',
    letterSpacing: '-0.02em',
  },
  heroSub: {
    fontSize: '15px',
    color: 'var(--text-2)',
    maxWidth: '480px',
    margin: '0 auto',
    lineHeight: 1.6,
  },
  main: { maxWidth: '900px', margin: '0 auto', padding: '0 32px 60px' },
  errorBox: {
    display: 'flex', alignItems: 'center', gap: '10px',
    background: 'rgba(248,81,73,0.08)', border: '1px solid rgba(248,81,73,0.3)',
    borderRadius: '8px', padding: '14px 18px', color: 'var(--red)', fontSize: '14px',
  },
  errorIcon: { fontSize: '16px' },
  empty: {
    textAlign: 'center', padding: '80px 24px',
    background: 'var(--bg-2)', borderRadius: '12px',
    border: '1px solid var(--border)',
  },
  emptyIcon: { fontSize: '40px', marginBottom: '16px' },
  emptyTitle: { fontSize: '18px', fontWeight: 600, color: 'var(--text)', marginBottom: '8px' },
  emptySub: { fontSize: '14px', color: 'var(--text-2)', maxWidth: '360px', margin: '0 auto' },
  skeletonCard: {
    height: '80px', borderRadius: '10px',
    background: 'linear-gradient(90deg, var(--bg-2) 0%, var(--bg-3) 50%, var(--bg-2) 100%)',
    border: '1px solid var(--border)',
    animation: 'pulse 1.5s ease-in-out infinite',
  },
}
