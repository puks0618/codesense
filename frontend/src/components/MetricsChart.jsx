import { BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ResponsiveContainer } from 'recharts'

const COLORS = {
  security: '#f85149',
  performance: '#d29922',
  style: '#58a6ff',
  correctness: '#bc8cff',
  maintainability: '#3fb950',
}

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const { name, count, fill } = payload[0].payload
  return (
    <div style={tt.box}>
      <span style={{ ...tt.dot, background: fill }} />
      <span style={tt.label}>{name}</span>
      <span style={tt.value}>{count}</span>
    </div>
  )
}

const tt = {
  box: {
    background: 'var(--bg-3)', border: '1px solid var(--border-2)',
    borderRadius: '8px', padding: '8px 12px',
    display: 'flex', alignItems: 'center', gap: '8px',
    fontSize: '13px', color: 'var(--text)',
  },
  dot: { width: '8px', height: '8px', borderRadius: '50%', flexShrink: 0 },
  label: { color: 'var(--text-2)', flex: 1 },
  value: { fontWeight: 700, color: 'var(--text)' },
}

export default function MetricsChart({ data }) {
  const chartData = data.map((d) => ({
    name: d.category || 'other',
    count: d.count,
    fill: COLORS[d.category] || '#656d76',
  }))

  return (
    <div style={s.wrap}>
      <div style={s.header}>
        <span style={s.title}>Issues by Category</span>
        <div style={s.legend}>
          {chartData.map((d) => (
            <span key={d.name} style={s.legendItem}>
              <span style={{ ...s.legendDot, background: d.fill }} />
              {d.name}
            </span>
          ))}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 4 }} barCategoryGap="35%">
          <XAxis dataKey="name" tick={{ fontSize: 11, fill: 'var(--text-3)' }} axisLine={false} tickLine={false} />
          <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: 'var(--text-3)' }} axisLine={false} tickLine={false} />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
          <Bar dataKey="count" radius={[4, 4, 0, 0]}>
            {chartData.map((entry, i) => (
              <Cell key={i} fill={entry.fill} fillOpacity={0.85} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

const s = {
  wrap: {
    background: 'var(--bg-3)', border: '1px solid var(--border)',
    borderRadius: '10px', padding: '16px 20px', marginBottom: '8px',
  },
  header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '8px' },
  title: { fontSize: '13px', fontWeight: 600, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '0.06em' },
  legend: { display: 'flex', gap: '12px', flexWrap: 'wrap' },
  legendItem: { display: 'flex', alignItems: 'center', gap: '5px', fontSize: '11px', color: 'var(--text-3)' },
  legendDot: { width: '7px', height: '7px', borderRadius: '50%' },
}
