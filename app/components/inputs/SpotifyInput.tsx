import { useState, useEffect } from 'react'
import { Input } from '../../ui/input'
import { Button } from '../../ui/button'
import { Label } from '../../ui/label'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../../ui/tooltip'

interface Track {
  id: string
  name: string
  artist: string
  duration_ms: number
  external_url: string
  view_count: number
  videoId: string  // Added for YouTube Music
}

interface MusicInputProps {
  value: string
  onChange: (value: string) => void
  formData: {
    contentFocus: string
    keyLabels: string
    stylePreference: string
    moodTone: string
    targetDuration: number
    genre: string
  }
  handleInputChange: (name: string, value: string) => void
  recommendations: Track[]
  setRecommendations: (tracks: Track[]) => void
  error: string
  setError: (error: string) => void
  isLoading: boolean
  setIsLoading: (loading: boolean) => void
}

export default function MusicInput({ 
  value, 
  onChange, 
  formData, 
  handleInputChange,
  recommendations,
  setRecommendations,
  error,
  setError,
  isLoading,
  setIsLoading
}: MusicInputProps) {
  const [manualUrl, setManualUrl] = useState(value)

  // Handle manual URL input
  const handleManualInput = (inputUrl: string) => {
    setManualUrl(inputUrl)
    if (validateYouTubeMusicUrl(inputUrl)) {
      onChange(inputUrl)
      // Update parent form's audioOption
      if (inputUrl) {
        handleInputChange('audioOption', 'Use Selected Track')
      }
    }
  }

  // Handle track selection from recommendations
  const handleTrackSelect = (track: Track) => {
    setManualUrl(track.external_url)
    onChange(track.external_url)
    // Update parent form's audioOption
    handleInputChange('audioOption', 'Use Selected Track')
  }

  // Validate YouTube Music URL
  const validateYouTubeMusicUrl = (url: string) => {
    if (!url) return true; // Allow empty input
    const patterns = [
      /^https:\/\/music\.youtube\.com\/watch\?v=[\w-]+$/,
      /^https:\/\/www\.youtube\.com\/watch\?v=[\w-]+$/,
      /^https:\/\/youtu\.be\/[\w-]+$/
    ];
    return patterns.some(pattern => pattern.test(url));
  }

  // Keep all the existing validation and form handling
  const isFormValid = () => {
    const requiredFields = {
      'Content Focus': formData.contentFocus,
      'Genre': formData.genre,
      'Mood': formData.moodTone
    }

    const emptyFields = Object.entries(requiredFields)
      .filter(([_, value]) => !value.trim())
      .map(([key, _]) => key)

    if (emptyFields.length > 0) {
      setError(`Please fill in: ${emptyFields.join(', ')}`)
      return false
    }
    return true
  }

  const getRecommendations = async () => {
    if (!isFormValid()) {
      return
    }

    try {
      setIsLoading(true)
      setError('')
      
      // Add artificial delay to prevent flickering for very fast responses
      await new Promise(resolve => setTimeout(resolve, 500));

      console.log('Sending request with data:', {
        contentFocus: formData.contentFocus,
        genre: formData.genre,
        mood: formData.moodTone,
        duration: formData.targetDuration
      })

      const response = await fetch('/api/get-music-recommendations', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          contentFocus: formData.contentFocus,
          genre: formData.genre,
          mood: formData.moodTone,
          duration: formData.targetDuration
        }),
      })

      const data = await response.json()
      console.log('Received response:', data)

      if (!data.success) {
        throw new Error(data.error || 'Failed to get recommendations')
      }

      console.log('Setting recommendations:', data.recommendations)
      setRecommendations(data.recommendations)

    } catch (error) {
      console.error('Error getting recommendations:', error)
      setError(error instanceof Error ? error.message : 'Failed to get recommendations')
    } finally {
      setIsLoading(false)
    }
  }

  const isButtonDisabled = isLoading || !formData.contentFocus.trim() || 
                          !formData.keyLabels.trim() || !formData.stylePreference.trim() || 
                          !formData.moodTone.trim()

  useEffect(() => {
    console.log('Current recommendations:', recommendations)
  }, [recommendations])

  return (
    <div className={`space-y-4 ${isLoading ? 'pointer-events-none opacity-50' : ''}`}>
      <div>
        <Label className="text-purple-400 flex items-center text-lg font-bold tracking-wide">
          Music Track Link
          <span className="text-purple-400 ml-1">*</span>
        </Label>
        <Input
          type="text"
          placeholder="Paste YouTube Music URL"
          value={manualUrl}
          onChange={(e) => handleManualInput(e.target.value)}
          className="mt-1 w-full bg-white text-gray-800 border-gray-300 focus:border-electric-blue focus:ring focus:ring-electric-blue focus:ring-opacity-50 transition-all duration-300"
        />
        {manualUrl && !validateYouTubeMusicUrl(manualUrl) && (
          <p className="text-red-500 text-sm">Please enter a valid YouTube Music URL</p>
        )}
      </div>

      <div className="mt-6">
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <span>
                <Button 
                  onClick={getRecommendations} 
                  type="button" 
                  disabled={isButtonDisabled}
                  className={`bg-purple-600 hover:bg-purple-700 text-white transition-all duration-300 w-full
                    ${isButtonDisabled ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  {isLoading ? 'Getting Recommendations...' : 'Get Recommendations'}
                </Button>
              </span>
            </TooltipTrigger>
            <TooltipContent>
              {isButtonDisabled ? 
                'Please fill in Content Focus, Key Labels, Style, and Mood to get recommendations' : 
                'Click to get music recommendations based on your video details'}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
      
      {error && (
        <p className="text-red-400 text-sm">{error}</p>
      )}

      {recommendations.length > 0 && (
        <div>
          <Label className="text-purple-400 flex items-center gap-2 text-xl font-bold mb-3 tracking-wide">
            Recommended Tracks
          </Label>
          <div className="mt-2 grid grid-cols-2 gap-4">
            {/* Left Column - Track List */}
            <div className="space-y-3">
              {recommendations.map((track) => (
                <div 
                  key={track.id}
                  onClick={() => handleTrackSelect(track)}
                  className="bg-white/20 backdrop-blur-sm rounded-lg p-4 
                             hover:bg-purple-900 hover:bg-opacity-25 hover:border-purple-400
                             transition-all duration-300 border border-purple-300/20 cursor-pointer"
                >
                  <h3 className="text-purple-400 font-semibold text-lg">{track.name}</h3>
                  <p className="text-purple-400 text-sm font-medium">{track.artist}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-purple-100 text-xs bg-purple-900/50 px-2 py-1 rounded-full">
                      Duration: {Math.floor(track.duration_ms / 60000)}:{String(Math.floor((track.duration_ms % 60000) / 1000)).padStart(2, '0')}
                    </span>
                    <span className="text-purple-100 text-xs bg-purple-900/50 px-2 py-1 rounded-full">
                      Views: {track.view_count.toLocaleString()}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            {/* Right Column - YouTube Player */}
            <div className="sticky top-4">
              <div className="bg-white/20 backdrop-blur-sm rounded-lg p-4 border border-purple-300/20">
                <iframe
                  src={`https://www.youtube.com/embed/${value ? value.split('v=')[1] : recommendations[0]?.videoId}?controls=1&showinfo=0&rel=0&modestbranding=1&color=white&iv_load_policy=3&playsinline=1&enablejsapi=1`}
                  width="100%"
                  height="315"
                  frameBorder="0"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                  loading="lazy"
                  className="rounded-md bg-black/20 w-full"
                  style={{
                    border: 'none',
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

