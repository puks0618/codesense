import { Link } from 'react-router-dom'

export default function RepoList({ repos }) {
  return (
    <div style={s.list}>
      {repos.map((repo) => {
        const [owner, name] = repo.repo_full_name.split('/')
        return (
          <Link key={repo.repo_full_name} to={`/repos/${owner}/${name}`} style={s.card}>
            <div style={s.cardLeft}>
              <div style={s.repoIcon}>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="var(--text-2)">
                  <path d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8Z"/>
                </svg>
              </div>
              <div>
                <div style={s.repoName}>{repo.repo_full_name}</div>
                {repo.last_reviewed_at && (
                  <div style={s.lastReviewed}>
                    Last reviewed {new Date(repo.last_reviewed_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                  </div>
                )}
              </div>
            </div>
            <div style={s.cardRight}>
              <div style={s.reviewBadge}>
                <span style={s.reviewCount}>{repo.review_count}</span>
                <span style={s.reviewLabel}>review{repo.review_count !== 1 ? 's' : ''}</span>
              </div>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="var(--text-3)">
                <path d="M6.22 3.22a.75.75 0 0 1 1.06 0l4.25 4.25a.75.75 0 0 1 0 1.06l-4.25 4.25a.751.751 0 0 1-1.042-.018.751.751 0 0 1-.018-1.042L9.94 8 6.22 4.28a.75.75 0 0 1 0-1.06Z"/>
              </svg>
            </div>
          </Link>
        )
      })}
    </div>
  )
}

const s = {
  list: { display: 'flex', flexDirection: 'column', gap: '8px' },
  card: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    background: 'var(--bg-2)', border: '1px solid var(--border)',
    borderRadius: '10px', padding: '16px 20px',
    transition: 'border-color 0.15s, background 0.15s',
    cursor: 'pointer',
    ':hover': { borderColor: 'var(--border-2)', background: 'var(--bg-3)' },
  },
  cardLeft: { display: 'flex', alignItems: 'center', gap: '14px' },
  repoIcon: {
    width: '36px', height: '36px',
    background: 'var(--bg-3)', border: '1px solid var(--border)',
    borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center',
    flexShrink: 0,
  },
  repoName: { fontWeight: 600, fontSize: '14px', color: 'var(--text)', marginBottom: '3px' },
  lastReviewed: { fontSize: '12px', color: 'var(--text-3)' },
  cardRight: { display: 'flex', alignItems: 'center', gap: '16px' },
  reviewBadge: { display: 'flex', alignItems: 'baseline', gap: '4px' },
  reviewCount: { fontSize: '18px', fontWeight: 700, color: 'var(--purple)' },
  reviewLabel: { fontSize: '12px', color: 'var(--text-3)' },
}
