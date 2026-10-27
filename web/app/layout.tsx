import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Klatreforhold',
  description: 'Er fjellet tørt? Varsel time for time for klatrefelt i Bergen.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="nb">
      <body className="min-h-screen">
        <header className="bg-accent-surface-default text-accent-text-default">
          <div className="mx-auto flex max-w-container items-center justify-between px-md py-sm">
            <a href="/" className="text-lg font-medium">
              Klatreforhold
            </a>
            <span className="text-sm opacity-80">BKK · prototype</span>
          </div>
        </header>
        <main className="mx-auto max-w-container px-md py-lg">{children}</main>
        <footer className="mx-auto max-w-container px-md pb-lg text-xs text-text-subtle">
          Værdata fra MET Norway (CC BY 4.0) via Open-Meteo. Høydedata © Kartverket.
        </footer>
      </body>
    </html>
  )
}
