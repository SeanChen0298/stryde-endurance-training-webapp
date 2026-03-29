"use client"

import { useEffect } from "react"
import { QueryClientProvider } from "@tanstack/react-query"
import { AnimatePresence } from "framer-motion"
import { queryClient } from "@/lib/queryClient"
import { loadSavedTheme } from "@/lib/theme"
import "@/styles/globals.css"

export default function RootLayout({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    loadSavedTheme()
  }, [])

  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Stryde</title>
        <meta name="description" content="Endurance training platform" />
        <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <QueryClientProvider client={queryClient}>
          <AnimatePresence mode="wait">
            {children}
          </AnimatePresence>
        </QueryClientProvider>
      </body>
    </html>
  )
}
