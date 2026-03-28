"use client"

import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Eye, EyeOff, CheckCircle, Loader2, Trash2 } from "lucide-react"
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
            <ServiceRow
              name="Garmin Connect"
              description="HRV, sleep, body battery"
              connected={profile?.garmin_connected ?? false}
              connectHref="/auth/garmin"
              pending={!profile?.garmin_connected}
            />
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
