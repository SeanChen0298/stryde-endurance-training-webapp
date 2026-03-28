"use client"

import { motion } from "framer-motion"

const pageVariants = {
  initial:  { opacity: 0, y: 16 },
  animate:  { opacity: 1, y: 0, transition: { duration: 0.22, ease: "easeOut" } },
  exit:     { opacity: 0, y: -8, transition: { duration: 0.15 } },
}

export function PageWrapper({ children }: { children: React.ReactNode }) {
  return (
    <motion.div variants={pageVariants} initial="initial" animate="animate" exit="exit">
      {children}
    </motion.div>
  )
}
