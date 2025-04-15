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
        body: formData,
        headers: { // Add headers
          'Connection': 'close' // Explicitly close connection after request
        }
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

      try { // Wrap stream processing in try...finally
        // Stream the response
        while (true) {
          const { done, value } = await reader.read()

          if (done) {
             // Exit loop when stream is done
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
                    // Don't return/break immediately, let stream finish naturally
                    break
                  case 'error':
                    lastError = eventData.message
                    // Optionally break here if errors should halt processing immediately
                    break
                  case 'end':
                    // The 'end' message signals the backend finished.
                    // We rely on the reader's 'done' flag to exit the loop.
                    // No specific action needed here, loop will terminate when done=true.
                    break
                  case 'progress':
                    console.log('Progress:', eventData.message)
                    break
                }
              } catch (parseError) {
                console.error('Error parsing SSE data:', parseError)
                lastError = `Error parsing stream data: ${parseError instanceof Error ? parseError.message : parseError}`;
                // Optionally break here if parsing errors are critical
              }
            }
          }
        } // End while loop

        // After loop finishes (because reader signaled done=true)
        if (videoUrl) {
          // Success case: return the video URL
          return NextResponse.json({
            status: 'success',
            video_url: videoUrl
          })
        } else if (lastError) {
          // Error case: Return JSON error response
          console.error("Stream processing finished with error:", lastError);
          // Throwing here might prevent finally block execution in some edge cases?
          // Let's return a JSON error response directly.
          // throw new Error(lastError)
           return NextResponse.json({ status: 'error', message: lastError }, { status: 500 });
        } else {
          // Unexpected case: stream finished without complete or error message
           console.error('Stream ended without explicit completion or error message.');
           return NextResponse.json({ status: 'error', message: 'Stream ended without explicit completion or error message.' }, { status: 500 });
          // throw new Error('Stream ended without explicit completion or error message.')
        }

      } finally {
        // Ensure the reader lock is always released
        if (reader) {
          try {
            await reader.releaseLock();
            console.log("Stream reader released.");
          } catch (releaseError) {
            console.error("Error releasing stream reader lock:", releaseError);
          }
        }
      }
      // The logic below this point was duplicated in the previous error and is removed by this replacement.

    } catch (streamOrFetchError: any) { // Catch errors from fetch OR errors thrown within the stream try block
      console.error('Error during fetch or stream processing:', streamOrFetchError);
      // Handle specific fetch errors if needed, otherwise return generic error
      const errorMessage = streamOrFetchError.code === 'UND_ERR_BODY_TIMEOUT'
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
