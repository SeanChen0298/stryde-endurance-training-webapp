export const THEMES = {
  ember: { name: "Ember", accent: "#F97316", accentLight: "#FED7AA", accentDim: "#C2410C" },
  cobalt: { name: "Cobalt", accent: "#3B82F6", accentLight: "#BFDBFE", accentDim: "#1D4ED8" },
  jade: { name: "Jade", accent: "#10B981", accentLight: "#A7F3D0", accentDim: "#047857" },
  violet: { name: "Violet", accent: "#8B5CF6", accentLight: "#DDD6FE", accentDim: "#6D28D9" },
  crimson: { name: "Crimson", accent: "#EF4444", accentLight: "#FEE2E2", accentDim: "#B91C1C" },
} as const

export type ThemeKey = keyof typeof THEMES

export function applyTheme(key: ThemeKey) {
  const t = THEMES[key]
  const root = document.documentElement
  root.style.setProperty("--accent", t.accent)
  root.style.setProperty("--accent-light", t.accentLight)
  root.style.setProperty("--accent-dim", t.accentDim)
  localStorage.setItem("theme", key)
}

export function loadSavedTheme() {
  if (typeof window === "undefined") return
  const saved = localStorage.getItem("theme") as ThemeKey | null
  if (saved && THEMES[saved]) applyTheme(saved)
}
