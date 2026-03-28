"use client"

import { useEffect, useRef } from "react"
import type { HRVPoint } from "@/lib/api"

interface Props {
  data: HRVPoint[]
}

export function HRVSparkline({ data }: Props) {
  const pathRef = useRef<SVGPathElement>(null)

  const values = data.map((d) => d.value ?? null)
  const filled = values.filter((v): v is number => v !== null)

  if (!filled.length) {
    return (
      <div style={{ height: 48, display: "flex", alignItems: "center" }}>
        <span className="body-text" style={{ fontSize: "var(--text-xs)" }}>No data</span>
      </div>
    )
  }

  const latest = filled[filled.length - 1]
  const prev = filled[filled.length - 2]
  const delta = prev ? ((latest - prev) / prev * 100).toFixed(0) : null
  const up = delta !== null && Number(delta) >= 0

  const min = Math.min(...filled)
  const max = Math.max(...filled)
  const range = max - min || 1

  const W = 100
  const H = 32
  const pts = values
    .map((v, i) => {
      if (v === null) return null
      const x = (i / (values.length - 1)) * W
      const y = H - ((v - min) / range) * H
      return `${x},${y}`
    })
    .filter(Boolean)

  const pathD = pts.map((p, i) => (i === 0 ? `M${p}` : `L${p}`)).join(" ")

  // Stroke-dashoffset animation on mount
  const pathLength = 200

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
        <span className="metric-value" style={{ fontSize: "var(--text-lg)" }}>{latest}<span style={{ fontSize: "var(--text-xs)", fontWeight: 400, color: "var(--gray-400)", marginLeft: 2 }}>ms</span></span>
        {delta !== null && (
          <span style={{ fontSize: "var(--text-xs)", color: up ? "var(--status-green)" : "var(--status-red)" }}>
            {up ? "↑" : "↓"} {Math.abs(Number(delta))}%
          </span>
        )}
      </div>
      <svg
        width="100%"
        height={H}
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
      >
        <path
          ref={pathRef}
          d={pathD}
          fill="none"
          stroke="var(--accent)"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeDasharray={pathLength}
          strokeDashoffset={pathLength}
          style={{
            animation: "drawStroke 600ms ease-out forwards",
          }}
        />
        {/* Today dot */}
        {pts[pts.length - 1] && (
          <circle
            cx={(values.length - 1) / (values.length - 1) * W}
            cy={H - ((latest - min) / range) * H}
            r="2.5"
            fill="var(--accent)"
          />
        )}
        <style>{`
          @keyframes drawStroke {
            to { stroke-dashoffset: 0; }
          }
        `}</style>
      </svg>
    </div>
  )
}
