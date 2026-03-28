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
      {TABS.map(({ label, href, icon: Icon }) => {
        const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href))
        return (
          <Link key={href} href={href} className={`tab-item ${active ? "active" : ""}`} aria-current={active ? "page" : undefined}>
            <Icon size={20} strokeWidth={active ? 2.5 : 1.75} />
            <span>{label}</span>
          </Link>
        )
      })}
    </nav>
  )
}
