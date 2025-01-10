import React from 'react'
import { motion } from 'framer-motion'
import { Camera, Music, Clapperboard, Share } from 'lucide-react'

interface DynamicBackgroundProps {
  scrollY: number
}

const DynamicBackground: React.FC<DynamicBackgroundProps> = ({ scrollY }) => {
  return (
    <div className="fixed inset-0 z-0 overflow-hidden">
      

      {/* Floating icons */}
      <motion.div
        className="absolute inset-0"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 1 }}
      >
        {[Camera, Music, Clapperboard, Share].map((Icon, index) => (
          <motion.div
            key={index}
            className="absolute text-purple-300 opacity-20"
            style={{
              left: index % 2 === 0 ? '10%' : '80%',
              top: index < 2 ? '15%' : '75%',
            }}
            animate={{
              y: [0, -20, 0],
              rotate: [0, 10, -10, 0],
            }}
            transition={{
              duration: 5,
              repeat: Infinity,
              delay: index,
            }}
          >
            <Icon size={48} />
          </motion.div>
        ))}
      </motion.div>

      {/* Animated lines representing video timeline */}
      <div className="absolute inset-x-0 bottom-0 h-20 flex items-end overflow-hidden">
        {[...Array(20)].map((_, i) => (
          <motion.div
            key={i}
            className="w-4 bg-purple-400 opacity-20 mx-1"
            initial={{ height: 0 }}
            animate={{ height: [0, 40, 0] }}
            transition={{
              duration: 2,
              repeat: Infinity,
              delay: i * 0.1,
            }}
          />
        ))}
      </div>

      {/* Particle effect */}
      {[...Array(50)].map((_, i) => (
        <motion.div
          key={i}
          className="absolute w-2 h-2 bg-pink-400 rounded-full"
          style={{
            left: `${Math.random() * 100}%`,
            top: `${Math.random() * 100}%`,
          }}
          animate={{
            y: [0, -30, 0],
            opacity: [0, 1, 0],
          }}
          transition={{
            duration: 3,
            repeat: Infinity,
            delay: i * 0.1,
          }}
        />
      ))}

      {/* Gradient overlay */}
      <div
        className="absolute inset-0 bg-gradient-to-b from-transparent to-gray-900 opacity-80"
        style={{ transform: `translateY(${scrollY * 0.5}px)` }}
      />
    </div>
  )
}

export default DynamicBackground

