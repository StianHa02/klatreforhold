'use client'

import { useEffect, useRef, useState } from 'react'

// Info-ikon med en forklaring som vises når musa er over, når ikonet har fokus (tastatur), eller etter trykk.
// Trykk må styres med state: Safari på iOS gir ikke knapper fokus ved trykk, så :focus-within slår aldri inn der.
// Trykk utenfor eller Escape lukker.
// Ikonet er informationCircle fra Heroicons, i samme strekstil som pilene i Ukerutenett.
export default function Info({ children }: { children: string }) {
  const [apen, setApen] = useState(false)
  const ref = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    if (!apen) return
    const utenfor = (e: PointerEvent) => {
      if (!ref.current?.contains(e.target as Node)) setApen(false)
    }
    const escape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setApen(false)
    }
    document.addEventListener('pointerdown', utenfor)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('pointerdown', utenfor)
      document.removeEventListener('keydown', escape)
    }
  }, [apen])

  return (
    <span ref={ref} className="group/info relative inline-flex">
      <button
        type="button"
        aria-label={children}
        aria-expanded={apen}
        onClick={() => setApen((v) => !v)}
        className="focus cursor-help rounded-full text-text-subtle hover:text-text-default"
      >
        <svg aria-hidden viewBox="0 0 24 24" width={18} height={18} fill="none" stroke="currentColor" strokeWidth={1.5}>
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="m11.25 11.25.041-.02a.75.75 0 0 1 1.063.852l-.708 2.836a.75.75 0 0 0 1.063.853l.041-.021M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9-3.75h.008v.008H12V8.25Z"
          />
        </svg>
      </button>
      <span
        aria-hidden
        className={`${apen ? 'visible' : 'invisible'} absolute top-full left-1/2 z-10 mt-xs w-max max-w-[min(16rem,calc(100vw-2rem))] -translate-x-1/2 rounded-sm bg-accent-surface-default px-sm py-xs text-sm text-accent-text-default shadow-sm group-focus-within/info:visible group-hover/info:visible`}
      >
        {children}
      </span>
    </span>
  )
}
