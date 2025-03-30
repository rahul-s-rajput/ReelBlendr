'use client';

import VideoCreationForm from './components/VideoCreationForm'
import DynamicBackground from './components/DynamicBackground'
import VideoPlayer from './components/VideoPlayer'
import { useState, useEffect } from 'react'

export default function Home() {
  const [outputVideoUrl, setOutputVideoUrl] = useState<string | null>(null);
  const [scrollY, setScrollY] = useState(0);

  useEffect(() => {
    const handleScroll = () => setScrollY(window.scrollY);
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

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

  return (
    <main className="min-h-screen relative overflow-hidden">
      <DynamicBackground scrollY={scrollY} />
      
      {/* Content */}
      <div className="relative z-10 max-w-7xl mx-auto py-12 px-4 sm:px-6 lg:px-8">
        <VideoCreationForm />
      </div>

      {outputVideoUrl && <VideoPlayer videoUrl={outputVideoUrl} isOutput={true} />}
    </main>
  )
}

