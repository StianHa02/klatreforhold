import type { Metadata, Viewport } from 'next'
import { Work_Sans } from 'next/font/google'
import localFont from 'next/font/local'
import './globals.css'

export const metadata: Metadata = {
  title: 'Klatreforhold',
  description: 'Er fjellet tørt? Varsel time for time for klatrefelt i Bergen.',
}

export const viewport: Viewport = {
  themeColor: '#ffffff',
  viewportFit: 'cover',
}

// Samme fonter som BKK nettfører: Work Sans til brødtekst, Mabry til titler.
const workSans = Work_Sans({
  subsets: ['latin'],
  variable: '--font-work-sans',
})

const mabry = localFont({
  src: [
    { path: '../public/fonts/mabry-regular-pro.woff2', weight: '400', style: 'normal' },
    { path: '../public/fonts/mabry-bold-pro.woff2', weight: '700', style: 'normal' },
    { path: '../public/fonts/mabry-italic-pro.woff2', weight: '400', style: 'italic' },
    { path: '../public/fonts/mabry-bold-italic-pro.woff2', weight: '700', style: 'italic' },
  ],
  display: 'swap',
  variable: '--font-mabry',
})

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="nb" className={`${workSans.variable} ${mabry.variable} font-sans scroll-smooth`}>
      <body className="flex min-h-screen flex-col">
        <header className="sticky top-0 z-20 border-b border-border-subtle bg-surface-default">
          <a
            className="focus sr-only z-40 px-xs focus:not-sr-only focus:absolute focus:top-sm focus:bg-background-tinted"
            href="#main"
          >
            Hopp til innhold
          </a>
          <div className="mx-auto flex max-w-container items-center justify-between gap-md px-md py-[12px]">
            <a href="/" className="focus flex items-center gap-sm rounded-sm">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/mark.svg" alt="" width={18} height={24} className="h-lg w-auto" />
              <span className="font-mabry text-xl leading-none">Klatreforhold</span>
            </a>
            <span className="byline">BKK · prototype</span>
          </div>
        </header>
        <main id="main" className="mx-auto w-full max-w-container grow px-md py-lg">
          {children}
        </main>
        <footer className="bg-accent-surface-default text-accent-text-default">
          <div className="mx-auto flex max-w-container flex-col gap-xs px-md py-lg text-sm">
            <span className="font-mabry">Klatreforhold · Bergen Klatreklubb</span>
            <span className="opacity-80">
              Værdata fra MET Norway (CC BY 4.0) via Open-Meteo. Høydedata © Kartverket.
            </span>
          </div>
        </footer>
      </body>
    </html>
  )
}
