import { BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ResponsiveContainer } from 'recharts'

const COLORS = {
  security: '#cf222e',
  performance: '#fb8500',
  style: '#0969da',
  correctness: '#6e40c9',
  maintainability: '#1a7f37',
}

export default function MetricsChart({ data }) {
  const chartData = data.map((d) => ({
    name: d.category || 'other',
    count: d.count,
    fill: COLORS[d.category] || '#57606a',
  }))

  return (
    <div>
      <h3 style={s.title}>Issues by Category</h3>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
          <XAxis dataKey="name" tick={{ fontSize: 12 }} />
          <YAxis allowDecimals={false} tick={{ fontSize: 12 }} width={32} />
          <Tooltip />
          <Bar dataKey="count" radius={[4, 4, 0, 0]}>
            {chartData.map((entry, i) => (
              <Cell key={i} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

const s = {
  title: { fontSize: '14px', fontWeight: 600, color: '#24292f', marginBottom: '12px' },
}
