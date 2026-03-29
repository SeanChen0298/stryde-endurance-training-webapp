"use client"

import { useState, useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Loader2, Download, RefreshCw, AlertCircle, CheckCircle, Calendar } from "lucide-react"
import { api, type TrainingPlanResponse } from "@/lib/api"
import { PageWrapper } from "@/components/PageWrapper"
import { AIFeatureGate } from "@/components/AIFeatureGate"

const MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

const WORKOUT_TYPE_COLORS: Record<string, string> = {
  easy:     "var(--status-green)",
  long_run: "var(--accent)",
  tempo:    "var(--status-amber)",
  interval: "var(--status-red)",
  race:     "#8B5CF6",
  rest:     "var(--gray-300)",
}

function fmtDate(s: string) {
  const d = new Date(s + "T00:00:00")
  return `${d.getDate()} ${MONTH_NAMES[d.getMonth()]} ${d.getFullYear()}`
}

function fmtGoalTime(seconds: number | null) {
  if (!seconds) return null
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  return h > 0 ? `${h}:${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}` : `${m}:${String(s).padStart(2,"0")}`
}

function WorkoutTypeStat({ plan }: { plan: TrainingPlanResponse }) {
  const counts: Record<string, number> = {}
  for (const w of plan.workouts) {
    counts[w.workout_type] = (counts[w.workout_type] ?? 0) + 1
  }
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
      {Object.entries(counts).sort((a, b) => b[1] - a[1]).map(([type, count]) => (
        <div key={type} style={{
          display: "flex", alignItems: "center", gap: 5,
          background: "var(--gray-50)", borderRadius: 8, padding: "5px 10px",
        }}>
          <div style={{
            width: 8, height: 8, borderRadius: "50%",
            background: WORKOUT_TYPE_COLORS[type] ?? "var(--gray-400)",
          }} />
          <span style={{ fontSize: "var(--text-xs)", color: "var(--gray-600)", fontWeight: 500 }}>
            {type.replace("_", " ")} ×{count}
          </span>
        </div>
      ))}
    </div>
  )
}

