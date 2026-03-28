import type { Config } from "tailwindcss"

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      // Design tokens are handled via CSS custom properties in globals.css
      // Tailwind is used for layout, spacing, and utility classes only
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "sans-serif"],
      },
      maxWidth: {
        content: "480px",
        "content-desktop": "900px",
      },
    },
  },
  plugins: [],
}

export default config
