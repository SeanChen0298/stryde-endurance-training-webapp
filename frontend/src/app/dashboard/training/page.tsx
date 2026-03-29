"use client"

import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { ChevronLeft, ChevronRight, Check, Calendar } from "lucide-react"
import Link from "next/link"
import { api, type PlannedWorkoutOut, type ActivitySummaryOut } from "@/lib/api"
import { PageWrapper } from "@/components/PageWrapper"

// ── Workout type colours ──────────────────────────────────────────────────────

const WORKOUT_COLORS: Record<string, string> = {
  easy:     "var(--status-green)",
  long_run: "var(--accent)",
  tempo:    "var(--status-amber)",
  interval: "var(--status-red)",
  race:     "#8B5CF6",
  rest:     "var(--gray-300)",
}

const WORKOUT_LABELS: Record<string, string> = {
  easy:     "Easy",
  long_run: "Long Run",
  tempo:    "Tempo",
  interval: "Interval",
  race:     "Race",
  rest:     "Rest",
}

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
const MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

// ── Helper: Monday of the week containing d ──────────────────────────────────

function getMondayOf(d: Date): Date {
  const day = d.getDay() // 0=Sun
  const diff = day === 0 ? -6 : 1 - day
  const m = new Date(d)
  m.setDate(d.getDate() + diff)
  m.setHours(0, 0, 0, 0)
  return m
}

function toISO(d: Date): string {
  return d.toISOString().split("T")[0]
}

function fmtDistance(meters: number | null): string {
  if (!meters) return ""
  return `${(meters / 1000).toFixed(1)} km`
}

function fmtPace(s: number | null): string {
  if (!s) return ""
  const m = Math.floor(s / 60)
  const sec = Math.round(s % 60)
  return `${m}:${sec.toString().padStart(2, "0")}/km`
}

// ── WorkoutChip ───────────────────────────────────────────────────────────────

function WorkoutChip({ workout, compact = false }: { workout: PlannedWorkoutOut; compact?: boolean }) {
  const color = WORKOUT_COLORS[workout.workout_type] ?? "var(--gray-400)"
  const label = WORKOUT_LABELS[workout.workout_type] ?? workout.workout_type

  if (compact) {
    return (
      <div style={{
        width: 8, height: 8, borderRadius: "50%",
        background: workout.completed ? color : "transparent",
        border: `2px solid ${color}`,
        display: "inline-block",
      }} />
    )
  }

  return (
    <div style={{
      background: color + "22",
      border: `1.5px solid ${color}`,
      borderRadius: 8,
      padding: "4px 8px",
      display: "inline-flex",
      alignItems: "center",
      gap: 5,
    }}>
      {workout.completed && <Check size={11} color={color} strokeWidth={2.5} />}
      <span style={{ fontSize: "var(--text-xs)", color, fontWeight: 600 }}>{label}</span>
      {workout.target_distance_meters && (
        <span style={{ fontSize: "var(--text-xs)", color: "var(--gray-600)" }}>
          {fmtDistance(workout.target_distance_meters)}
        </span>
      )}
    </div>
  )
}

// ── Week view ─────────────────────────────────────────────────────────────────

