"use client"

import { Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { CheckCircle, Clock, AlertCircle, ArrowRight } from "lucide-react"
import { motion } from "framer-motion"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { PageWrapper } from "@/components/PageWrapper"

export default function ConnectPage() {
  return (
    <Suspense>
      <ConnectPageInner />
    </Suspense>
  )
}

function ConnectPageInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const stravaParam = searchParams.get("strava")

  const { data: profile } = useQuery({ queryKey: ["me"], queryFn: api.auth.me })

  const stravaConnected = profile?.strava_connected || stravaParam === "connected"
  const garminConnected = profile?.garmin_connected ?? false

  function handleContinue() {
    router.push("/dashboard")
  }

  return (
    <PageWrapper>
      <div
        style={{
          minHeight: "100dvh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "24px 16px",
          background: "var(--gray-0)",
        }}
      >
        <div style={{ width: "100%", maxWidth: 400 }}>
          {/* Step indicator */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
              marginBottom: 32,
            }}
          >
            {[1, 2, 3].map((step) => (
              <div
                key={step}
                style={{
                  width: step === 2 ? 24 : 8,
                  height: 8,
                  borderRadius: 4,
                  background: step === 2 ? "var(--accent)" : "var(--gray-200)",
                  transition: "all 300ms ease",
                }}
              />
            ))}
          </div>

          <div style={{ marginBottom: 32 }}>
            <h1 style={{ fontSize: "var(--text-xl)", fontWeight: 600, color: "var(--gray-900)", marginBottom: 8 }}>
              Connect your data
            </h1>
            <p className="body-text">
              Connect Strava to import your training history. Garmin health data sync is optional.
            </p>
          </div>

          {/* Strava card */}
          <ServiceCard
            name="Strava"
            description="Activities, routes, segments, pace zones"
            pills={["Activities", "Pace", "Heart rate", "Segments", "Gear"]}
            connected={stravaConnected}
            connectHref="/auth/strava"
            accentColor="#FC4C02"
            logo={
              <svg width="24" height="24" viewBox="0 0 24 24" fill="#FC4C02">
                <path d="M15.387 17.944l-2.089-4.116h-3.065L15.387 24l5.15-10.172h-3.066m-7.008-5.599l2.836 5.599h4.172L10.463 0l-7 13.828h4.169" />
              </svg>
            }
          />

          {/* Garmin card */}
          <GarminCard connected={garminConnected} />

          {/* Continue */}
          {stravaConnected && (
            <motion.button
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="btn-primary"
              onClick={handleContinue}
              style={{ marginTop: 8, display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}
            >
              Continue to dashboard <ArrowRight size={16} />
            </motion.button>
          )}

          {!stravaConnected && (
            <p
              className="body-text"
              style={{ textAlign: "center", marginTop: 16, cursor: "pointer", color: "var(--accent)" }}
              onClick={handleContinue}
            >
              Connect Strava later →
            </p>
          )}

          <p className="body-text" style={{ textAlign: "center", marginTop: 16, fontSize: "var(--text-xs)", color: "var(--gray-400)" }}>
            Your data is stored privately and never shared.
          </p>
        </div>
      </div>
    </PageWrapper>
  )
}

function ServiceCard({
  name, description, pills, connected, connectHref, accentColor, logo,
}: {
  name: string
  description: string
  pills: string[]
  connected: boolean
  connectHref: string
  accentColor: string
  logo: React.ReactNode
}) {
  return (
    <div
      className="card"
      style={{
        marginBottom: 12,
        border: connected ? `1.5px solid var(--status-green)` : "1.5px solid var(--gray-100)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
        <div
          style={{
            width: 44, height: 44, borderRadius: 12,
            background: "#F5F5F5",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}
        >
          {logo}
        </div>
        <div style={{ flex: 1 }}>
          <div className="card-title">{name}</div>
          <div className="body-text" style={{ fontSize: "var(--text-xs)" }}>{description}</div>
        </div>
        {connected ? (
          <CheckCircle size={20} color="var(--status-green)" />
        ) : null}
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 16 }}>
        {pills.map((p) => (
          <span
            key={p}
            style={{
              background: "var(--gray-100)",
              color: "var(--gray-600)",
              fontSize: "var(--text-xs)",
              padding: "3px 8px",
              borderRadius: 6,
            }}
          >
            {p}
          </span>
        ))}
      </div>

      {connected ? (
        <div
          style={{
            fontSize: "var(--text-sm)",
            color: "var(--status-green)",
            fontWeight: 600,
          }}
        >
          ✓ Connected
        </div>
      ) : (
        <a
          href={connectHref}
          style={{
            display: "block",
            background: accentColor,
            color: "white",
            textAlign: "center",
            padding: "11px",
            borderRadius: 10,
            fontSize: "var(--text-sm)",
            fontWeight: 600,
            textDecoration: "none",
          }}
        >
          Connect {name}
        </a>
      )}
    </div>
  )
}

function GarminCard({ connected }: { connected: boolean }) {
  return (
    <div
      className="card"
      style={{
        marginBottom: 12,
        border: connected
          ? "1.5px solid var(--status-green)"
          : "1.5px solid var(--status-amber)",
        opacity: 0.9,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
        <div
          style={{
            width: 44, height: 44, borderRadius: 12,
            background: "#F0F7FF",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 20,
          }}
        >
          ⌚
        </div>
        <div style={{ flex: 1 }}>
          <div className="card-title">Garmin Connect</div>
          <div className="body-text" style={{ fontSize: "var(--text-xs)" }}>
            HRV, sleep, body battery, health metrics
          </div>
        </div>
        {!connected && <Clock size={18} color="var(--status-amber)" />}
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 16 }}>
        {["HRV", "Sleep stages", "Body battery", "Resting HR", "SpO₂", "Steps"].map((p) => (
          <span
            key={p}
            style={{
              background: "var(--gray-100)",
              color: "var(--gray-600)",
              fontSize: "var(--text-xs)",
              padding: "3px 8px",
              borderRadius: 6,
            }}
          >
            {p}
          </span>
        ))}
      </div>

      {!connected && (
        <div
          style={{
            background: "#FFFBEB",
            border: "1px solid #FDE68A",
            borderRadius: 8,
            padding: "10px 12px",
            fontSize: "var(--text-xs)",
            color: "#92400E",
            display: "flex",
            gap: 8,
            alignItems: "flex-start",
          }}
        >
          <AlertCircle size={14} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>
            Garmin Developer API approval is pending (typically 2 business days).
            You can connect it later in Settings.
          </span>
        </div>
      )}
    </div>
  )
}
