"use client"

import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Eye, EyeOff, CheckCircle, Loader2, Trash2, AlertCircle } from "lucide-react"
import { api, APIError } from "@/lib/api"
import { applyTheme, THEMES, type ThemeKey } from "@/lib/theme"
import { PageWrapper } from "@/components/PageWrapper"
import { TabBar } from "@/components/TabBar"

export default function SettingsPage() {
  const queryClient = useQueryClient()
  const { data: profile } = useQuery({ queryKey: ["settings", "profile"], queryFn: api.settings.getProfile })
  const { data: gemini } = useQuery({ queryKey: ["settings", "gemini"], queryFn: api.settings.getGeminiStatus })

  const [geminiKey, setGeminiKey] = useState("")
  const [showKey, setShowKey] = useState(false)
  const [selectedModel, setSelectedModel] = useState("gemini-2.5-flash")
  const [keyError, setKeyError] = useState<string | null>(null)
  const [keySaved, setKeySaved] = useState(false)
  const [activeTheme, setActiveTheme] = useState<ThemeKey>("ember")

  const saveKeyMutation = useMutation({
    mutationFn: () => api.settings.saveGeminiKey({ api_key: geminiKey, model: selectedModel }),
    onSuccess: () => {
      setKeySaved(true)
      setGeminiKey("")
      setKeyError(null)
      queryClient.invalidateQueries({ queryKey: ["settings", "gemini"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard"] })
      setTimeout(() => setKeySaved(false), 3000)
    },
    onError: (err) => {
      if (err instanceof APIError) setKeyError(err.message)
    },
  })

  const removeKeyMutation = useMutation({
    mutationFn: api.settings.removeGeminiKey,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "gemini"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard"] })
    },
  })

  function handleTheme(key: ThemeKey) {
    setActiveTheme(key)
    applyTheme(key)
  }

  return (
    <>
      <TabBar />
      <PageWrapper>
        <div className="container page-content">
          <h1 style={{ fontSize: "var(--text-xl)", fontWeight: 600, marginBottom: 24, marginTop: 0 }}>
            Settings
          </h1>

          {/* Profile section */}
          <Section title="Profile">
            {profile && (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <div>
                  <div className="metric-label" style={{ marginBottom: 4 }}>Name</div>
                  <div style={{ fontSize: "var(--text-base)", color: "var(--gray-900)" }}>{profile.name}</div>
                </div>
                <div>
                  <div className="metric-label" style={{ marginBottom: 4 }}>Email</div>
                  <div style={{ fontSize: "var(--text-base)", color: "var(--gray-900)" }}>{profile.email}</div>
                </div>
                <div>
                  <div className="metric-label" style={{ marginBottom: 4 }}>Timezone</div>
                  <div style={{ fontSize: "var(--text-base)", color: "var(--gray-900)" }}>{profile.timezone}</div>
                </div>
                {profile.goal_race_date && (
                  <div>
                    <div className="metric-label" style={{ marginBottom: 4 }}>Goal race</div>
                    <div style={{ fontSize: "var(--text-base)", color: "var(--gray-900)" }}>
                      {profile.goal_race_type?.replace("_", " ")} · {profile.goal_race_date}
                    </div>
                  </div>
                )}
              </div>
            )}
          </Section>

          {/* AI Configuration */}
          <Section title="AI Configuration" id="ai">
            {gemini?.connected ? (
              <div>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    marginBottom: 16,
                    padding: "10px 14px",
                    background: "#F0FDF4",
                    borderRadius: 10,
                    border: "1px solid #BBF7D0",
                  }}
                >
                  <CheckCircle size={16} color="var(--status-green)" />
                  <span style={{ fontSize: "var(--text-sm)", color: "#15803D", fontWeight: 600 }}>
                    Connected · {gemini.model}
                  </span>
                </div>

                <div style={{ marginBottom: 12 }}>
                  <div className="metric-label" style={{ marginBottom: 8 }}>Model</div>
                  {["gemini-2.5-flash", "gemini-2.5-flash-lite"].map((m) => (
                    <label
                      key={m}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        marginBottom: 8,
                        cursor: "pointer",
                        fontSize: "var(--text-sm)",
                      }}
                    >
                      <input
                        type="radio"
                        name="model"
                        value={m}
                        checked={selectedModel === m}
                        onChange={() => setSelectedModel(m)}
                        style={{ accentColor: "var(--accent)" }}
                      />
                      <span style={{ color: "var(--gray-900)" }}>
                        {m === "gemini-2.5-flash" ? "Gemini 2.5 Flash" : "Gemini 2.5 Flash Lite (faster)"}
                      </span>
                    </label>
                  ))}
                </div>

                <button
                  className="btn-secondary"
                  style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--status-red)" }}
                  onClick={() => removeKeyMutation.mutate()}
                  disabled={removeKeyMutation.isPending}
                >
                  <Trash2 size={14} /> Remove API key
                </button>
              </div>
            ) : (
              <div>
                <p className="body-text" style={{ marginBottom: 16 }}>
                  Add your free Gemini API key from{" "}
                  <span style={{ color: "var(--accent)", fontWeight: 600 }}>aistudio.google.com</span> to
                  enable AI coaching features.
                </p>

                <div style={{ marginBottom: 12 }}>
                  <div className="metric-label" style={{ marginBottom: 6 }}>API Key</div>
                  <div style={{ position: "relative" }}>
                    <input
                      type={showKey ? "text" : "password"}
                      className="input"
                      placeholder="AIzaSy..."
                      value={geminiKey}
                      onChange={(e) => { setGeminiKey(e.target.value); setKeyError(null) }}
                      style={{ paddingRight: 48 }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowKey(!showKey)}
                      style={{
                        position: "absolute", right: 14, top: "50%",
                        transform: "translateY(-50%)",
                        background: "none", border: "none", cursor: "pointer",
                        color: "var(--gray-400)", padding: 4, display: "flex",
                      }}
                    >
                      {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>

                <div style={{ marginBottom: 16 }}>
                  <div className="metric-label" style={{ marginBottom: 8 }}>Model</div>
                  {["gemini-2.5-flash", "gemini-2.5-flash-lite"].map((m) => (
                    <label
                      key={m}
                      style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, cursor: "pointer", fontSize: "var(--text-sm)" }}
                    >
                      <input
                        type="radio" name="model" value={m}
                        checked={selectedModel === m}
                        onChange={() => setSelectedModel(m)}
                        style={{ accentColor: "var(--accent)" }}
                      />
                      <span style={{ color: "var(--gray-900)" }}>
                        {m === "gemini-2.5-flash" ? "Gemini 2.5 Flash" : "Gemini 2.5 Flash Lite"}
                      </span>
                    </label>
                  ))}
                </div>

                {keyError && (
                  <div
                    style={{
                      background: "#FEF2F2", border: "1px solid #FECACA", borderRadius: 8,
                      padding: "10px 12px", fontSize: "var(--text-sm)", color: "#B91C1C", marginBottom: 12,
                    }}
                  >
                    {keyError}
                  </div>
                )}

                {keySaved && (
                  <div
                    style={{
                      background: "#F0FDF4", border: "1px solid #BBF7D0", borderRadius: 8,
                      padding: "10px 12px", fontSize: "var(--text-sm)", color: "#15803D",
                      display: "flex", alignItems: "center", gap: 6, marginBottom: 12,
                    }}
                  >
                    <CheckCircle size={14} /> Key saved successfully
                  </div>
                )}

                <button
                  className="btn-primary"
                  onClick={() => saveKeyMutation.mutate()}
                  disabled={!geminiKey || saveKeyMutation.isPending}
                  style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}
                >
                  {saveKeyMutation.isPending ? (
                    <><Loader2 size={16} style={{ animation: "spin 1s linear infinite" }} /> Testing key…</>
                  ) : (
                    "Save & connect"
                  )}
                </button>
                <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
              </div>
            )}
          </Section>

          {/* Connected services */}
          <Section title="Connected services">
            <ServiceRow
              name="Strava"
              description="Activities, routes, segments"
              connected={profile?.strava_connected ?? false}
              connectHref="/auth/strava"
            />
          </Section>

          {/* Garmin Connect */}
          <Section title="Garmin Connect">
            <GarminSection />
          </Section>

          {/* Appearance */}
          <Section title="Appearance">
            <div className="metric-label" style={{ marginBottom: 10 }}>Accent colour</div>
            <div style={{ display: "flex", gap: 10 }}>
              {(Object.keys(THEMES) as ThemeKey[]).map((key) => (
                <button
                  key={key}
                  onClick={() => handleTheme(key)}
                  title={THEMES[key].name}
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: "50%",
                    background: THEMES[key].accent,
                    border: activeTheme === key ? `2.5px solid var(--gray-900)` : "2.5px solid transparent",
                    cursor: "pointer",
                    transition: "border 150ms ease, transform 100ms ease",
                    padding: 0,
                  }}
                  aria-label={THEMES[key].name}
                />
              ))}
            </div>
          </Section>

          {/* Account */}
          <Section title="Account">
            <button
              className="btn-secondary"
              onClick={async () => { await api.auth.logout(); window.location.href = "/login" }}
              style={{ width: "100%", marginBottom: 8 }}
            >
              Sign out
            </button>
          </Section>
        </div>
      </PageWrapper>
    </>
  )
}

