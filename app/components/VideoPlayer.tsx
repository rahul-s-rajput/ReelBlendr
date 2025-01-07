'use client'

import { Button } from '../ui/button'
import { Play, Download } from 'lucide-react'
import { useState } from 'react'

interface VideoPlayerProps {
  videoUrl: string
  isOutput?: boolean
}

export default function VideoPlayer({ videoUrl, isOutput = false }: VideoPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false)
  const fullVideoUrl = videoUrl.startsWith('http') 
    ? videoUrl 
    : `http://127.0.0.1:5000${videoUrl}`

  console.log('Video URL:', fullVideoUrl)

  return (
    <div className="mt-8 space-y-4">
      <h2 className="text-2xl font-bold text-gray-800 mb-4">
        {isOutput ? "Generated Video" : "Your Reel"}
      </h2>
      <div className="relative aspect-w-16 aspect-h-9 bg-gray-100 rounded-lg overflow-hidden group">
        <video 
          className="w-full h-full object-cover" 
          controls={isOutput}
          preload="metadata"
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          onEnded={() => setIsPlaying(false)}
        >
          <source src={fullVideoUrl} type="video/mp4" />
          Your browser does not support the video tag.
        </video>
        {!isOutput && !isPlaying && (
          <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-300">
            <Button
              className="bg-electric-blue hover:bg-electric-blue-dark text-white rounded-full p-4"
              onClick={() => {
                const video = document.querySelector('video')
                if (video) {
                  video.play()
                  setIsPlaying(true)
                }
              }}
            >
              <Play className="h-8 w-8" />
            </Button>
          </div>
        )}
      </div>
      <div className="flex justify-center">
        <Button
          className="mt-4 bg-coral hover:bg-coral-dark text-white px-6 py-3 rounded-full flex items-center space-x-2"
          onClick={() => window.open(fullVideoUrl, '_blank')}
        >
          <Download className="h-5 w-5" />
          <span>Download {isOutput ? "Generated Video" : "Reel"}</span>
        </Button>
      </div>
    </div>
  )
}

