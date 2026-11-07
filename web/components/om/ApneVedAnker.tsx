'use client'

import { useEffect } from 'react'

// Seksjonene på «Om modellen» er lukket fra start. Lenker som /om#data skal likevel vise innholdet:
// åpner den lukkede seksjonen ankeret peker på (eller ligger i), og ruller dit.
export default function ApneVedAnker() {
  useEffect(() => {
    const apne = () => {
      const id = decodeURIComponent(location.hash.slice(1))
      const mal = id ? document.getElementById(id) : null
      const seksjon = mal?.closest('details')
      if (!mal || !seksjon) return
      seksjon.open = true
      mal.scrollIntoView()
    }
    apne()
    window.addEventListener('hashchange', apne)
    return () => window.removeEventListener('hashchange', apne)
  }, [])
  return null
}
