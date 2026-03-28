"use client"

import { useState } from "react"
import Link from "next/link"
import { format, parseISO } from "date-fns"
import { useQuery } from "@tanstack/react-query"
import { ChevronRight, Activity } from "lucide-react"
import { api } from "@/lib/api"
import { PageWrapper } from "@/components/PageWrapper"
import { TabBar } from "@/components/TabBar"

const FILTERS = [
  { label: "All",        workout_type: undefined },
  { label: "Easy",       workout_type: "easy" },
  { label: "Tempo",      workout_type: "tempo" },
  { label: "Long run",   workout_type: "long_run" },
  { label: "Intervals",  workout_type: "interval" },
  { label: "Race",       workout_type: "race" },
]

const WORKOUT_COLORS: Record<string, string> = {
  easy:     "#DCFCE7",
  tempo:    "#FEF3C7",
  long_run: "#DBEAFE",
  interval: "#FAE8FF",
  race:     "#FEE2E2",
}

const WORKOUT_TEXT: Record<string, string> = {
  easy:     "#15803D",
  tempo:    "#92400E",
  long_run: "#1E40AF",
  interval: "#6B21A8",
  race:     "#991B1B",
}

export default function ActivitiesPage() {
  const [activeFilter, setActiveFilter] = useState(0)
  const [page, setPage] = useState(1)

  const filter = FILTERS[activeFilter]
  const { data, isLoading } = useQuery({
    queryKey: ["activities", activeFilter, page],
    queryFn: () => api.activities.list({ page, per_page: 20, workout_type: filter.workout_type }),
  })

  const { data: summary } = useQuery({
    queryKey: ["activities", "monthly-summary"],
    queryFn: () => api.activities.monthlySummary(),
  })

  return (
    <>
      <TabBar />
      <PageWrapper>
        <div className="container page-content">
          <h1 style={{ fontSize: "var(--text-xl)", fontWeight: 600, marginBottom: 20, marginTop: 0 }}>
            Activities
          </h1>

          {/* Monthly summary */}
          {summary && (
            <div
              className="card card-full"
              style={{ display: "flex", gap: 24, marginBottom: 20 }}
            >
              <Stat label="This month" value={`${summary.total_km} km`} />
              <Stat label="Runs" value={String(summary.total_runs)} />
              {summary.avg_hr && <Stat label="Avg HR" value={`${Math.round(summary.avg_hr)} bpm`} />}
            </div>
          )}

          {/* Filter chips */}
          <div
            style={{
              display: "flex",
              gap: 8,
              overflowX: "auto",
              paddingBottom: 4,
              marginBottom: 16,
              scrollbarWidth: "none",
            }}
          >
            {FILTERS.map((f, i) => (
              <button
                key={f.label}
                onClick={() => { setActiveFilter(i); setPage(1) }}
                style={{
                  flexShrink: 0,
                  background: i === activeFilter ? "var(--accent)" : "var(--gray-100)",
                  color: i === activeFilter ? "white" : "var(--gray-600)",
                  border: "none",
                  borderRadius: 20,
                  padding: "7px 14px",
                  fontSize: "var(--text-sm)",
                  fontWeight: i === activeFilter ? 600 : 400,
                  cursor: "pointer",
                  transition: "all 150ms ease",
                }}
              >
                {f.label}
              </button>
            ))}
          </div>

          {/* Activity list */}
          {isLoading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="skeleton" style={{ height: 80, borderRadius: 16, marginBottom: 10 }} />
            ))
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {data?.items.map((a) => {
                const wt = a.workout_type ?? "easy"
                return (
                  <Link
                    key={a.id}
                    href={`/dashboard/activities/${a.id}`}
                    style={{ textDecoration: "none" }}
                  >
                    <div className="card" style={{ display: "flex", alignItems: "center", gap: 14 }}>
                      <div
                        style={{
                          width: 44, height: 44, borderRadius: 12,
                          background: WORKOUT_COLORS[wt] ?? "var(--gray-100)",
                          display: "flex", alignItems: "center", justifyContent: "center",
                          flexShrink: 0,
                        }}
                      >
                        <Activity size={20} color={WORKOUT_TEXT[wt] ?? "var(--gray-600)"} />
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                          <span style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--gray-900)" }}>
                            {a.distance_km ? `${a.distance_km} km` : "—"}
                          </span>
                          {a.workout_type && (
                            <span
                              style={{
                                background: WORKOUT_COLORS[a.workout_type] ?? "var(--gray-100)",
                                color: WORKOUT_TEXT[a.workout_type] ?? "var(--gray-600)",
                                fontSize: "var(--text-xs)",
                                fontWeight: 600,
                                padding: "2px 7px",
                                borderRadius: 5,
                                textTransform: "capitalize",
                              }}
                            >
                              {a.workout_type.replace("_", " ")}
                            </span>
                          )}
                        </div>
                        <div style={{ fontSize: "var(--text-xs)", color: "var(--gray-400)" }}>
                          {[
                            a.pace_str && `${a.pace_str}/km`,
                            a.avg_hr && `${a.avg_hr} bpm`,
                            a.duration_str,
                          ]
                            .filter(Boolean)
                            .join("  ·  ")}
                        </div>
                      </div>
                      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
                        <span style={{ fontSize: "var(--text-xs)", color: "var(--gray-400)" }}>
                          {a.started_at ? format(parseISO(a.started_at), "d MMM") : ""}
                        </span>
                        <ChevronRight size={14} color="var(--gray-400)" />
                      </div>
                    </div>
                  </Link>
                )
              })}

              {data?.items.length === 0 && (
                <div className="body-text" style={{ textAlign: "center", padding: "40px 0" }}>
                  No activities found.
                </div>
              )}
            </div>
          )}

          {/* Load more */}
          {data && data.total > page * 20 && (
            <button
              className="btn-secondary"
              style={{ marginTop: 16, width: "100%" }}
              onClick={() => setPage((p) => p + 1)}
            >
              Load more
            </button>
          )}
        </div>
      </PageWrapper>
    </>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="metric-label" style={{ marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: "var(--text-lg)", fontWeight: 600, color: "var(--gray-900)" }}>{value}</div>
    </div>
  )
}