function WeekView({ weekStart }: { weekStart: Date }) {
  const [expanded, setExpanded] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ["plans", "week", toISO(weekStart)],
    queryFn: () => api.plans.week(toISO(weekStart)),
  })

  const completeMutation = useMutation({
    mutationFn: (workoutId: string) => api.plans.completeWorkout(workoutId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["plans", "week", toISO(weekStart)] })
    },
  })

  if (isLoading) {
    return (
      <div>
        {Array.from({ length: 7 }).map((_, i) => (
          <div key={i} className="skeleton" style={{ height: 56, marginBottom: 8, borderRadius: 12 }} />
        ))}
      </div>
    )
  }

  if (!data?.days?.length) {
    return (
      <div style={{ textAlign: "center", padding: "40px 0", color: "var(--gray-400)" }}>
        <Calendar size={32} strokeWidth={1.5} style={{ margin: "0 auto 12px" }} />
        <p className="body-text">No plan yet for this week.</p>
        <Link href="/dashboard/training/plan" style={{ color: "var(--accent)", fontSize: "var(--text-sm)" }}>
          Generate a training plan →
        </Link>
      </div>
    )
  }

  return (
    <div>
      {data.days.map((day) => {
        const isToday = day.date === toISO(new Date())
        const isExpanded = expanded === day.date
        const pw = day.planned
        const act = day.actual

        return (
          <div
            key={day.date}
            style={{
              marginBottom: 8,
              borderRadius: 12,
              border: isToday ? "1.5px solid var(--accent)" : "1.5px solid var(--gray-100)",
              background: isToday ? "var(--accent-light)" + "33" : "var(--gray-0)",
              overflow: "hidden",
            }}
          >
            {/* Row header */}
            <div
              style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 12px", cursor: pw ? "pointer" : "default" }}
              onClick={() => pw && setExpanded(isExpanded ? null : day.date)}
            >
              {/* Day label */}
              <div style={{ width: 40, flexShrink: 0 }}>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--gray-400)", fontWeight: 500 }}>
                  {DAY_NAMES[new Date(day.date + "T00:00:00").getDay() === 0 ? 6 : new Date(day.date + "T00:00:00").getDay() - 1]}
                </div>
                <div style={{
                  fontSize: "var(--text-sm)", fontWeight: isToday ? 700 : 500,
                  color: isToday ? "var(--accent)" : "var(--gray-900)"
                }}>
                  {new Date(day.date + "T00:00:00").getDate()}
                </div>
              </div>

              {/* Planned */}
              <div style={{ flex: 1 }}>
                {pw ? <WorkoutChip workout={pw} /> : (
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--gray-300)" }}>—</span>
                )}
              </div>

              {/* Actual */}
              {act && (
                <div style={{
                  fontSize: "var(--text-xs)", color: "var(--gray-600)",
                  background: "var(--gray-100)", borderRadius: 6, padding: "3px 7px",
                }}>
                  ✓ {act.distance_km?.toFixed(1)} km {act.pace_str ? `@ ${act.pace_str}` : ""}
                </div>
              )}
            </div>

            {/* Expanded detail */}
            {isExpanded && pw && (
              <div style={{ padding: "0 12px 12px", borderTop: "1px solid var(--gray-100)" }}>
                {pw.description && (
                  <p className="body-text" style={{ marginTop: 10, marginBottom: 8 }}>{pw.description}</p>
                )}
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
                  {pw.target_distance_meters && (
                    <span style={{ fontSize: "var(--text-xs)", background: "var(--gray-100)", padding: "3px 8px", borderRadius: 6 }}>
                      {fmtDistance(pw.target_distance_meters)}
                    </span>
                  )}
                  {pw.target_duration_minutes && (
                    <span style={{ fontSize: "var(--text-xs)", background: "var(--gray-100)", padding: "3px 8px", borderRadius: 6 }}>
                      {pw.target_duration_minutes} min
                    </span>
                  )}
                  {pw.target_pace_min_seconds_per_km && pw.target_pace_max_seconds_per_km && (
                    <span style={{ fontSize: "var(--text-xs)", background: "var(--gray-100)", padding: "3px 8px", borderRadius: 6 }}>
                      {fmtPace(pw.target_pace_min_seconds_per_km)}–{fmtPace(pw.target_pace_max_seconds_per_km)}
                    </span>
                  )}
                  {pw.target_hr_zone && (
                    <span style={{ fontSize: "var(--text-xs)", background: "var(--gray-100)", padding: "3px 8px", borderRadius: 6 }}>
                      Zone {pw.target_hr_zone}
                    </span>
                  )}
                  {pw.target_rpe && (
                    <span style={{ fontSize: "var(--text-xs)", background: "var(--gray-100)", padding: "3px 8px", borderRadius: 6 }}>
                      RPE {pw.target_rpe}/10
                    </span>
                  )}
                </div>
                {!pw.completed && (
                  <button
                    className="btn-secondary"
                    style={{ fontSize: "var(--text-xs)", padding: "6px 12px", display: "flex", alignItems: "center", gap: 5 }}
                    onClick={() => completeMutation.mutate(pw.id)}
                    disabled={completeMutation.isPending}
                  >
                    <Check size={12} /> Mark complete
                  </button>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── Month view ────────────────────────────────────────────────────────────────

function MonthView({ year, month }: { year: number; month: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ["plans", "month", year, month],
    queryFn: () => api.plans.month(year, month),
  })

  const today = toISO(new Date())

  if (isLoading) {
    return <div className="skeleton" style={{ height: 240, borderRadius: 12 }} />
  }

  // Build date → workout map
  const workoutMap: Record<string, PlannedWorkoutOut> = {}
  for (const w of data ?? []) {
    workoutMap[w.scheduled_date] = w
  }

  // Calendar grid
  const firstDay = new Date(year, month - 1, 1)
  const daysInMonth = new Date(year, month, 0).getDate()
  // Monday-first offset
  const startOffset = firstDay.getDay() === 0 ? 6 : firstDay.getDay() - 1

  const cells: (number | null)[] = [
    ...Array(startOffset).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ]
  // Pad to complete weeks
  while (cells.length % 7 !== 0) cells.push(null)

  return (
    <div>
      {/* Day headers */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 2, marginBottom: 4 }}>
        {DAY_NAMES.map((d) => (
          <div key={d} style={{ textAlign: "center", fontSize: "var(--text-xs)", color: "var(--gray-400)", fontWeight: 600, padding: "4px 0" }}>
            {d}
          </div>
        ))}
      </div>

      {/* Day cells */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 2 }}>
        {cells.map((day, idx) => {
          if (!day) return <div key={idx} />
          const dateStr = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`
          const w = workoutMap[dateStr]
          const isToday = dateStr === today

          return (
            <div
              key={idx}
              style={{
                minHeight: 44,
                borderRadius: 8,
                background: isToday ? "var(--accent-light)" + "44" : "var(--gray-50)",
                border: isToday ? "1.5px solid var(--accent)" : "1.5px solid transparent",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "flex-start",
                padding: "4px 2px",
                gap: 3,
              }}
            >
              <span style={{
                fontSize: "var(--text-xs)",
                fontWeight: isToday ? 700 : 400,
                color: isToday ? "var(--accent)" : "var(--gray-600)",
              }}>
                {day}
              </span>
              {w && <WorkoutChip workout={w} compact />}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function TrainingPage() {
  const [viewMode, setViewMode] = useState<"week" | "month">("week")
  const [weekStart, setWeekStart] = useState(() => getMondayOf(new Date()))
  const [monthOffset, setMonthOffset] = useState(0)

  const now = new Date()
  const displayYear = new Date(now.getFullYear(), now.getMonth() + monthOffset).getFullYear()
  const displayMonth = ((now.getMonth() + monthOffset) % 12 + 12) % 12 + 1

  function prevWeek() { const d = new Date(weekStart); d.setDate(d.getDate() - 7); setWeekStart(d) }
  function nextWeek() { const d = new Date(weekStart); d.setDate(d.getDate() + 7); setWeekStart(d) }

  const weekLabel = (() => {
    const end = new Date(weekStart); end.setDate(weekStart.getDate() + 6)
    return `${weekStart.getDate()} ${MONTH_NAMES[weekStart.getMonth()]} – ${end.getDate()} ${MONTH_NAMES[end.getMonth()]}`
  })()

  const monthLabel = `${MONTH_NAMES[displayMonth - 1]} ${displayYear}`

  return (
    <PageWrapper>
      <div className="container" style={{ paddingTop: 24, paddingBottom: 100 }}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
          <h1 style={{ fontSize: "var(--text-xl)", fontWeight: 700, color: "var(--gray-900)" }}>Training</h1>
          <Link
            href="/dashboard/training/plan"
            style={{ fontSize: "var(--text-sm)", color: "var(--accent)", fontWeight: 600, textDecoration: "none" }}
          >
            Plan →
          </Link>
        </div>

        {/* View toggle */}
        <div style={{ display: "flex", gap: 4, marginBottom: 16, background: "var(--gray-100)", borderRadius: 10, padding: 3 }}>
          {(["week", "month"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setViewMode(m)}
              style={{
                flex: 1, padding: "6px 0", borderRadius: 8, border: "none", cursor: "pointer",
                background: viewMode === m ? "var(--gray-0)" : "transparent",
                color: viewMode === m ? "var(--gray-900)" : "var(--gray-400)",
                fontWeight: viewMode === m ? 600 : 400,
                fontSize: "var(--text-sm)",
                boxShadow: viewMode === m ? "0 1px 3px rgba(0,0,0,0.08)" : "none",
              }}
            >
              {m.charAt(0).toUpperCase() + m.slice(1)}
            </button>
          ))}
        </div>

        {/* Navigator */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <button
            className="btn-secondary"
            style={{ padding: "6px 10px" }}
            onClick={viewMode === "week" ? prevWeek : () => setMonthOffset(o => o - 1)}
          >
            <ChevronLeft size={16} />
          </button>
          <span style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--gray-900)" }}>
            {viewMode === "week" ? weekLabel : monthLabel}
          </span>
          <button
            className="btn-secondary"
            style={{ padding: "6px 10px" }}
            onClick={viewMode === "week" ? nextWeek : () => setMonthOffset(o => o + 1)}
          >
            <ChevronRight size={16} />
          </button>
        </div>

        {/* Calendar */}
        {viewMode === "week"
          ? <WeekView weekStart={weekStart} />
          : <MonthView year={displayYear} month={displayMonth} />
        }
      </div>
    </PageWrapper>
  )
}
