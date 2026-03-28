"use client"

import { useQuery } from "@tanstack/react-query"
import { useParams } from "next/navigation"
import Link from "next/link"
import { format, parseISO } from "date-fns"
import { ChevronLeft } from "lucide-react"
import { api, type HealthDayDetail } from "@/lib/api"
import { PageWrapper } from "@/components/PageWrapper"
import { TabBar } from "@/components/TabBar"

export default function HealthDayPage() {
  const params = useParams()
  const dateStr = params.date as string

  const { data, isLoading } = useQuery({
    queryKey: ["health", "day", dateStr],
    queryFn: () => api.health.day(dateStr),
    enabled: !!dateStr,
  })

  const title = dateStr ? format(parseISO(dateStr), "EEEE d MMMM") : "—"

  return (
    <>
      <TabBar />
      <PageWrapper>
        <div className="container page-content">
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 20 }}>
            <Link href="/dashboard/health" style={{ color: "var(--gray-400)", display: "flex" }}>
              <ChevronLeft size={20} />
            </Link>
            <div>
              <div className="metric-label">Health detail</div>
              <div style={{ fontSize: "var(--text-lg)", fontWeight: 600, color: "var(--gray-900)" }}>{title}</div>
            </div>
          </div>

          {isLoading ? (
            <LoadingSkeleton />
          ) : data ? (
            <DayDetail data={data} />
          ) : (
            <div className="card" style={{ textAlign: "center", padding: "32px 16px" }}>
              <div className="body-text">No data for this date.</div>
            </div>
          )}
        </div>
      </PageWrapper>
    </>
  )
}

function DayDetail({ data }: { data: HealthDayDetail }) {
  return (
    <div className="card-grid">
      {/* Readiness score */}
      {data.readiness_score !== null && (
        <div className="card card-full" style={{ display: "flex", gap: 16, alignItems: "center" }}>
          <ReadinessRing score={data.readiness_score} />
          <div>
            <div className="metric-label" style={{ marginBottom: 4 }}>Readiness</div>
            <div className="metric-value">{Math.round(data.readiness_score)}</div>
            <div style={{ fontSize: "var(--text-sm)", color: "var(--gray-600)", marginTop: 2 }}>
              {data.readiness_label}
            </div>
          </div>
          <div style={{ flex: 1, display: "flex", gap: 16, justifyContent: "flex-end", flexWrap: "wrap" }}>
            <DeltaBadge label="HRV" delta={data.hrv_delta_pct} />
            <DeltaBadge label="Sleep" delta={data.sleep_delta_pct} />
            <DeltaBadge label="Load" delta={data.load_delta_pct} invertColor />
          </div>
        </div>
      )}

      {/* AI brief */}
      {data.ai_summary && (
        <div className="card card-full">
          <div className="card-title" style={{ marginBottom: 8 }}>AI Brief</div>
          <div style={{ fontSize: "var(--text-sm)", color: "var(--gray-600)", lineHeight: 1.7 }}>
            {data.ai_summary.split("\n").filter(Boolean).map((line, i) => (
              <div key={i} style={{ marginBottom: 4 }}>{line}</div>
            ))}
          </div>
        </div>
      )}

      {/* HRV + HR */}
      <div className="card card-half">
        <div className="metric-label" style={{ marginBottom: 12 }}>Heart</div>
        <MetricRow label="HRV (RMSSD)" value={data.hrv_rmssd !== null ? `${data.hrv_rmssd.toFixed(1)} ms` : "—"} />
        <MetricRow label="Resting HR" value={data.resting_hr !== null ? `${data.resting_hr} bpm` : "—"} />
      </div>

      {/* Sleep */}
      <div className="card card-half">
        <div className="metric-label" style={{ marginBottom: 12 }}>Sleep</div>
        <MetricRow label="Score" value={data.sleep_score !== null ? String(data.sleep_score) : "—"} />
        <MetricRow
          label="Duration"
          value={data.sleep_duration_minutes !== null ? formatMinutes(data.sleep_duration_minutes) : "—"}
        />
        <MetricRow
          label="Deep"
          value={data.deep_sleep_minutes !== null ? formatMinutes(data.deep_sleep_minutes) : "—"}
        />
        <MetricRow
          label="REM"
          value={data.rem_sleep_minutes !== null ? formatMinutes(data.rem_sleep_minutes) : "—"}
        />
      </div>

      {/* Body battery + stress */}
      <div className="card card-half">
        <div className="metric-label" style={{ marginBottom: 12 }}>Energy</div>
        <MetricRow label="Body battery" value={data.body_battery_max !== null ? `${data.body_battery_min}–${data.body_battery_max}` : "—"} />
        <MetricRow label="Stress avg" value={data.stress_avg !== null ? String(data.stress_avg) : "—"} />
      </div>

      {/* Other */}
      <div className="card card-half">
        <div className="metric-label" style={{ marginBottom: 12 }}>Other</div>
        <MetricRow label="Steps" value={data.steps !== null ? data.steps.toLocaleString() : "—"} />
        <MetricRow label="SpO₂" value={data.spo2_avg !== null ? `${data.spo2_avg.toFixed(1)}%` : "—"} />
      </div>
    </div>
  )
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
      <span style={{ fontSize: "var(--text-xs)", color: "var(--gray-400)" }}>{label}</span>
      <span style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--gray-900)" }}>{value}</span>
    </div>
  )
}

function DeltaBadge({
  label,
  delta,
  invertColor = false,
}: {
  label: string
  delta: number | null
  invertColor?: boolean
}) {
  if (delta === null) return null
  const positive = invertColor ? delta < 0 : delta > 0
  const color = Math.abs(delta) < 2 ? "var(--gray-400)" : positive ? "var(--status-green)" : "var(--status-red)"
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ fontSize: "var(--text-xs)", color: "var(--gray-400)" }}>{label}</div>
      <div style={{ fontSize: "var(--text-sm)", fontWeight: 700, color }}>
        {delta > 0 ? "+" : ""}{delta.toFixed(1)}%
      </div>
    </div>
  )
}

function ReadinessRing({ score }: { score: number }) {
  const r = 28
  const circ = 2 * Math.PI * r
  const filled = (score / 100) * circ
  const color = score >= 70 ? "var(--status-green)" : score >= 50 ? "var(--status-amber)" : "var(--status-red)"
  return (
    <svg width={72} height={72} viewBox="0 0 72 72" style={{ flexShrink: 0 }}>
      <circle cx={36} cy={36} r={r} fill="none" stroke="var(--gray-200)" strokeWidth={7} />
      <circle
        cx={36} cy={36} r={r} fill="none"
        stroke={color} strokeWidth={7}
        strokeDasharray={`${filled} ${circ}`}
        strokeLinecap="round"
        transform="rotate(-90 36 36)"
      />
    </svg>
  )
}

function formatMinutes(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}

function LoadingSkeleton() {
  return (
    <div className="card-grid">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className={`skeleton card-${i < 2 ? "full" : "half"}`} style={{ height: 100, borderRadius: 16 }} />
      ))}
    </div>
  )
}
