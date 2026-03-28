"use client"

import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"

interface Props {
  children: React.ReactNode
  skeleton?: React.ReactNode
}

export function AIFeatureGate({ children, skeleton }: Props) {
  const { data: settings, isLoading } = useQuery({
    queryKey: ["settings", "gemini"],
    queryFn: api.settings.getGeminiStatus,
  })

  if (isLoading) {
    return (
      skeleton ?? (
        <div className="card" style={{ minHeight: 80 }}>
          <div className="skeleton" style={{ height: 16, width: "60%", marginBottom: 8 }} />
          <div className="skeleton" style={{ height: 12, width: "80%" }} />
        </div>
      )
    )
  }

  if (!settings?.connected) {
    return (
      <div
        className="card"
        style={{
          textAlign: "center",
          padding: "24px 16px",
          border: `1.5px dashed var(--gray-200)`,
          background: "transparent",
        }}
      >
        <p className="body-text" style={{ marginBottom: 12 }}>
          Add your Gemini API key to enable AI features
        </p>
        <Link
          href="/dashboard/settings#ai"
          style={{
            fontSize: "var(--text-sm)",
            fontWeight: 600,
            color: "var(--accent)",
            textDecoration: "none",
          }}
        >
          Set up in Settings →
        </Link>
      </div>
    )
  }

  return <>{children}</>
}