function PlanCard({ plan }: { plan: TrainingPlanResponse }) {
  const queryClient = useQueryClient()
  const [showRevision, setShowRevision] = useState(false)
  const exportUrl = api.calendar.exportUrl()

  const reviseMutation = useMutation({
    mutationFn: api.plans.generate,
    onSuccess: () => {
      // Poll until new plan appears
      const interval = setInterval(async () => {
        await queryClient.invalidateQueries({ queryKey: ["plans", "active"] })
        clearInterval(interval)
      }, 5000)
      setTimeout(() => clearInterval(interval), 60000)
    },
  })

  const weeklyStructure = plan.weekly_structure as Record<string, number[]> | null
  const totalKm = plan.workouts.reduce((sum, w) => sum + (w.target_distance_meters ?? 0), 0) / 1000
  const weeks = Math.round(
    (new Date(plan.valid_to).getTime() - new Date(plan.valid_from).getTime()) / (7 * 86400000)
  )

  return (
    <div>
      {/* Meta */}
      <div className="card" style={{ marginBottom: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
          <div>
            <div className="card-title" style={{ marginBottom: 4 }}>
              {plan.goal_race_type?.replace("_", " ").replace(/\b\w/g, c => c.toUpperCase()) ?? "Training Plan"}
            </div>
            <div className="body-text" style={{ fontSize: "var(--text-xs)" }}>
              {fmtDate(plan.valid_from)} — {fmtDate(plan.valid_to)}
            </div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--gray-400)" }}>{weeks} weeks</div>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--gray-400)" }}>{totalKm.toFixed(0)} km total</div>
          </div>
        </div>

        {plan.goal_race_date && (
          <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 10 }}>
            <Calendar size={13} color="var(--accent)" />
            <span style={{ fontSize: "var(--text-xs)", color: "var(--gray-600)" }}>
              Race: {fmtDate(plan.goal_race_date)}
              {plan.goal_time_seconds && ` · Goal ${fmtGoalTime(plan.goal_time_seconds)}`}
            </span>
          </div>
        )}

        <WorkoutTypeStat plan={plan} />
      </div>

      {/* AI summary */}
      {plan.plan_summary && (
        <div className="card" style={{ marginBottom: 12 }}>
          <div className="metric-label" style={{ marginBottom: 8 }}>Plan approach</div>
          <p className="body-text">{plan.plan_summary}</p>
        </div>
      )}

      {/* Periodisation blocks */}
      {weeklyStructure && (
        <div className="card" style={{ marginBottom: 12 }}>
          <div className="metric-label" style={{ marginBottom: 10 }}>Periodisation</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {[
              { key: "base_weeks", label: "Base", color: "var(--status-green)" },
              { key: "build_weeks", label: "Build", color: "var(--accent)" },
              { key: "peak_weeks", label: "Peak", color: "var(--status-red)" },
              { key: "taper_weeks", label: "Taper", color: "var(--gray-400)" },
            ].map(({ key, label, color }) => {
              const wks = weeklyStructure[key] as number[] | undefined
              if (!wks?.length) return null
              return (
                <div key={key} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div style={{ width: 8, height: 8, borderRadius: "50%", background: color, flexShrink: 0 }} />
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--gray-600)", width: 36 }}>{label}</span>
                  <div style={{ flex: 1, display: "flex", gap: 3 }}>
                    {wks.map(w => (
                      <div key={w} style={{
                        width: 22, height: 22, borderRadius: 6,
                        background: color + "33", border: `1.5px solid ${color}`,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontSize: "var(--text-xs)", color, fontWeight: 600,
                      }}>
                        {w}
                      </div>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Revision reason */}
      {plan.revision_reason && (
        <div
          style={{
            background: "#FFFBEB", border: "1px solid #FDE68A", borderRadius: 10,
            padding: "10px 12px", marginBottom: 12, display: "flex", gap: 8, alignItems: "flex-start",
          }}
        >
          <AlertCircle size={14} color="#B45309" style={{ flexShrink: 0, marginTop: 1 }} />
          <span style={{ fontSize: "var(--text-xs)", color: "#92400E" }}>{plan.revision_reason}</span>
        </div>
      )}

      {/* Actions */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <a
          href={exportUrl}
          download="stryde-training-plan.ics"
          className="btn-secondary"
          style={{ display: "flex", alignItems: "center", gap: 6, textDecoration: "none", fontSize: "var(--text-sm)" }}
        >
          <Download size={14} /> Export .ics
        </a>
        <button
          className="btn-secondary"
          style={{ display: "flex", alignItems: "center", gap: 6 }}
          onClick={() => setShowRevision(true)}
          disabled={reviseMutation.isPending}
        >
          {reviseMutation.isPending
            ? <><Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> Generating…</>
            : reviseMutation.isSuccess
            ? <><CheckCircle size={14} color="var(--status-green)" /> New plan coming…</>
            : <><RefreshCw size={14} /> Regenerate plan</>
          }
        </button>
      </div>

      {showRevision && !reviseMutation.isPending && !reviseMutation.isSuccess && (
        <div style={{
          marginTop: 12, padding: "12px 14px", background: "var(--gray-50)",
          borderRadius: 10, border: "1px solid var(--gray-200)",
        }}>
          <p className="body-text" style={{ marginBottom: 10, fontSize: "var(--text-xs)" }}>
            This will replace your current plan. The new plan will use your latest fitness data and health metrics.
          </p>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn-primary" style={{ fontSize: "var(--text-xs)", padding: "7px 14px" }}
              onClick={() => { reviseMutation.mutate(); setShowRevision(false) }}>
              Yes, regenerate
            </button>
            <button className="btn-secondary" style={{ fontSize: "var(--text-xs)", padding: "7px 14px" }}
              onClick={() => setShowRevision(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function NoPlanState() {
  const queryClient = useQueryClient()
  const [polling, setPolling] = useState(false)

  const generateMutation = useMutation({
    mutationFn: api.plans.generate,
    onSuccess: () => setPolling(true),
  })

  // Poll every 5s for up to 90s after generation starts
  useQuery({
    queryKey: ["plans", "active"],
    queryFn: api.plans.active,
    refetchInterval: polling ? 5000 : false,
    retry: false,
  })

  useEffect(() => {
    if (!polling) return
    const t = setTimeout(() => setPolling(false), 90000)
    return () => clearTimeout(t)
  }, [polling])

  return (
    <div style={{ textAlign: "center", padding: "48px 24px" }}>
      <Calendar size={40} strokeWidth={1.25} style={{ margin: "0 auto 16px", color: "var(--gray-300)" }} />
      <h2 style={{ fontSize: "var(--text-lg)", fontWeight: 600, marginBottom: 8 }}>No training plan yet</h2>
      <p className="body-text" style={{ marginBottom: 24 }}>
        Gemini will analyse your recent training and build a personalised plan based on your race goal.
      </p>

      {polling ? (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, color: "var(--gray-600)" }}>
          <Loader2 size={16} style={{ animation: "spin 1s linear infinite" }} />
          <span style={{ fontSize: "var(--text-sm)" }}>Generating your plan… this takes ~30 seconds</span>
        </div>
      ) : (
        <button
          className="btn-primary"
          onClick={() => generateMutation.mutate()}
          disabled={generateMutation.isPending}
          style={{ display: "inline-flex", alignItems: "center", gap: 8 }}
        >
          {generateMutation.isPending
            ? <><Loader2 size={16} style={{ animation: "spin 1s linear infinite" }} /> Starting…</>
            : "Generate training plan"}
        </button>
      )}

      {generateMutation.isSuccess && !polling && (
        <div style={{
          marginTop: 16, padding: "10px 14px", background: "#F0FDF4",
          border: "1px solid #BBF7D0", borderRadius: 10, display: "flex", gap: 8, alignItems: "center",
        }}>
          <CheckCircle size={14} color="var(--status-green)" />
          <span style={{ fontSize: "var(--text-xs)", color: "#15803D" }}>
            {generateMutation.data?.message ?? "Plan generation started"}
          </span>
        </div>
      )}
    </div>
  )
}

export default function PlanPage() {
  const { data: plan, isLoading, error } = useQuery({
    queryKey: ["plans", "active"],
    queryFn: api.plans.active,
    retry: false,
  })

  return (
    <PageWrapper>
      <div className="container" style={{ paddingTop: 24, paddingBottom: 100 }}>
        <h1 style={{ fontSize: "var(--text-xl)", fontWeight: 700, marginBottom: 20 }}>Training Plan</h1>

        <AIFeatureGate>
          {isLoading ? (
            <div>
              <div className="skeleton" style={{ height: 120, borderRadius: 12, marginBottom: 12 }} />
              <div className="skeleton" style={{ height: 80, borderRadius: 12 }} />
            </div>
          ) : error || !plan ? (
            <NoPlanState />
          ) : (
            <PlanCard plan={plan} />
          )}
        </AIFeatureGate>
      </div>
    </PageWrapper>
  )
}