function GarminSection() {
  const queryClient = useQueryClient()
  const { data: garmin, isLoading } = useQuery({
    queryKey: ["settings", "garmin"],
    queryFn: api.settings.getGarminStatus,
  })

  const [mode, setMode] = useState<"credentials" | "token">("credentials")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [mfaCode, setMfaCode] = useState("")
  const [showPw, setShowPw] = useState(false)
  const [needsMfa, setNeedsMfa] = useState(false)
  const [tokenJson, setTokenJson] = useState("")
  const [error, setError] = useState<string | null>(null)

  const connectMutation = useMutation({
    mutationFn: () =>
      api.settings.connectGarmin({ email, password, mfa_code: mfaCode || undefined }),
    onSuccess: () => {
      setEmail(""); setPassword(""); setMfaCode(""); setNeedsMfa(false); setError(null)
      queryClient.invalidateQueries({ queryKey: ["settings", "garmin"] })
      queryClient.invalidateQueries({ queryKey: ["settings", "profile"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard"] })
    },
    onError: (err) => {
      if (err instanceof APIError) {
        if (err.message.toLowerCase().includes("mfa") || err.message.toLowerCase().includes("two-factor")) {
          setNeedsMfa(true)
          setError("Enter the 6-digit code from your authenticator app")
        } else if (err.status === 429 || err.message.toLowerCase().includes("rate")) {
          setMode("token")
          setError("rate_limited")
        } else {
          setError(err.message)
        }
      }
    },
  })

  const pasteTokenMutation = useMutation({
    mutationFn: () => api.settings.connectGarminToken({ token_json: tokenJson, email }),
    onSuccess: () => {
      setTokenJson(""); setEmail(""); setError(null)
      queryClient.invalidateQueries({ queryKey: ["settings", "garmin"] })
      queryClient.invalidateQueries({ queryKey: ["settings", "profile"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard"] })
    },
    onError: (err) => {
      if (err instanceof APIError) setError(err.message)
    },
  })

  const disconnectMutation = useMutation({
    mutationFn: api.settings.disconnectGarmin,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "garmin"] })
      queryClient.invalidateQueries({ queryKey: ["settings", "profile"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard"] })
    },
  })

  const syncMutation = useMutation({
    mutationFn: api.settings.syncGarmin,
  })

  if (isLoading) return <div className="skeleton" style={{ height: 40 }} />

  if (garmin?.connected) {
    return (
      <div>
        <div
          style={{
            display: "flex", alignItems: "center", gap: 8, marginBottom: 16,
            padding: "10px 14px", background: "#F0FDF4", borderRadius: 10, border: "1px solid #BBF7D0",
          }}
        >
          <CheckCircle size={16} color="var(--status-green)" />
          <div style={{ flex: 1 }}>
            <span style={{ fontSize: "var(--text-sm)", color: "#15803D", fontWeight: 600 }}>
              Connected
            </span>
            {garmin.email && (
              <span style={{ fontSize: "var(--text-xs)", color: "#15803D", marginLeft: 8 }}>
                {garmin.email}
              </span>
            )}
          </div>
        </div>
        <p className="body-text" style={{ marginBottom: 16 }}>
          Health data (HRV, sleep, body battery) syncs daily at 06:00 MYT.
        </p>
        <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
          <button
            className="btn-secondary"
            style={{ display: "flex", alignItems: "center", gap: 6 }}
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending || syncMutation.isSuccess}
          >
            {syncMutation.isPending
              ? <><Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> Syncing…</>
              : syncMutation.isSuccess
              ? <><CheckCircle size={14} color="var(--status-green)" /> Sync started</>
              : "Sync now (last 90 days)"}
          </button>
          <button
            className="btn-secondary"
            style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--status-red)" }}
            onClick={() => disconnectMutation.mutate()}
            disabled={disconnectMutation.isPending}
          >
            <Trash2 size={14} /> Disconnect
          </button>
        </div>
      </div>
    )
  }

  return (
    <div>
      {/* Mode toggle */}
      <div style={{ display: "flex", gap: 4, marginBottom: 16, background: "var(--gray-100)", borderRadius: 10, padding: 3 }}>
        {(["credentials", "token"] as const).map((m) => (
          <button
            key={m}
            onClick={() => { setMode(m); setError(null) }}
            style={{
              flex: 1, padding: "6px 0", borderRadius: 8, border: "none", cursor: "pointer",
              fontSize: "var(--text-xs)", fontWeight: 600,
              background: mode === m ? "var(--gray-0)" : "transparent",
              color: mode === m ? "var(--gray-900)" : "var(--gray-400)",
              boxShadow: mode === m ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
              transition: "all 150ms ease",
            }}
          >
            {m === "credentials" ? "Sign in" : "Rate-limited? Paste token"}
          </button>
        ))}
      </div>

      {mode === "credentials" ? (
        <div>
          <p className="body-text" style={{ marginBottom: 14 }}>
            The server logs in to Garmin on your behalf — works from any device, no Python needed.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 12 }}>
            <div>
              <div className="metric-label" style={{ marginBottom: 6 }}>Email</div>
              <input type="email" className="input" placeholder="you@example.com"
                value={email} onChange={(e) => { setEmail(e.target.value); setError(null) }} />
            </div>
            <div>
              <div className="metric-label" style={{ marginBottom: 6 }}>Password</div>
              <div style={{ position: "relative" }}>
                <input
                  type={showPw ? "text" : "password"} className="input"
                  placeholder="Garmin Connect password" value={password}
                  onChange={(e) => { setPassword(e.target.value); setError(null) }}
                  style={{ paddingRight: 48 }}
                />
                <button type="button" onClick={() => setShowPw(!showPw)}
                  style={{ position: "absolute", right: 14, top: "50%", transform: "translateY(-50%)",
                    background: "none", border: "none", cursor: "pointer", color: "var(--gray-400)", padding: 4, display: "flex" }}>
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>
            {needsMfa && (
              <div>
                <div className="metric-label" style={{ marginBottom: 6 }}>MFA Code</div>
                <input type="text" className="input" placeholder="123456" value={mfaCode}
                  onChange={(e) => { setMfaCode(e.target.value); setError(null) }}
                  maxLength={6} inputMode="numeric" />
              </div>
            )}
          </div>
          {error && error !== "rate_limited" && <ErrorBox message={error} />}
          <button className="btn-primary" onClick={() => connectMutation.mutate()}
            disabled={!email || !password || connectMutation.isPending}
            style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
            {connectMutation.isPending
              ? <><Loader2 size={16} style={{ animation: "spin 1s linear infinite" }} /> Connecting…</>
              : "Connect Garmin"}
          </button>
        </div>
      ) : (
        <div>
          {error === "rate_limited" && (
            <div style={{
              display: "flex", alignItems: "flex-start", gap: 8,
              background: "#FFFBEB", border: "1px solid #FDE68A", borderRadius: 8,
              padding: "10px 12px", fontSize: "var(--text-sm)", color: "#92400E", marginBottom: 14,
            }}>
              <AlertCircle size={15} style={{ flexShrink: 0, marginTop: 1 }} />
              <span>
                <strong>Garmin is rate-limiting login attempts</strong> — too many tries from the server&apos;s IP.
                Use the token method below to connect without going through Garmin&apos;s SSO.
              </span>
            </div>
          )}
          <div
            style={{
              background: "var(--gray-100)", borderRadius: 10, padding: "12px 14px",
              fontSize: "var(--text-xs)", color: "var(--gray-600)", marginBottom: 14, lineHeight: 1.7,
            }}
          >
            <strong style={{ color: "var(--gray-900)" }}>Run on your own machine (not the server) using the script at C:\Users\cheny\get_garmin_token.py:</strong>
            <pre style={{ margin: "8px 0 0", fontFamily: "monospace", whiteSpace: "pre-wrap", wordBreak: "break-all", color: "var(--gray-900)" }}>
              {`pip install garminconnect\npython get_garmin_token.py`}
            </pre>
            Copy the JSON output and paste below.
          </div>
          <div style={{ marginBottom: 10 }}>
            <div className="metric-label" style={{ marginBottom: 6 }}>Email (for display)</div>
            <input type="email" className="input" placeholder="you@garmin.com"
              value={email} onChange={(e) => { setEmail(e.target.value); setError(null) }} />
          </div>
          <div style={{ marginBottom: 12 }}>
            <div className="metric-label" style={{ marginBottom: 6 }}>Token (output of script above)</div>
            <textarea className="input" placeholder="Paste the token output here…"
              value={tokenJson} onChange={(e) => { setTokenJson(e.target.value); setError(null) }}
              rows={4} style={{ resize: "vertical", fontFamily: "monospace", fontSize: "var(--text-xs)" }} />
          </div>
          {error && error !== "rate_limited" && <ErrorBox message={error} />}
          <button className="btn-primary" onClick={() => pasteTokenMutation.mutate()}
            disabled={!tokenJson || pasteTokenMutation.isPending}
            style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
            {pasteTokenMutation.isPending
              ? <><Loader2 size={16} style={{ animation: "spin 1s linear infinite" }} /> Saving…</>
              : "Save token"}
          </button>
        </div>
      )}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

function ErrorBox({ message }: { message: string }) {
  return (
    <div style={{
      display: "flex", alignItems: "flex-start", gap: 8,
      background: "#FEF2F2", border: "1px solid #FECACA", borderRadius: 8,
      padding: "10px 12px", fontSize: "var(--text-sm)", color: "#B91C1C", marginBottom: 12,
    }}>
      <AlertCircle size={15} style={{ flexShrink: 0, marginTop: 1 }} />
      {message}
    </div>
  )
}

function Section({ title, children, id }: { title: string; children: React.ReactNode; id?: string }) {
  return (
    <section id={id} style={{ marginBottom: 24 }}>
      <div
        style={{
          fontSize: "var(--text-xs)",
          fontWeight: 600,
          color: "var(--gray-400)",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          marginBottom: 8,
          paddingLeft: 4,
        }}
      >
        {title}
      </div>
      <div className="card">{children}</div>
    </section>
  )
}

function ServiceRow({
  name, description, connected, connectHref, pending,
}: {
  name: string
  description: string
  connected: boolean
  connectHref: string
  pending?: boolean
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "10px 0",
        borderBottom: "1px solid var(--gray-100)",
      }}
    >
      <div>
        <div style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--gray-900)" }}>{name}</div>
        <div style={{ fontSize: "var(--text-xs)", color: "var(--gray-400)" }}>{description}</div>
      </div>
      {connected ? (
        <span style={{ fontSize: "var(--text-xs)", color: "var(--status-green)", fontWeight: 600 }}>● Connected</span>
      ) : pending ? (
        <span style={{ fontSize: "var(--text-xs)", color: "var(--status-amber)", fontWeight: 600 }}>◌ Pending</span>
      ) : (
        <a
          href={connectHref}
          style={{
            fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--accent)", textDecoration: "none",
          }}
        >
          Connect →
        </a>
      )}
    </div>
  )
}
