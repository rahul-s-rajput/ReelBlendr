import { NextResponse } from 'next/server'

export const maxDuration = 6000 // Set maximum duration to 100 minutes
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
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 6000000)

      const response = await fetch('http://127.0.0.1:5000/api/create-video', {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      })

      clearTimeout(timeoutId)

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()
      return NextResponse.json(data)
      
    } catch (fetchError: any) {
      console.error('Connection error:', fetchError)
      const errorMessage = fetchError.code === 'UND_ERR_HEADERS_TIMEOUT' 
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
      message: 'Failed to process request'
    }, { status: 500 })
  }
} 