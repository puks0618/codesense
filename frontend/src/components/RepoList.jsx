import { Link } from 'react-router-dom'

export default function RepoList({ repos }) {
  return (
    <div style={s.list}>
      {repos.map((repo) => {
        const [owner, name] = repo.repo_full_name.split('/')
        return (
          <Link key={repo.repo_full_name} to={`/repos/${owner}/${name}`} style={s.card}>
            <div style={s.repoName}>{repo.repo_full_name}</div>
            <div style={s.meta}>
              <span style={s.badge}>{repo.review_count} review{repo.review_count !== 1 ? 's' : ''}</span>
              {repo.last_reviewed_at && (
                <span style={s.date}>
                  Last: {new Date(repo.last_reviewed_at).toLocaleDateString()}
                </span>
              )}
            </div>
          </Link>
        )
      })}
    </div>
  )
}

const s = {
  list: { display: 'flex', flexDirection: 'column', gap: '10px' },
  card: {
    display: 'block', background: '#fff', border: '1px solid #d0d7de',
    borderRadius: '8px', padding: '16px 20px', textDecoration: 'none', color: 'inherit',
  },
  repoName: { fontWeight: 600, fontSize: '15px', color: '#0969da', marginBottom: '8px' },
  meta: { display: 'flex', gap: '14px', alignItems: 'center' },
  badge: {
    background: '#ddf4ff', color: '#0969da', padding: '2px 8px',
    borderRadius: '12px', fontSize: '12px', fontWeight: 500,
  },
  date: { color: '#57606a', fontSize: '12px' },
}
