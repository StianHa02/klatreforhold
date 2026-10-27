import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  // Standalone is for Docker; Vercel's build adapter needs the default output.
  output: process.env.VERCEL ? undefined : 'standalone',
}

export default nextConfig
