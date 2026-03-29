const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export class APIError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string,
  ) {
    super(message)
    this.name = "APIError"
  }
}

function getAuthHeader(): Record<string, string> {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export function setToken(token: string) {
  localStorage.setItem("access_token", token)
}

export function clearToken() {
  localStorage.removeItem("access_token")
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...getAuthHeader(), ...options?.headers },
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new APIError(res.status, err.detail ?? err.error ?? "Unknown error", err.code)
  }

  return res.json()
}

// ── Type definitions ──────────────────────────────────────────────────────────

export interface LoginResponse {
  access_token: string
  token_type: string
  athlete_name: string | null
  gemini_connected: boolean
}

export interface AthleteProfile {
  id: string
  email: string
  name: string | null
  timezone: string
  goal_race_type: string | null
  goal_race_date: string | null
  goal_finish_time_seconds: number | null
  gemini_connected: boolean
  gemini_model: string
  strava_connected: boolean
  garmin_connected: boolean
}

export interface WeeklyMileage {
  current_km: number
  target_km: number | null
  run_count: number
  daily_runs: number[]
}

export interface RecentActivity {
  id: string
  activity_type: string
  workout_type: string | null
  started_at: string
  distance_km: number | null
  pace_str: string | null
  duration_str: string | null
  avg_hr: number | null
  source: string
}

export interface HRVPoint { date: string; value: number | null }
export interface SleepPoint { date: string; score: number | null; duration_minutes: number | null }

export interface DashboardData {
  weekly_mileage: WeeklyMileage
  recent_activities: RecentActivity[]
  hrv_trend: HRVPoint[]
  sleep_trend: SleepPoint[]
  gemini_connected: boolean
  garmin_connected: boolean
  strava_connected: boolean
  readiness_score: number | null
  readiness_label: string | null
  ai_brief: string | null
}

export interface ActivitySummary {
  id: string
  activity_type: string
  workout_type: string | null
  started_at: string
  distance_km: number | null
  duration_str: string | null
  pace_str: string | null
  avg_hr: number | null
  max_hr: number | null
  elevation_gain_m: number | null
  source: string
  gear_id: string | null
}

export interface ActivityDetail extends ActivitySummary {
  avg_cadence: number | null
  avg_power: number | null
  hr_zone_distribution: Record<string, number> | null
  splits: Array<{ km: number; pace_s_per_km: number | null; hr: number | null }> | null
  notes: string | null
  perceived_effort: number | null
}

export interface ActivitiesListResponse {
  total: number
  page: number
  per_page: number
  items: ActivitySummary[]
}

export interface GeminiKeyRequest {
  api_key: string
  model?: string
}

export interface GarminCredentialsRequest {
  email: string
  password: string
  mfa_code?: string
}

export interface GarminStatus {
  connected: boolean
  email: string | null
}

export interface ReadinessPoint {
  date: string
  score: number | null
  label: string | null
  ai_summary: string | null
}

export interface HealthDayDetail {
  date: string
  readiness_score: number | null
  readiness_label: string | null
  hrv_delta_pct: number | null
  sleep_delta_pct: number | null
  load_delta_pct: number | null
  ai_summary: string | null
  ai_recommendation: string | null
  hrv_rmssd: number | null
  resting_hr: number | null
  sleep_score: number | null
  sleep_duration_minutes: number | null
  deep_sleep_minutes: number | null
  rem_sleep_minutes: number | null
  body_battery_max: number | null
  body_battery_min: number | null
  stress_avg: number | null
  steps: number | null
  spo2_avg: number | null
}

export interface PlannedWorkoutOut {
  id: string
  plan_id: string
  scheduled_date: string
  workout_type: string
  title: string
  description: string | null
  target_distance_meters: number | null
  target_duration_minutes: number | null
  target_pace_min_seconds_per_km: number | null
  target_pace_max_seconds_per_km: number | null
  target_hr_zone: number | null
  target_rpe: number | null
  intensity_points: number | null
  completed: boolean
  completed_activity_id: string | null
}

export interface TrainingPlanResponse {
  id: string
  created_at: string
  valid_from: string
  valid_to: string
  goal_race_type: string | null
  goal_race_date: string | null
  goal_time_seconds: number | null
  status: string
  plan_summary: string | null
  revision_reason: string | null
  weekly_structure: Record<string, unknown> | null
  workouts: PlannedWorkoutOut[]
}

export interface ActivitySummaryOut {
  id: string
  started_at: string
  distance_km: number | null
  pace_str: string | null
  avg_hr: number | null
  workout_type: string | null
}

