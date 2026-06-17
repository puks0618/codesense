import { Link } from 'react-router-dom'

export default function Navbar() {
  return (
    <nav style={s.nav}>
      <div style={s.inner}>
        <Link to="/" style={s.brand}>
          <span style={s.logo}>⚡</span>
          <span style={s.brandName}>CodeSense</span>
        </Link>
        <div style={s.right}>
          <span style={s.badge}>Beta</span>
        </div>
      </div>
    </nav>
  )
}

const s = {
  nav: {
    position: 'sticky', top: 0, zIndex: 100,
    background: 'rgba(13,17,23,0.85)',
    backdropFilter: 'blur(12px)',
    borderBottom: '1px solid var(--border)',
  },
  inner: {
    maxWidth: '900px', margin: '0 auto',
    padding: '0 32px', height: '56px',
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  },
  brand: { display: 'flex', alignItems: 'center', gap: '8px', textDecoration: 'none' },
  logo: { fontSize: '18px' },
  brandName: { fontWeight: 700, fontSize: '16px', color: 'var(--text)', letterSpacing: '-0.01em' },
  right: { display: 'flex', alignItems: 'center', gap: '12px' },
  badge: {
    fontSize: '11px', fontWeight: 600, color: 'var(--purple)',
    background: 'var(--accent-glow)', border: '1px solid rgba(124,58,237,0.3)',
    padding: '2px 8px', borderRadius: '10px', letterSpacing: '0.04em',
  },
}
