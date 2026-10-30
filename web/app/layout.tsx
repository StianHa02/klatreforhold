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
          <div className="mx-auto flex max-w-container items-center justify-between gap-md px-md py-[12px] lg:px-lg">
            <a href="/" className="focus flex items-center gap-sm rounded-sm">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/mark.svg" alt="" width={18} height={24} className="h-lg w-auto" />
              <span className="font-mabry text-xl leading-none">Klatreforhold</span>
            </a>
            <nav aria-label="Hovedmeny" className="flex items-center gap-md text-sm">
              <a href="/" className="focus rounded-sm decoration-2 underline-offset-4 hover:underline">Felt</a>
              <a href="/om" className="focus rounded-sm decoration-2 underline-offset-4 hover:underline">Om varselet</a>
            </nav>
          </div>
        </header>
        <main id="main" className="mx-auto w-full max-w-innhold grow px-md py-lg">
          {children}
        </main>
        <footer className="bg-accent-surface-default text-accent-text-default">
          <div className="mx-auto flex max-w-container flex-col gap-md px-md py-lg text-sm sm:flex-row sm:items-end sm:justify-between lg:px-lg">
            <div className="flex flex-col gap-[2px]">
              <span className="flex items-center gap-sm font-mabry text-md">
                Klatreforhold
                <span className="rounded-sm border border-current px-[6px] font-sans text-xs opacity-80">prototype</span>
              </span>
              <span className="opacity-80">Et prosjekt fra Bergen Klatreklubb</span>
            </div>
            <p className="flex flex-col gap-[2px] opacity-80 sm:text-right">
              <span>Værdata: MET Norway, direkte og via Open-Meteo (CC BY 4.0)</span>
              <span>Høydedata: © Kartverket</span>
            </p>
          </div>
        </footer>
      </body>
    </html>
  )
}
