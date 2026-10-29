'use client'

import { type ReactNode, useEffect, useRef } from 'react'

// Rullbar beholder som starter helt til høyre ("nå"), så mobilen viser de siste timene først.
export default function HistorikkScroll({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (ref.current) ref.current.scrollLeft = ref.current.scrollWidth
  }, [])
  return (
    <div ref={ref} className="min-w-0 flex-1 overflow-x-auto" tabIndex={0} aria-label="Timeverdier, rull sideveis">
      {children}
    </div>
  )
}
