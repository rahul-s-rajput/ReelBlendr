import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  reactStrictMode: false,  // Disable strict mode in development
  webpack: (config) => {
    // Reduce hot reloading overhead
    config.watchOptions = {
      poll: false,
      ignored: ['**/node_modules', '**/.git']
    }
    return config
  },
  // Optimize image handling
  images: {
    domains: ['localhost'],
    unoptimized: true
  },
  // Reduce development overhead
  swcMinify: true,
  poweredByHeader: false
}

export default nextConfig
