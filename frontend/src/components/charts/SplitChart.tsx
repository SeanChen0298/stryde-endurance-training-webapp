"use client"

interface Split {
  km: number
  pace_s_per_km: number | null
  hr: number | null
}

interface Props {
  splits: Split[]
}

export function SplitChart({ splits }: Props) {
  if (!splits.length) return null

  const paces = splits.map((s) => s.pace_s_per_km).filter((v): v is number => v !== null)
  const hrs = splits.map((s) => s.hr).filter((v): v is number => v !== null)

  if (!paces.length) return null

  const W = 300
  const H = 56
  const BAR_H = 40   // bars occupy bottom portion
  const DOT_AREA = H // HR dots use full height

  const paceMin = Math.min(...paces)
  const paceMax = Math.max(...paces)
  const paceRange = paceMax - paceMin || 1

  const hrMin = hrs.length ? Math.min(...hrs) - 5 : 0
  const hrMax = hrs.length ? Math.max(...hrs) + 5 : 200

  const barW = Math.max(2, W / splits.length - 2)
  const avgPace = paces.reduce((a, b) => a + b, 0) / paces.length

  function paceColor(pace: number): string {
    // Relative to avg: faster = green, similar = accent, slower = red
    const diff = pace - avgPace
    const threshold = paceRange * 0.15
    if (diff < -threshold) return "var(--status-green)"
    if (diff > threshold) return "var(--status-red)"
    return "var(--accent)"
  }

  // HR line points
  const hrPts = splits
    .map((s, i) => {
      if (s.hr === null) return null
      const x = (i / splits.length) * W + barW / 2
      const y = DOT_AREA - ((s.hr - hrMin) / (hrMax - hrMin)) * (DOT_AREA * 0.8) - DOT_AREA * 0.05
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .filter(Boolean)

  const hrPath = hrPts.map((p, i) => (i === 0 ? `M${p}` : `L${p}`)).join(" ")

  return (
    <div>
      <svg
        width="100%"
        height={H}
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        overflow="visible"
      >
        {/* Pace bars */}
        {splits.map((s, i) => {
          if (s.pace_s_per_km === null) return null
          const x = (i / splits.length) * W
          const heightPct = (s.pace_s_per_km - paceMin) / paceRange
          const barHeight = Math.max(4, heightPct * BAR_H + 4)
          return (
            <rect
              key={s.km}
              x={x + 1}
              y={H - barHeight}
              width={barW}
              height={barHeight}
              rx={2}
              fill={paceColor(s.pace_s_per_km)}
              opacity={0.85}
            />
          )
        })}

        {/* HR line */}
        {hrPts.length > 1 && (
          <path
            d={hrPath}
            fill="none"
            stroke="var(--gray-600)"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity={0.7}
            strokeDasharray="200"
            strokeDashoffset="200"
            style={{ animation: "drawStroke 600ms ease-out forwards" }}
          />
        )}

        {/* HR dots */}
        {splits.map((s, i) => {
          if (s.hr === null) return null
          const x = (i / splits.length) * W + barW / 2
          const y = DOT_AREA - ((s.hr - hrMin) / (hrMax - hrMin)) * (DOT_AREA * 0.8) - DOT_AREA * 0.05
          return (
            <circle key={`hr-${s.km}`} cx={x} cy={y} r={2.5} fill="var(--gray-600)" opacity={0.8} />
          )
        })}

        <style>{`@keyframes drawStroke { to { stroke-dashoffset: 0; } }`}</style>
      </svg>

      {/* Legend */}
      <div style={{ display: "flex", gap: 16, marginTop: 6 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <div style={{ width: 10, height: 10, borderRadius: 2, background: "var(--accent)" }} />
          <span style={{ fontSize: "var(--text-xs)", color: "var(--gray-400)" }}>Pace</span>
        </div>
        {hrs.length > 0 && (
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <div style={{ width: 10, height: 2, background: "var(--gray-600)", borderRadius: 1 }} />
            <span style={{ fontSize: "var(--text-xs)", color: "var(--gray-400)" }}>HR</span>
          </div>
        )}
        <div style={{ marginLeft: "auto", display: "flex", gap: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <div style={{ width: 8, height: 8, borderRadius: 2, background: "var(--status-green)" }} />
            <span style={{ fontSize: "var(--text-xs)", color: "var(--gray-400)" }}>Faster</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <div style={{ width: 8, height: 8, borderRadius: 2, background: "var(--status-red)" }} />
            <span style={{ fontSize: "var(--text-xs)", color: "var(--gray-400)" }}>Slower</span>
          </div>
        </div>
      </div>
    </div>
  )
}
