"use client"

import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { format, parseISO, startOfWeek, addDays, subDays } from "date-fns"
import { api } from "@/lib/api"
import { PageWrapper } from "@/components/PageWrapper"
import { TabBar } from "@/components/TabBar"
import type { ReadinessPoint } from "@/lib/api"

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

function scoreColor(score: number): string {
  if (score >= 70) return "var(--status-green)"
  if (score >= 50) return "var(--status-amber)"
  return "var(--status-red)"
}

function scoreBg(score: number | null): string {
  if (score === null) return "var(--gray-100)"
  if (score >= 70) return "#DCFCE7"
  if (score >= 50) return "#FEF3C7"
  return "#FEE2E2"
}

export default function HealthPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["health", "history"],
    queryFn: () => api.health.history(35),
  })

  return (
    <>
      <TabBar />
      <PageWrapper>
        <div className="container page-content">
          <div style={{ marginBottom: 20 }}>
            <div className="metric-label" style={{ marginBottom: 4 }}>Health</div>
            <div style={{ fontSize: "var(--text-xl)", fontWeight: 600, color: "var(--gray-900)" }}>
              Readiness calendar
            </div>
          </div>

          {isLoading ? (
            <div className="skeleton" style={{ height: 260, borderRadius: 16 }} />
          ) : (
            <CalendarHeatmap data={data ?? []} />
          )}

          {/* Score legend */}
          <div style={{ display: "flex", gap: 16, marginTop: 16, paddingLeft: 4 }}>
            {[
              { label: "High (≥70)", bg: "#DCFCE7", color: "var(--status-green)" },
              { label: "OK (50–69)", bg: "#FEF3C7", color: "var(--status-amber)" },
              { label: "Low (<50)", bg: "#FEE2E2", color: "var(--status-red)" },
              { label: "No data", bg: "var(--gray-100)", color: "var(--gray-400)" },
            ].map((item) => (
              <div key={item.label} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <div style={{ width: 10, height: 10, borderRadius: 3, background: item.bg, border: `1.5px solid ${item.color}`, flexShrink: 0 }} />
                <span style={{ fontSize: "var(--text-xs)", color: "var(--gray-400)" }}>{item.label}</span>
              </div>
            ))}
          </div>
        </div>
      </PageWrapper>
    </>
  )
}

function CalendarHeatmap({ data }: { data: ReadinessPoint[] }) {
  const scoreByDate = new Map(data.map((p) => [p.date, p]))

  // Build a 5-week grid ending today
  const today = new Date()
  // Start from Monday 4 weeks + days-since-monday ago
  const todayDow = today.getDay() // 0=Sun, 1=Mon, ...
  const daysSinceMonday = todayDow === 0 ? 6 : todayDow - 1
  const gridEnd = today
  const gridStart = subDays(today, daysSinceMonday + 28) // 5 weeks back, starting on Monday

  const cells: Date[] = []
  let cur = gridStart
  while (cur <= gridEnd) {
    cells.push(new Date(cur))
    cur = addDays(cur, 1)
  }
  // Pad to a full week at the end
  while (cells.length % 7 !== 0) {
    cells.push(addDays(cells[cells.length - 1], 1))
  }

  const weeks: Date[][] = []
  for (let i = 0; i < cells.length; i += 7) {
    weeks.push(cells.slice(i, i + 7))
  }

  const hasAnyData = data.some((p) => p.score !== null)

  if (!hasAnyData) {
    return (
      <div className="card" style={{ textAlign: "center", padding: "32px 16px" }}>
        <div className="body-text">No health data yet.</div>
        <div style={{ fontSize: "var(--text-xs)", color: "var(--gray-400)", marginTop: 8 }}>
          Connect Garmin to see your daily readiness.
        </div>
      </div>
    )
  }

  return (
    <div className="card" style={{ overflowX: "auto" }}>
      {/* Day-of-week header */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 4, marginBottom: 6 }}>
        {DAY_LABELS.map((d) => (
          <div key={d} style={{ textAlign: "center", fontSize: "var(--text-xs)", color: "var(--gray-400)", fontWeight: 600 }}>
            {d}
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      {weeks.map((week, wi) => (
        <div key={wi} style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 4, marginBottom: 4 }}>
          {week.map((day, di) => {
            const dateStr = format(day, "yyyy-MM-dd")
            const point = scoreByDate.get(dateStr)
            const isFuture = day > today
            const isToday = format(day, "yyyy-MM-dd") === format(today, "yyyy-MM-dd")

            const score = point?.score ?? null
            const bg = isFuture ? "transparent" : scoreBg(score)
            const border = isToday ? "2px solid var(--accent)" : score !== null ? `1.5px solid ${scoreColor(score)}` : "1.5px solid var(--gray-200)"

            const cell = (
              <div
                style={{
                  aspectRatio: "1",
                  borderRadius: 8,
                  background: bg,
                  border,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: point && !isFuture ? "pointer" : "default",
                  opacity: isFuture ? 0.25 : 1,
                  transition: "transform 120ms ease",
                }}
              >
                <span style={{ fontSize: "var(--text-xs)", fontWeight: isToday ? 700 : 400, color: score !== null ? scoreColor(score) : "var(--gray-400)" }}>
                  {format(day, "d")}
                </span>
                {score !== null && (
                  <span style={{ fontSize: 9, fontWeight: 600, color: scoreColor(score), lineHeight: 1 }}>
                    {Math.round(score)}
                  </span>
                )}
              </div>
            )

            return (
              <div key={di}>
                {point && !isFuture ? (
                  <Link href={`/dashboard/health/${dateStr}`} style={{ textDecoration: "none", display: "block" }}>
                    {cell}
                  </Link>
                ) : (
                  cell
                )}
              </div>
            )
          })}
        </div>
      ))}
    </div>
  )
}
