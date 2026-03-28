"use client"

import { useParams, useRouter } from "next/navigation"
import { useQuery } from "@tanstack/react-query"
import { format, parseISO } from "date-fns"
import { ArrowLeft, MapPin, Zap, Heart, Clock, TrendingUp } from "lucide-react"
import { api } from "@/lib/api"
import { PageWrapper } from "@/components/PageWrapper"
import { TabBar } from "@/components/TabBar"

const HR_ZONE_COLORS = ["#93C5FD", "#6EE7B7", "#FCD34D", "#F97316", "#EF4444"]
const HR_ZONE_LABELS = ["Zone 1", "Zone 2", "Zone 3", "Zone 4", "Zone 5"]

export default function ActivityDetailPage() {
  const { id } = useParams()
  const router = useRouter()

  const { data: activity, isLoading } = useQuery({
    queryKey: ["activity", id],
    queryFn: () => api.activities.get(id as string),
  })

  if (isLoading) {
    return (
      <>
        <TabBar />
        <div className="container page-content">
          <div className="skeleton" style={{ height: 200, borderRadius: 16 }} />
        </div>
      </>
    )
  }

  if (!activity) return null

  const zones = activity.hr_zone_distribution
    ? Object.entries(activity.hr_zone_distribution).map(([k, v]) => ({ label: k.toUpperCase(), pct: v }))
    : null

  return (
    <>
      <TabBar />
      <PageWrapper>
        <div className="container page-content">
          {/* Back nav */}
          <button
            onClick={() => router.back()}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "var(--gray-600)",
              fontSize: "var(--text-sm)",
              padding: "0 0 16px 0",
            }}
          >
            <ArrowLeft size={16} /> Back
          </button>

          {/* Header */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
              {activity.workout_type && (
                <span
                  style={{
                    fontSize: "var(--text-xs)",
                    fontWeight: 600,
                    textTransform: "capitalize",
                    color: "var(--accent)",
                    background: "var(--accent-light)",
                    padding: "3px 8px",
                    borderRadius: 6,
                  }}
                >
                  {activity.workout_type.replace("_", " ")}
                </span>
              )}
              <span style={{ fontSize: "var(--text-xs)", color: "var(--gray-400)" }}>
                {activity.started_at ? format(parseISO(activity.started_at), "EEEE, d MMMM yyyy") : ""}
              </span>
            </div>
            <div style={{ fontSize: "var(--text-xl)", fontWeight: 600, color: "var(--gray-900)" }}>
              {activity.distance_km ? `${activity.distance_km} km Run` : "Run"}
            </div>
          </div>

          {/* Key stats grid */}
          <div className="card card-full" style={{ marginBottom: 12 }}>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, 1fr)",
                gap: 16,
              }}
            >
              <StatBlock label="Distance" value={activity.distance_km ? `${activity.distance_km}` : "—"} unit="km" />
              <StatBlock label="Time" value={activity.duration_str ?? "—"} />
              <StatBlock label="Avg Pace" value={activity.pace_str ?? "—"} unit="/km" />
              {activity.avg_hr && <StatBlock label="Avg HR" value={String(activity.avg_hr)} unit="bpm" />}
              {activity.max_hr && <StatBlock label="Max HR" value={String(activity.max_hr)} unit="bpm" />}
              {activity.elevation_gain_m && (
                <StatBlock label="Elevation" value={String(Math.round(activity.elevation_gain_m))} unit="m" />
              )}
              {activity.avg_cadence && <StatBlock label="Cadence" value={String(activity.avg_cadence)} unit="spm" />}
              {activity.avg_power && <StatBlock label="Power" value={String(activity.avg_power)} unit="W" />}
            </div>
          </div>

          {/* HR Zone distribution */}
          {zones && (
            <div className="card" style={{ marginBottom: 12 }}>
              <div className="card-title" style={{ marginBottom: 16 }}>HR Zone Distribution</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {zones.map((z, i) => (
                  <div key={z.label} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ fontSize: "var(--text-xs)", color: "var(--gray-600)", width: 44 }}>{HR_ZONE_LABELS[i]}</span>
                    <div style={{ flex: 1, background: "var(--gray-100)", borderRadius: 4, height: 8, overflow: "hidden" }}>
                      <div
                        style={{
                          height: "100%",
                          width: `${Math.round(z.pct * 100)}%`,
                          background: HR_ZONE_COLORS[i],
                          borderRadius: 4,
                          animation: "barFill 700ms ease-out forwards",
                        }}
                      />
                    </div>
                    <span style={{ fontSize: "var(--text-xs)", color: "var(--gray-600)", width: 36, textAlign: "right" }}>
                      {Math.round(z.pct * 100)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Splits table */}
          {activity.splits && activity.splits.length > 0 && (
            <div className="card" style={{ marginBottom: 12 }}>
              <div className="card-title" style={{ marginBottom: 12 }}>Per-km Splits</div>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr>
                    {["km", "Pace", "HR"].map((h) => (
                      <th
                        key={h}
                        style={{
                          fontSize: "var(--text-xs)",
                          fontWeight: 400,
                          color: "var(--gray-400)",
                          textTransform: "uppercase",
                          letterSpacing: "0.06em",
                          textAlign: h === "km" ? "left" : "right",
                          paddingBottom: 8,
                        }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {activity.splits.map((s) => {
                    const paceStr = s.pace_s_per_km
                      ? `${Math.floor(s.pace_s_per_km / 60)}:${String(Math.round(s.pace_s_per_km % 60)).padStart(2, "0")}`
                      : "—"
                    return (
                      <tr key={s.km} style={{ borderTop: "1px solid var(--gray-100)" }}>
                        <td style={{ padding: "8px 0", fontSize: "var(--text-sm)", color: "var(--gray-600)" }}>
                          {s.km}
                        </td>
                        <td style={{ padding: "8px 0", fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--gray-900)", textAlign: "right" }}>
                          {paceStr}
                        </td>
                        <td style={{ padding: "8px 0", fontSize: "var(--text-sm)", color: "var(--gray-600)", textAlign: "right" }}>
                          {s.hr ?? "—"}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Notes */}
          {activity.notes && (
            <div className="card" style={{ marginBottom: 12 }}>
              <div className="card-title" style={{ marginBottom: 8 }}>Notes</div>
              <div className="body-text">{activity.notes}</div>
            </div>
          )}
        </div>
      </PageWrapper>
    </>
  )
}

function StatBlock({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div>
      <div className="metric-label" style={{ marginBottom: 2 }}>{label}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 2 }}>
        <span className="metric-value" style={{ fontSize: "var(--text-xl)" }}>{value}</span>
        {unit && <span style={{ fontSize: "var(--text-xs)", color: "var(--gray-400)" }}>{unit}</span>}
      </div>
    </div>
  )
}
