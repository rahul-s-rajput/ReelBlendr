import { spawn, ChildProcess } from 'child_process'
import { NextResponse } from 'next/server'

export async function POST(request: Request): Promise<Response> {
  try {
    const data = await request.json()
    console.log('Received request data:', data)
    
    // Use environment variable for Python path, fallback to 'python'
    const pythonExecutable: string = global.process.env.PYTHON_EXECUTABLE || 'python';
    
    const process: ChildProcess = spawn(
      pythonExecutable,
      [
        'backend/music_recommender.py',
        JSON.stringify({
          contentFocus: data.contentFocus,
          genre: data.genre,
          mood: data.mood,
          duration: data.duration
        })
      ]
    )
    
    return new Promise((resolve, reject) => {
      let result = ''
      let errorOutput = ''
      
      process.stdout?.on('data', (data: Buffer) => {
        result += data.toString()
      })
      
      process.stderr?.on('data', (data: Buffer) => {
        errorOutput += data.toString()
        console.error('Python stderr:', data.toString())
      })
      
      process.on('close', (code: number | null) => {
        if (code !== 0) {
          resolve(NextResponse.json({
            success: false,
            error: `Process exited with code ${code}: ${errorOutput}`
          }, { status: 500 }))
          return
        }
        
        try {
          // Clean the result string
          const cleanResult = result.trim()
          if (!cleanResult) {
            throw new Error('Empty response from Python script')
          }
          
          const recommendations = JSON.parse(cleanResult)
          
          // Check if recommendations is an array
          if (!Array.isArray(recommendations)) {
            throw new Error('Invalid recommendations format')
          }
          
          resolve(NextResponse.json({
            success: true,
            recommendations: recommendations
          }))
        } catch (error) {
          console.error('Parse error:', error)
          resolve(NextResponse.json({
            success: false,
            error: `Failed to parse recommendations: ${error instanceof Error ? error.message : String(error)}`
          }, { status: 500 }))
        }
      })
    })
    
  } catch (error) {
    console.error('Request error:', error)
    return NextResponse.json({
      success: false,
      error: 'Failed to get music recommendations'
    }, { status: 500 })
  }
}
