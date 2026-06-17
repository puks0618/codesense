import { useEffect, useState } from 'react'
import { getRepos } from '../api/client.js'
import RepoList from '../components/RepoList.jsx'

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

  if (loading) return <div style={s.center}>Loading...</div>
  if (error) return <div style={s.center}>Error: {error}</div>

  return (
    <div style={s.page}>
      <header style={s.header}>
        <h1 style={s.title}>CodeSense</h1>
        <span style={s.subtitle}>AI-powered PR reviews</span>
      </header>
      <main style={s.main}>
        <h2 style={s.sectionTitle}>Connected Repositories</h2>
        {repos.length === 0 ? (
          <p style={s.empty}>
            No repositories reviewed yet. Install the GitHub App to get started.
          </p>
        ) : (
          <RepoList repos={repos} />
        )}
      </main>
    </div>
  )
}

const s = {
  page: { fontFamily: 'inherit', minHeight: '100vh', background: '#f6f8fa' },
  header: {
    background: '#24292f', color: '#fff', padding: '16px 32px',
    display: 'flex', alignItems: 'center', gap: '16px',
  },
  title: { margin: 0, fontSize: '20px', fontWeight: 700 },
  subtitle: { color: '#8b949e', fontSize: '14px' },
  main: { maxWidth: '900px', margin: '0 auto', padding: '32px 24px' },
  sectionTitle: { fontSize: '18px', fontWeight: 600, color: '#24292f', marginBottom: '16px' },
  empty: { color: '#57606a', fontSize: '14px' },
  center: { display: 'flex', justifyContent: 'center', alignItems: 'center', height: '80vh', color: '#57606a' },
}
