"use client"

import type { SleepPoint } from "@/lib/api"

interface Props {
  data: SleepPoint[]
}

export function SleepSparkline({ data }: Props) {
  const scores = data.map((d) => d.score ?? null)
  const filled = scores.filter((v): v is number => v !== null)

  if (!filled.length) {
    return (
      <div style={{ height: 48, display: "flex", alignItems: "center" }}>
        <span className="body-text" style={{ fontSize: "var(--text-xs)" }}>No data</span>
      </div>
    )
  }

  const latest = filled[filled.length - 1]
  const avg = Math.round(filled.reduce((a, b) => a + b, 0) / filled.length)
  const color = latest >= 75 ? "var(--status-green)" : latest >= 55 ? "var(--status-amber)" : "var(--status-red)"

  const min = 0
  const max = 100
  const W = 100
  const H = 32
  const pts = scores
    .map((v, i) => {
      if (v === null) return null
      const x = (i / (scores.length - 1)) * W
      const y = H - ((v - min) / (max - min)) * H
      return `${x},${y}`
    })
    .filter(Boolean)

  const pathD = pts.map((p, i) => (i === 0 ? `M${p}` : `L${p}`)).join(" ")

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
        <span className="metric-value" style={{ fontSize: "var(--text-lg)", color }}>{latest}</span>
        <span style={{ fontSize: "var(--text-xs)", color: "var(--gray-400)" }}>avg {avg}</span>
      </div>
      <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
        <path
          d={pathD}
          fill="none"
          stroke={color}
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeDasharray={200}
          strokeDashoffset={200}
          style={{ animation: "drawStroke 600ms ease-out forwards" }}
        />
        <style>{`@keyframes drawStroke { to { stroke-dashoffset: 0; } }`}</style>
      </svg>
    </div>
  )
}