export interface WeekDay {
  date: string
  planned: PlannedWorkoutOut | null
  actual: ActivitySummaryOut | null
}

export interface WeekCalendarResponse {
  week_start: string
  days: WeekDay[]
}

// ── API surface ───────────────────────────────────────────────────────────────

export const api = {
  auth: {
    login: async (email: string, password: string) => {
      const res = await apiFetch<LoginResponse>("/auth/login", {
        method: "POST",
        body: new URLSearchParams({ username: email, password }).toString(),
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      })
      setToken(res.access_token)
      return res
    },
    logout: async () => {
      clearToken()
      return apiFetch<void>("/auth/logout", { method: "POST" })
    },
    stravaUrl: () => apiFetch<{ url: string }>("/auth/strava/url"),
    me: () => apiFetch<AthleteProfile>("/auth/me"),
  },

  dashboard: () => apiFetch<DashboardData>("/dashboard"),

  activities: {
    list: (params?: { page?: number; per_page?: number; activity_type?: string; workout_type?: string }) => {
      const qs = new URLSearchParams()
      if (params?.page) qs.set("page", String(params.page))
      if (params?.per_page) qs.set("per_page", String(params.per_page))
      if (params?.activity_type) qs.set("activity_type", params.activity_type)
      if (params?.workout_type) qs.set("workout_type", params.workout_type)
      return apiFetch<ActivitiesListResponse>(`/activities?${qs}`)
    },
    get: (id: string) => apiFetch<ActivityDetail>(`/activities/${id}`),
    monthlySummary: (year?: number, month?: number) => {
      const qs = new URLSearchParams()
      if (year) qs.set("year", String(year))
      if (month) qs.set("month", String(month))
      return apiFetch<{ total_km: number; total_runs: number; total_duration_seconds: number; avg_hr: number | null }>(`/activities/monthly-summary?${qs}`)
    },
  },

  health: {
    history: (days?: number) => apiFetch<ReadinessPoint[]>(`/health/history${days ? `?days=${days}` : ""}`),
    today: () => apiFetch<HealthDayDetail>("/health/today"),
    day: (dateStr: string) => apiFetch<HealthDayDetail>(`/health/${dateStr}`),
  },

  settings: {
    getProfile: () => apiFetch<AthleteProfile>("/settings/profile"),
    updateProfile: (data: Partial<AthleteProfile>) =>
      apiFetch<{ status: string }>("/settings/profile", { method: "PATCH", body: JSON.stringify(data) }),
    getGarminStatus: () => apiFetch<GarminStatus>("/settings/garmin"),
    connectGarmin: (req: GarminCredentialsRequest) =>
      apiFetch<{ status: string; email: string }>("/settings/garmin", { method: "POST", body: JSON.stringify(req) }),
    connectGarminToken: (req: { token_json: string; email?: string }) =>
      apiFetch<{ status: string; email: string }>("/settings/garmin/token", { method: "POST", body: JSON.stringify(req) }),
    disconnectGarmin: () => apiFetch<{ status: string }>("/settings/garmin", { method: "DELETE" }),
    syncGarmin: () => apiFetch<{ status: string }>("/settings/garmin/sync", { method: "POST" }),
    getGeminiStatus: () => apiFetch<{ connected: boolean; model: string | null }>("/settings/gemini"),
    saveGeminiKey: (req: GeminiKeyRequest) =>
      apiFetch<{ status: string; model: string }>("/settings/gemini", { method: "POST", body: JSON.stringify(req) }),
    testGeminiKey: (req: GeminiKeyRequest) =>
      apiFetch<{ status: string }>("/settings/gemini/test", { method: "POST", body: JSON.stringify(req) }),
    removeGeminiKey: () => apiFetch<{ status: string }>("/settings/gemini", { method: "DELETE" }),
  },

  plans: {
    active: () => apiFetch<TrainingPlanResponse>("/plans/active"),
    generate: () => apiFetch<{ status: string; message: string }>("/plans/generate", { method: "POST" }),
    week: (start: string) => apiFetch<WeekCalendarResponse>(`/plans/workouts/week?start=${start}`),
    month: (year: number, month: number) => apiFetch<PlannedWorkoutOut[]>(`/plans/workouts/month?year=${year}&month=${month}`),
    completeWorkout: (id: string, activityId?: string) =>
      apiFetch<PlannedWorkoutOut>(`/plans/workouts/${id}/complete`, {
        method: "POST",
        body: JSON.stringify({ activity_id: activityId ?? null }),
      }),
  },

  calendar: {
    exportUrl: () => `${BASE}/calendar/export.ics`,
  },
}
