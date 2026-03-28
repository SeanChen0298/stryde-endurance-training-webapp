"use client"

import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { format, parseISO } from "date-fns"
import { api } from "@/lib/api"
import { PageWrapper } from "@/components/PageWrapper"
import { TabBar } from "@/components/TabBar"

export default function HealthPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["health", "history"],
    queryFn: () => api.health.history(30),
  })

  const entries = data ? [...data].reverse() : []

  return (
    <>
      <TabBar />
      <PageWrapper>
        <div className="container page-content">
          <div style={{ marginBottom: 20 }}>
            <div className="metric-label" style={{ marginBottom: 4 }}>Health</div>
            <div style={{ fontSize: "var(--text-xl)", fontWeight: 600, color: "var(--gray-900)" }}>
              30-day readiness
            </div>
          </div>

          {isLoading ? (
            Array.from({ length: 7 }).map((_, i) => (
              <div key={i} className="skeleton" style={{ height: 64, borderRadius: 12, marginBottom: 8 }} />
            ))
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {entries.map((point) => (
                <Link
                  key={point.date}
                  href={`/dashboard/health/${point.date}`}
                  style={{ textDecoration: "none" }}
                >
                  <div
                    className="card"
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 14,
                      padding: "12px 16px",
                      borderRadius: 12,
                    }}
                  >
                    <ScoreDot score={point.score} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--gray-900)" }}>
                        {format(parseISO(point.date), "EEE d MMM")}
                      </div>
                      <div style={{ fontSize: "var(--text-xs)", color: "var(--gray-400)", marginTop: 1 }}>
                        {point.label ?? "No data"}
                      </div>
                    </div>
                    {point.score !== null && (
                      <div
                        style={{
                          fontSize: "var(--text-lg)",
                          fontWeight: 700,
                          color: scoreColor(point.score),
                          minWidth: 36,
                          textAlign: "right",
                        }}
                      >
                        {Math.round(point.score)}
                      </div>
                    )}
                  </div>
                </Link>
              ))}
              {entries.every((p) => p.score === null) && (
                <div className="card" style={{ textAlign: "center", padding: "32px 16px" }}>
                  <div className="body-text">No health data yet.</div>
                  <div style={{ fontSize: "var(--text-xs)", color: "var(--gray-400)", marginTop: 8 }}>
                    Connect Garmin or add HRV data to see your daily readiness.
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </PageWrapper>
    </>
  )
}

function scoreColor(score: number): string {
  if (score >= 70) return "var(--status-green)"
  if (score >= 50) return "var(--status-amber)"
  return "var(--status-red)"
}

function ScoreDot({ score }: { score: number | null }) {
  const color = score !== null ? scoreColor(score) : "var(--gray-200)"
  return (
    <div
      style={{
        width: 12,
        height: 12,
        borderRadius: "50%",
        background: color,
        flexShrink: 0,
      }}
    />
  )
}
