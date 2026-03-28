"use client"

import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { format, parseISO } from "date-fns"
import { Activity, TrendingUp } from "lucide-react"
import { api } from "@/lib/api"
import { PageWrapper } from "@/components/PageWrapper"
import { TabBar } from "@/components/TabBar"
import { AIFeatureGate } from "@/components/AIFeatureGate"
import { HRVSparkline } from "@/components/charts/HRVSparkline"
import { SleepSparkline } from "@/components/charts/SleepSparkline"

export default function DashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard"],
    queryFn: api.dashboard,
  })

  return (
    <>
      <TabBar />
      <PageWrapper>
        <div className="container page-content">
          {/* Strava onboarding banner */}
          {data && !data.strava_connected && (
            <div
              style={{
                background: "var(--accent-light)",
                borderRadius: 12,
                padding: "12px 16px",
                marginBottom: 20,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 12,
              }}
            >
              <div>
                <div style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--accent-dim)", marginBottom: 2 }}>
                  Connect Strava
                </div>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--accent-dim)" }}>
                  Link your Strava account to import your activities and start tracking
                </div>
              </div>
              <button
                onClick={async () => {
                  const { url } = await api.auth.stravaUrl()
                  window.location.href = url
                }}
                style={{
                  background: "var(--accent)",
                  color: "white",
                  borderRadius: 8,
                  padding: "8px 14px",
                  fontSize: "var(--text-xs)",
                  fontWeight: 600,
                  border: "none",
                  cursor: "pointer",
                  whiteSpace: "nowrap",
                }}
              >
                Connect →
              </button>
            </div>
          )}

          {/* AI onboarding banner (Phase 1 — no key set) */}
          {data && !data.gemini_connected && (
            <div
              style={{
                background: "var(--accent-light)",
                borderRadius: 12,
                padding: "12px 16px",
                marginBottom: 20,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 12,
              }}
            >
              <div>
                <div style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--accent-dim)", marginBottom: 2 }}>
                  Enable AI coaching
                </div>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--accent-dim)" }}>
                  Add your free Gemini API key to unlock daily briefs and plan generation
                </div>
              </div>
              <Link
                href="/dashboard/settings#ai"
                style={{
                  background: "var(--accent)",
                  color: "white",
                  borderRadius: 8,
                  padding: "8px 14px",
                  fontSize: "var(--text-xs)",
                  fontWeight: 600,
                  textDecoration: "none",
                  whiteSpace: "nowrap",
                }}
              >
                Set up →
              </Link>
            </div>
          )}

          <div className="card-grid">
            {/* Weekly mileage */}
            <div className="card card-full">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
                <div>
                  <div className="metric-label" style={{ marginBottom: 4 }}>This week</div>
                  {isLoading ? (
                    <div className="skeleton" style={{ height: 36, width: 100 }} />
                  ) : (
                    <div className="metric-value">{data?.weekly_mileage.current_km ?? 0} km</div>
                  )}
                </div>
                <div style={{ textAlign: "right" }}>
                  <div className="metric-label" style={{ marginBottom: 4 }}>Runs</div>
                  <div className="metric-value" style={{ fontSize: "var(--text-xl)" }}>
                    {isLoading ? "—" : data?.weekly_mileage.run_count ?? 0}
                  </div>
                </div>
              </div>

              {/* Day bars */}
              {data && (
                <DayBars dailyRuns={data.weekly_mileage.daily_runs} />
              )}
            </div>

            {/* HRV sparkline */}
            <div className="card card-half">
              <div className="metric-label" style={{ marginBottom: 8 }}>HRV 14-day</div>
              {isLoading ? (
                <div className="skeleton" style={{ height: 48 }} />
              ) : (
                <HRVSparkline data={data?.hrv_trend ?? []} />
              )}
            </div>

            {/* Sleep sparkline */}
            <div className="card card-half">
              <div className="metric-label" style={{ marginBottom: 8 }}>Sleep 14-day</div>
              {isLoading ? (
                <div className="skeleton" style={{ height: 48 }} />
              ) : (
                <SleepSparkline data={data?.sleep_trend ?? []} />
              )}
            </div>

            {/* AI brief gate */}
            <div className="card-full">
              <AIFeatureGate>
                <div className="card">
                  <div className="card-title" style={{ marginBottom: 8 }}>AI Daily Brief</div>
                  <div className="body-text">
                    {data?.ai_brief ?? "Brief will appear after your next sync."}
                  </div>
                </div>
              </AIFeatureGate>
            </div>

            {/* Recent activities */}
            <div className="card card-full">
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 16,
                }}
              >
                <div className="card-title">Recent activities</div>
                <Link
                  href="/dashboard/activities"
                  style={{ fontSize: "var(--text-xs)", color: "var(--accent)", textDecoration: "none", fontWeight: 600 }}
                >
                  See all
                </Link>
              </div>

              {isLoading ? (
                Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="skeleton" style={{ height: 52, marginBottom: 8, borderRadius: 10 }} />
                ))
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  {data?.recent_activities.map((a) => (
                    <Link
                      key={a.id}
                      href={`/dashboard/activities/${a.id}`}
                      style={{ textDecoration: "none" }}
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 12,
                          padding: "10px 0",
                          borderBottom: "1px solid var(--gray-100)",
                        }}
                      >
                        <div
                          style={{
                            width: 36, height: 36,
                            borderRadius: 10,
                            background: "var(--accent-light)",
                            display: "flex", alignItems: "center", justifyContent: "center",
                          }}
                        >
                          <Activity size={16} color="var(--accent)" />
                        </div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--gray-900)" }}>
                            {a.distance_km ? `${a.distance_km} km` : "—"}
                            {a.workout_type && (
                              <span style={{ marginLeft: 8, fontWeight: 400, color: "var(--gray-400)" }}>
                                {a.workout_type.replace("_", " ")}
                              </span>
                            )}
                          </div>
                          <div style={{ fontSize: "var(--text-xs)", color: "var(--gray-400)" }}>
                            {a.pace_str && `${a.pace_str}/km`}
                            {a.avg_hr && ` · ${a.avg_hr} bpm`}
                          </div>
                        </div>
                        <div style={{ fontSize: "var(--text-xs)", color: "var(--gray-400)", textAlign: "right" }}>
                          {a.started_at ? format(parseISO(a.started_at), "d MMM") : ""}
                        </div>
                      </div>
                    </Link>
                  ))}
                  {!data?.recent_activities.length && (
                    <div className="body-text" style={{ textAlign: "center", padding: "24px 0" }}>
                      No activities yet — connect Strava to import your runs.
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </PageWrapper>
    </>
  )
}

function DayBars({ dailyRuns }: { dailyRuns: number[] }) {
  const labels = ["M", "T", "W", "T", "F", "S", "S"]
  const max = Math.max(...dailyRuns, 1)

  return (
    <div style={{ display: "flex", gap: 6, alignItems: "flex-end", height: 40 }}>
      {dailyRuns.map((km, i) => (
        <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
          <div
            style={{
              width: "100%",
              height: km > 0 ? `${Math.round((km / max) * 28)}px` : 4,
              background: km > 0 ? "var(--accent)" : "var(--gray-200)",
              borderRadius: 3,
              transition: "height 700ms ease",
              minHeight: 4,
            }}
          />
          <span style={{ fontSize: "var(--text-xs)", color: "var(--gray-400)" }}>{labels[i]}</span>
        </div>
      ))}
    </div>
  )
}
