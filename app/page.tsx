'use client';

import VideoCreationForm from './components/VideoCreationForm'
import FloatingParticles from './components/FloatingParticles'
import VideoPlayer from './components/VideoPlayer'
import { useState, useEffect } from 'react'

export default function Home() {
  const [outputVideoUrl, setOutputVideoUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  
  const handleCreateVideo = async () => {
    try {
      const response = await fetch('/api/create-video', {
        // ... your fetch options
      });
      const data = await response.json();
      
      if (data.status === 'success') {
        setOutputVideoUrl(data.video_url);
      }
    } catch (error) {
      console.error('Error:', error);
    }
  };

  useEffect(() => {
    setLoading(true);
  }, []);

  return (
    <main className="min-h-screen relative overflow-hidden bg-gradient-to-br from-gray-900 via-purple-900 to-indigo-900">
      {/* Video Frames Pattern */}
      <div className="absolute inset-0 opacity-10">
        <svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
          <pattern id="video-frames" x="0" y="0" width="100" height="100" patternUnits="userSpaceOnUse">
            <rect x="10" y="10" width="80" height="60" fill="none" stroke="white" strokeWidth="1"/>
            <rect x="15" y="15" width="70" height="50" fill="none" stroke="white" strokeWidth="0.5"/>
          </pattern>
          <rect x="0" y="0" width="100%" height="100%" fill="url(#video-frames)" />
        </svg>
      </div>

      {/* Timeline Pattern */}
      <div 
        className="absolute inset-0 opacity-5"
        style={{
          backgroundImage: `
            repeating-linear-gradient(
              90deg,
              white 0px,
              white 2px,
              transparent 2px,
              transparent 20px
            )
          `,
          backgroundSize: '100px 100%'
        }}
      />

      <FloatingParticles />

      {/* Content */}
      <div className="relative z-10 max-w-7xl mx-auto py-12 px-4 sm:px-6 lg:px-8">
        
        <VideoCreationForm />
      </div>

      {/* Original video player */}
      {outputVideoUrl && <VideoPlayer videoUrl={outputVideoUrl} isOutput={true} />}
    </main>
  )
}

