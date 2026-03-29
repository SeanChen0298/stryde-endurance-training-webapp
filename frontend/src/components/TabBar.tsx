"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Home, Calendar, Heart, BarChart2, Settings } from "lucide-react"

const TABS = [
  { label: "Overview",  href: "/dashboard",              icon: Home },
  { label: "Training",  href: "/dashboard/training",     icon: Calendar },
  { label: "Health",    href: "/dashboard/health",       icon: Heart },
  { label: "Analysis",  href: "/dashboard/analysis",     icon: BarChart2 },
  { label: "Settings",  href: "/dashboard/settings",     icon: Settings },
]

export function TabBar() {
  const pathname = usePathname()

  return (
    <nav className="tab-bar" aria-label="Main navigation">
      {/* Logo — desktop only */}
      <Link href="/dashboard" className="tab-bar-logo" aria-label="Stryde home">
        <svg width="28" height="28" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect width="32" height="32" rx="8" fill="var(--accent)"/>
          <text x="16" y="23" fontFamily="Inter, -apple-system, sans-serif" fontSize="20" fontWeight="700" fill="white" textAnchor="middle">S</text>
        </svg>
        <span className="tab-bar-logo-text">Stryde</span>
      </Link>

      <div className="tab-bar-items">
        {TABS.map(({ label, href, icon: Icon }) => {
          const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href))
          return (
            <Link key={href} href={href} className={`tab-item ${active ? "active" : ""}`} aria-current={active ? "page" : undefined}>
              <Icon size={20} strokeWidth={active ? 2.5 : 1.75} />
              <span>{label}</span>
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
