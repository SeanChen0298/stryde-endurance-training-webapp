"use client"

import type { LoadPoint } from "@/lib/api"

interface Props {
  data: LoadPoint[]
}

export function LoadTrendChart({ data }: Props) {
  if (!data.length) {
    return (
      <div style={{ height: 80, display: "flex", alignItems: "center" }}>
        <span className="body-text" style={{ fontSize: "var(--text-xs)" }}>No run data yet</span>
      </div>
    )
  }

  const W = 300
  const H = 64
  const LINE_PAD = 8  // vertical padding so lines don't clip

  const latest = data[data.length - 1]
  const tsb = latest.tsb
  const tsbColor = tsb > 5 ? "var(--status-green)" : tsb < -10 ? "var(--status-red)" : "var(--status-amber)"

  // Scales
  const maxDist = Math.max(...data.map((d) => d.distance_km), 1)
  const maxLine = Math.max(...data.map((d) => Math.max(d.ctl, d.atl)), 1)

  function barH(km: number) {
    return Math.max(2, (km / maxDist) * (H * 0.5))
  }

  function lineY(val: number) {
    return H - LINE_PAD - ((val / maxLine) * (H - LINE_PAD * 2))
  }

  const barW = Math.max(1, W / data.length - 1)

  // Build CTL and ATL SVG paths
  const ctlPts = data.map((d, i) => {
    const x = (i / (data.length - 1)) * W
    const y = lineY(d.ctl)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  const atlPts = data.map((d, i) => {
    const x = (i / (data.length - 1)) * W
    const y = lineY(d.atl)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })

  const ctlPath = ctlPts.map((p, i) => (i === 0 ? `M${p}` : `L${p}`)).join(" ")
  const atlPath = atlPts.map((p, i) => (i === 0 ? `M${p}` : `L${p}`)).join(" ")

  return (
    <div>
      {/* Header row */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
        <div style={{ display: "flex", gap: 16 }}>
          <div>
            <span className="metric-value" style={{ fontSize: "var(--text-lg)" }}>{latest.ctl}</span>
            <span style={{ fontSize: "var(--text-xs)", color: "var(--gray-400)", marginLeft: 2 }}>CTL</span>
          </div>
          <div>
            <span className="metric-value" style={{ fontSize: "var(--text-lg)" }}>{latest.atl}</span>
            <span style={{ fontSize: "var(--text-xs)", color: "var(--gray-400)", marginLeft: 2 }}>ATL</span>
          </div>
        </div>
        <div style={{
          fontSize: "var(--text-xs)", fontWeight: 600, color: tsbColor,
          background: tsb > 5 ? "#DCFCE7" : tsb < -10 ? "#FEE2E2" : "#FEF3C7",
          padding: "2px 8px", borderRadius: 6,
        }}>
          {tsb > 0 ? "+" : ""}{tsb} TSB
        </div>
      </div>

      <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" overflow="visible">
        {/* Daily distance bars */}
        {data.map((d, i) => (
          <rect
            key={d.date}
            x={(i / data.length) * W}
            y={H - barH(d.distance_km)}
            width={barW}
            height={barH(d.distance_km)}
            rx={1}
            fill="var(--gray-200)"
          />
        ))}

        {/* ATL line (acute — more reactive, shown with accent) */}
        <path
          d={atlPath}
          fill="none"
          stroke="var(--accent)"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeDasharray="500"
          strokeDashoffset="500"
          style={{ animation: "drawStroke 700ms ease-out forwards" }}
        />

        {/* CTL line (chronic — slower, shown in gray) */}
        <path
          d={ctlPath}
          fill="none"
          stroke="var(--gray-600)"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeDasharray="500"
          strokeDashoffset="500"
          style={{ animation: "drawStroke 900ms ease-out forwards" }}
        />

        {/* End dots */}
        <circle cx={W} cy={lineY(latest.ctl)} r={2.5} fill="var(--gray-600)" />
        <circle cx={W} cy={lineY(latest.atl)} r={2.5} fill="var(--accent)" />

        <style>{`@keyframes drawStroke { to { stroke-dashoffset: 0; } }`}</style>
      </svg>

      {/* Legend */}
      <div style={{ display: "flex", gap: 14, marginTop: 6 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <div style={{ width: 12, height: 2, background: "var(--gray-600)", borderRadius: 1 }} />
          <span style={{ fontSize: "var(--text-xs)", color: "var(--gray-400)" }}>Fitness (CTL)</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <div style={{ width: 12, height: 2, background: "var(--accent)", borderRadius: 1 }} />
          <span style={{ fontSize: "var(--text-xs)", color: "var(--gray-400)" }}>Fatigue (ATL)</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <div style={{ width: 10, height: 8, borderRadius: 2, background: "var(--gray-200)" }} />
          <span style={{ fontSize: "var(--text-xs)", color: "var(--gray-400)" }}>Daily km</span>
        </div>
      </div>
    </div>
  )
}
