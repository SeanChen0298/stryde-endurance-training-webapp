"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Eye, EyeOff } from "lucide-react"
import { motion } from "framer-motion"
import { api, APIError } from "@/lib/api"

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await api.auth.login(email, password)
      router.push("/dashboard")
    } catch (err) {
      if (err instanceof APIError) {
        setError(err.message)
      } else {
        setError("Something went wrong. Please try again.")
      }
    } finally {
      setLoading(false)
    }
  }

  return (
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
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.22, ease: "easeOut" }}
        style={{ width: "100%", maxWidth: 400 }}
      >
        {/* Brand mark */}
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <svg width="52" height="52" viewBox="0 0 52 52" fill="none" style={{ marginBottom: 12 }}>
            <circle cx="26" cy="26" r="25" stroke="var(--accent)" strokeWidth="2" fill="var(--accent-light)" />
            <path
              d="M16 36 L22 20 L28 30 L32 24 L38 36"
              stroke="var(--accent)"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              fill="none"
            />
          </svg>
          <div style={{ fontSize: "var(--text-xl)", fontWeight: 600, color: "var(--gray-900)" }}>Stryde</div>
          <div className="body-text" style={{ marginTop: 4 }}>Endurance Training Platform</div>
        </div>

        {/* Login card */}
        <div
          className="card"
          style={{
            boxShadow: "0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04)",
          }}
        >
          <h1
            style={{
              fontSize: "var(--text-lg)",
              fontWeight: 600,
              color: "var(--gray-900)",
              marginBottom: 24,
              marginTop: 0,
            }}
          >
            Sign in
          </h1>

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <label
                htmlFor="email"
                className="metric-label"
                style={{ display: "block", marginBottom: 6 }}
              >
                Email
              </label>
              <input
                id="email"
                type="email"
                className="input"
                placeholder="faiz@example.my"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="metric-label"
                style={{ display: "block", marginBottom: 6 }}
              >
                Password
              </label>
              <div style={{ position: "relative" }}>
                <input
                  id="password"
                  type={showPw ? "text" : "password"}
                  className="input"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                  style={{ paddingRight: 48 }}
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  style={{
                    position: "absolute",
                    right: 14,
                    top: "50%",
                    transform: "translateY(-50%)",
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    color: "var(--gray-400)",
                    padding: 4,
                    display: "flex",
                    alignItems: "center",
                  }}
                  aria-label={showPw ? "Hide password" : "Show password"}
                >
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {error && (
              <motion.div
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                style={{
                  background: "#FEF2F2",
                  border: "1px solid #FECACA",
                  borderRadius: 8,
                  padding: "10px 12px",
                  fontSize: "var(--text-sm)",
                  color: "#B91C1C",
                }}
              >
                {error}
              </motion.div>
            )}

            <button
              type="submit"
              className="btn-primary"
              disabled={loading}
              style={{ marginTop: 8 }}
            >
              {loading ? "Signing in…" : "Sign in"}
            </button>
          </form>
        </div>
      </motion.div>
    </div>
  )
}
