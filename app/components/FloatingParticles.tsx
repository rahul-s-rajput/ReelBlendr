'use client'

import { useEffect, useState } from 'react'

interface Particle {
  id: number
  left: string
  top: string
  duration: string
}

export default function FloatingParticles() {
  const [particles, setParticles] = useState<Particle[]>([])
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
    const newParticles = Array.from({ length: 20 }).map((_, i) => ({
      id: i,
      left: `${Math.random() * 100}%`,
      top: `${Math.random() * 100}%`,
      duration: `${10 + Math.random() * 20}s`
    }))
    setParticles(newParticles)
  }, [])

  if (!mounted) return null // Prevent server-side rendering

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {particles.map((particle) => (
        <div
          key={particle.id}
          className="absolute w-2 h-2 bg-purple-400 rounded-full animate-float"
          style={{
            left: particle.left,
            top: particle.top,
            opacity: 0.2,
            animationDuration: particle.duration
          }}
        />
      ))}
    </div>
  )
}

