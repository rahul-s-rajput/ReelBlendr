import { NextResponse } from 'next/server'

// Increase maxDuration to 10 minutes for local development
export const maxDuration = 600
export const dynamic = 'force-dynamic'

const extractYouTubeId = (url: string): string | null => {
  const patterns = [
    /(?:youtube\.com\/watch\?v=|youtu\.be\/|music\.youtube\.com\/watch\?v=)([\w-]+)/i
  ];
  
  for (const pattern of patterns) {
    const match = url.match(pattern);
    if (match) return match[1];
  }
  
  return null;
};

export async function POST(request: Request) {
  try {
    const formData = await request.formData()
    
    try {
      const response = await fetch('http://127.0.0.1:5000/api/create-video', {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()

      if (!reader) {
        throw new Error('No response body')
      }

      let videoUrl: string | null = null
      let lastError: string | null = null

      // Stream the response
      while (true) {
        const { done, value } = await reader.read()
        
        if (done) {
          if (videoUrl) {
            return NextResponse.json({
              status: 'success',
              video_url: videoUrl
            })
          } else if (lastError) {
            throw new Error(lastError)
          }
          break
        }

        const chunk = decoder.decode(value)
        const lines = chunk.split('\n\n')
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const eventData = JSON.parse(line.slice(6))
              
              switch (eventData.type) {
                case 'complete':
                  videoUrl = eventData.video_url
                  break
                case 'error':
                  lastError = eventData.message
                  break
                case 'end':
                  if (videoUrl) {
                    return NextResponse.json({
                      status: 'success',
                      video_url: videoUrl
                    })
                  } else if (lastError) {
                    throw new Error(lastError)
                  }
                  break
                case 'progress':
                  console.log('Progress:', eventData.message)
                  break
              }
            } catch (parseError) {
              console.error('Error parsing SSE data:', parseError)
            }
          }
        }
      }

      if (!videoUrl && !lastError) {
        throw new Error('Stream ended without completion')
      }

    } catch (fetchError: any) {
      console.error('Connection error:', fetchError)
      const errorMessage = fetchError.code === 'UND_ERR_BODY_TIMEOUT' 
        ? 'Video processing is taking longer than expected...'
        : 'Could not connect to video processing server. Please ensure the server is running.'
      
      return NextResponse.json({
        status: 'error',
        message: errorMessage
      }, { status: 503 })
    }

  } catch (error) {
    console.error('Error:', error)
    return NextResponse.json({
      status: 'error',
      message: error instanceof Error ? error.message : 'Failed to process request'
    }, { status: 500 })
  }
} 