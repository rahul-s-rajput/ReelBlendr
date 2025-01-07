'use client'

import { useState } from 'react'
import { Button } from '../ui/button'
import { Card, CardContent } from '../ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip'
import NumberInput from './inputs/NumberInput'
import TextInput from './inputs/TextInput'
import StyleSelector from './inputs/StyleSelector'
import DropdownInput from './inputs/DropdownInput'
import FileUploadInput from './inputs/FileUploadInput'
import SpotifyInput from './inputs/SpotifyInput'
import VideoPlayer from './VideoPlayer'
import LoadingAnimation from './LoadingAnimation'
import LoadingOverlay from './LoadingOverlay'
import { motion } from 'framer-motion'

interface Track {
  id: string
  name: string
  artist: string
  duration_ms: number
  external_url: string
  view_count: number
  videoId: string
}

export default function VideoCreationForm() {
  const [formData, setFormData] = useState({
    targetDuration: 30,
    contentFocus: '',
    keyLabels: '',
    stylePreference: 'Smooth/Cinematic',
    moodTone: 'Chill',
    orderPreference: 'AI-determined',
    excludedContent: '',
    audioOption: 'No Audio',
    spotifyTrack: '',
    uploadedVideos: [] as File[],
  })

  const [generatedVideoUrl, setGeneratedVideoUrl] = useState('')
  const [error, setError] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const [musicRecommendations, setMusicRecommendations] = useState<Track[]>([])
  const [musicError, setMusicError] = useState('')
  const [isMusicLoading, setIsMusicLoading] = useState(false)
  const [loadingMessage, setLoadingMessage] = useState('')

  const handleInputChange = (name: string, value: any) => {
    setFormData((prev) => {
      const newData = { ...prev, [name]: value }
      
      // If spotifyTrack is set/cleared, update audioOption accordingly
      if (name === 'spotifyTrack') {
        newData.audioOption = value ? 'Use Selected Track' : 'No Audio'
      }
      
      return newData
    })
  }

  const analyzeAudio = async (trackName: string, artist: string) => {
    try {
      const response = await fetch('/api/analyze-audio', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          trackName,
          artist,
          targetDuration: formData.targetDuration || 30000 // in milliseconds
        }),
      });

      const data = await response.json();
      if (!data.success) {
        throw new Error(data.error);
      }

      console.log('Audio analysis:', data.analysis);
      return data.analysis;
    } catch (error) {
      console.error('Error analyzing audio:', error);
      throw error;
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsProcessing(true);
    setLoadingMessage('Creating your video...');
    setError('');

    try {
      // Debug log to check the files
      console.log('Current uploaded videos:', formData.uploadedVideos);
      
      // More detailed check for uploaded videos
      if (!formData.uploadedVideos || !Array.isArray(formData.uploadedVideos) || formData.uploadedVideos.length === 0) {
        throw new Error('Please upload at least one video.');
      }

      // Verify that all items in uploadedVideos are valid File objects
      const validFiles = formData.uploadedVideos.every(file => file instanceof File);
      if (!validFiles) {
        throw new Error('Invalid file data. Please try uploading your videos again.');
      }

      const formDataToSend = new FormData();
      
      // Log the files being sent
      console.log('Sending files:', formData.uploadedVideos);
      
      Object.entries(formData).forEach(([key, value]) => {
        if (key === 'uploadedVideos' && Array.isArray(value)) {
          value.forEach((file: File) => {
            formDataToSend.append('videos', file);
          });
        } else {
          formDataToSend.append(key, value.toString());
        }
      });

      // Log what's actually being sent
      console.log('FormData entries:', Array.from(formDataToSend.entries()));

      const response = await fetch('/api/create-video', {
        method: 'POST',
        body: formDataToSend,
      });

      const data = await response.json()
      
      if (data.status !== 'success') {
        throw new Error(data.message || 'Failed to create video')
      }

      setGeneratedVideoUrl(data.video_url)
      
      // Log audio analysis results if available
      if (data.audioAnalysis) {
        console.log('Audio analysis results:', data.audioAnalysis)
        console.log('Tempo:', data.audioAnalysis.analysis.tempo)
        console.log('Number of beats:', data.audioAnalysis.analysis.beat_times.length)
        console.log('Energy profile:', data.audioAnalysis.analysis.energy_profile)
      }

    } catch (error) {
      console.error('Error:', error)
      setError(error instanceof Error ? error.message : 'An error occurred while creating the video.')
    } finally {
      setIsProcessing(false);
      setLoadingMessage('');
    }
  }

  const validateMusicUrl = (url: string) => {
    if (!url) return true; // Optional field
    
    // YouTube Music URL patterns
    const ytMusicPatterns = [
      /^https:\/\/music\.youtube\.com\/watch\?v=[\w-]+$/,
      /^https:\/\/www\.youtube\.com\/watch\?v=[\w-]+$/,
      /^https:\/\/youtu\.be\/[\w-]+$/
    ];
    
    return ytMusicPatterns.some(pattern => pattern.test(url));
  };

  const validateForm = () => {
    const errors: { [key: string]: string } = {};
    
    if (formData.targetDuration < 5 || formData.targetDuration > 300) {
      errors.targetDuration = 'Duration must be between 5 and 300 seconds';
    }

    if (!formData.contentFocus) {
      errors.contentFocus = 'Content focus is required';
    }

    if (!formData.keyLabels) {
      errors.keyLabels = 'Key labels are required';
    }

    if (!formData.stylePreference) {
      errors.stylePreference = 'Style preference is required';
    }

    if (!formData.moodTone) {
      errors.moodTone = 'Mood/tone is required';
    }

    if (formData.audioOption === 'spotify' && !formData.spotifyTrack) {
      errors.spotifyTrack = 'Please select a Spotify track';
    }

    if (!formData.uploadedVideos || formData.uploadedVideos.length === 0) {
      errors.uploadedVideos = 'Please upload at least one video';
    }

    return errors;
  };

  return (
    <div className="min-h-screen relative">
      <div className="fixed inset-0 overflow-hidden z-0">
        <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-blue-900/50 to-purple-900/50"></div>
        
        {[...Array(5)].map((_, i) => (
          <motion.div
            key={i}
            className={`absolute inset-0 opacity-20`}
            animate={{
              y: [-20, 20],
              scaleY: [0.8, 1.2],
            }}
            transition={{
              duration: 3 + i,
              repeat: Infinity,
              repeatType: "reverse",
              ease: "easeInOut",
              delay: i * 0.3,
            }}
          >
            <div 
              className="h-[200px] w-full absolute top-1/2 transform -translate-y-1/2"
              style={{
                background: `linear-gradient(90deg, 
                  transparent 0%,
                  ${i % 2 ? 'rgba(147, 51, 234, 0.3)' : 'rgba(59, 130, 246, 0.3)'} 50%,
                  transparent 100%)`,
                filter: 'blur(40px)',
              }}
            />
          </motion.div>
        ))}

        {[...Array(10)].map((_, i) => (
          <motion.div
            key={`particle-${i}`}
            className="absolute w-4 h-4 rounded-full bg-white/10"
            style={{
              left: `${Math.random() * 100}%`,
              top: `${Math.random() * 100}%`,
            }}
            animate={{
              y: [-20, 20],
              x: [-20, 20],
              scale: [0.8, 1.2],
              opacity: [0.3, 0.6],
            }}
            transition={{
              duration: 4 + Math.random() * 6,
              repeat: Infinity,
              repeatType: "reverse",
              ease: "easeInOut",
            }}
          />
        ))}

        <div className="absolute inset-0 opacity-5">
          <div className="h-full w-full bg-[url('/filmstrip-pattern.svg')] bg-repeat bg-[length:100px_100px] animate-slide"></div>
        </div>



        <motion.div
          animate={{
            rotate: [0, 10, -10, 0],
          }}
          transition={{
            duration: 4,
            repeat: Infinity,
            ease: "easeInOut",
          }}
          className="absolute top-20 right-40"
        >
          <svg
            className="w-24 h-24 text-white"
            viewBox="0 0 32 32"
            xmlns="http://www.w3.org/2000/svg"
          >
            <rect
              x="4"
              y="8"
              width="16"
              height="12"
              rx="2"
              ry="2"
              fill="currentColor"
            />
           
            <circle cx="20" cy="14" r="4" fill="currentColor" />
            <circle cx="20" cy="14" r="2.5" fill="black" />
            
            <circle cx="8" cy="10" r="1.5" fill="red" />
    
            <rect
              x="22"
              y="10"
              width="2"
              height="8"
              rx="1"
              ry="1"
              fill="currentColor"
            />
          
          </svg>
        </motion.div>
        

        <div className="absolute top-1/4 -left-10 w-40 h-40 bg-blue-500/30 rounded-full blur-3xl"></div>
        <div className="absolute bottom-1/4 -right-10 w-40 h-40 bg-purple-500/30 rounded-full blur-3xl"></div>
          
      </div>

      <div className="relative z-10">
        <div className="text-center mb-12">
          <h1 className="text-6xl font-extrabold">
            <span className="bg-gradient-to-r from-purple-400 to-purple-600 text-transparent bg-clip-text">
              Reel
            </span>
            <span className="text-white">
              Blendr
            </span>
          </h1>
          <p className="text-xl text-purple-200 mt-4">
            Blend your moments into captivating reels
          </p>
        </div>

        {(isProcessing || isMusicLoading) && (
          <LoadingOverlay message={loadingMessage || 'Getting music recommendations...'} />
        )}
        <Card className="bg-white/90 backdrop-blur-lg border-gray-200/50 rounded-xl overflow-hidden shadow-2xl">
          <CardContent className="p-6">
            <form onSubmit={handleSubmit}>
              <Tabs defaultValue="upload" className="w-full">
                <TabsList className="grid w-full grid-cols-3 mb-6">
                  <TabsTrigger value="upload">Upload</TabsTrigger>
                  <TabsTrigger value="style">Style</TabsTrigger>
                  <TabsTrigger value="audio">Audio</TabsTrigger>
                </TabsList>
                <TabsContent value="upload" className="space-y-6">
                  <FileUploadInput
                    label="Upload Videos"
                    name="uploadedVideos"
                    value={formData.uploadedVideos}
                    onChange={handleInputChange}
                  />
                  <NumberInput
                    label="Target Duration (seconds)"
                    name="targetDuration"
                    value={formData.targetDuration}
                    onChange={handleInputChange}
                    min={5}
                    max={300}
                    step={5}
                  />
                </TabsContent>
                <TabsContent value="style" className="space-y-6">
                  <TextInput
                    label="Content Focus"
                    name="contentFocus"
                    value={formData.contentFocus}
                    onChange={handleInputChange}
                    placeholder="Example: People enjoying outdoor activities"
                    required
                  />
                  <TextInput
                    label="Key Labels & Emphasis"
                    name="keyLabels"
                    value={formData.keyLabels}
                    onChange={handleInputChange}
                    placeholder="Example: Smiling faces, laughter, group activities, sunset views"
                    required
                  />
                  <StyleSelector
                    label="Style Preference"
                    name="stylePreference"
                    value={formData.stylePreference}
                    onChange={handleInputChange}
                    options={["Fast-paced", "Smooth/Cinematic", "Documentary"]}
                  />

                  <DropdownInput
                    label="Order Preference"
                    name="orderPreference"
                    value={formData.orderPreference}
                    onChange={handleInputChange}
                    options={["Chronological", "AI-determined"]}
                  />
                  <TextInput
                    label="Excluded Content"
                    name="excludedContent"
                    value={formData.excludedContent}
                    onChange={handleInputChange}
                    placeholder="Example: Violence, inappropriate content, blurry footage"
                  />
                </TabsContent>
                <TabsContent value="audio" className="space-y-6">
                <DropdownInput
                    label="Music Mood"
                    name="moodTone"
                    value={formData.moodTone}
                    onChange={handleInputChange}
                    options={["Chill", "Commute", "Energy Boosters", "Feel Good", "Focus", "Party", "Romance", "Sad", "Workout"]}
                  />
                  <SpotifyInput
                    value={formData.spotifyTrack}
                    onChange={(value) => handleInputChange('spotifyTrack', value)}
                    formData={formData}
                    handleInputChange={handleInputChange}
                    recommendations={musicRecommendations}
                    setRecommendations={setMusicRecommendations}
                    error={musicError}
                    setError={setMusicError}
                    isLoading={isMusicLoading}
                    setIsLoading={setIsMusicLoading}
                  />
                </TabsContent>
              </Tabs>
              {error && <p className="text-red-500 mt-4">{error}</p>}
              <div className="mt-8 flex justify-center">
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button type="submit" className="w-64 h-12 bg-gradient-to-r from-coral to-electric-blue hover:from-coral-dark hover:to-electric-blue-dark text-white text-lg font-semibold rounded-full shadow-lg transition-all duration-300 ease-in-out transform hover:scale-105" disabled={isProcessing}>
                        {isProcessing ? <LoadingAnimation /> : 'Create Reel'}
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>Click to blend your videos and create a captivating reel!</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
            </form>
            {generatedVideoUrl && <VideoPlayer videoUrl={generatedVideoUrl} />}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

