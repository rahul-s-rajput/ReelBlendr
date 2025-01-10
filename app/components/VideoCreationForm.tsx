'use client'

import { useState, useRef } from 'react'
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
    moodTone: 'Calm',
    genre: 'Alternative',
    orderPreference: 'AI-determined',
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
  const [showError, setShowError] = useState(false)

  const videoPlayerRef = useRef<HTMLDivElement>(null)

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
    setShowError(false);
    setGeneratedVideoUrl('');

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

      // Set new video URL which will trigger re-render of VideoPlayer
      setGeneratedVideoUrl(data.video_url)
      
      // Add this scroll behavior after setting the video URL
      setTimeout(() => {
        videoPlayerRef.current?.scrollIntoView({ 
          behavior: 'smooth',
          block: 'center'
        })
      }, 100)

      // Log audio analysis results if available
      if (data.audioAnalysis) {
        console.log('Audio analysis results:', data.audioAnalysis)
        console.log('Tempo:', data.audioAnalysis.analysis.tempo)
        console.log('Number of beats:', data.audioAnalysis.analysis.beat_times.length)
        console.log('Energy profile:', data.audioAnalysis.analysis.energy_profile)
      }

    } catch (error) {
      console.error('Error:', error);
      setError(error instanceof Error ? error.message : 'An error occurred while creating the video.');
      setShowError(true);
      setTimeout(() => setShowError(false), 5000);
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
                </TabsContent>
                <TabsContent value="audio" className="space-y-6">
                <DropdownInput
                    label="Music Mood"
                    name="moodTone"
                    value={formData.moodTone}
                    onChange={handleInputChange}
                    options={["Calm", "Chill", "Commute", "Energy Boosters", "Feel Good", "Party", "Romance", "Sad", "Workout"]}
                  />
                  <DropdownInput
                    label="Music Genre"
                    name="genre"
                    value={formData.genre}
                    onChange={handleInputChange}
                    options={["Alternative", "Blues", "Bollywood", "Classical", "Country", "Electronic", "Folk", "Funk", "Hip-hop", "Indie", "Instrumental", "Jazz", "Latin", "Metal", "Pop", "Punk", "Rap", "Reggae", "Rock", "Soul", "World"]}
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
              {error && showError && (
                <p className="text-red-500 mt-4 transition-opacity duration-300">
                  {error}
                </p>
              )}
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
            {generatedVideoUrl && (
              <div ref={videoPlayerRef}>
                <VideoPlayer 
                  key={generatedVideoUrl} 
                  videoUrl={generatedVideoUrl} 
                  isOutput={true} 
                />
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

