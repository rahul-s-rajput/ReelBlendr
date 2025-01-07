import { spawn } from 'child_process';
import { NextResponse } from 'next/server';

export async function POST(request: Request): Promise<Response> {
  try {
    const data = await request.json();
    console.log('Analyzing audio for:', data);

    const process = spawn(
      'C:\\Users\\rajpu\\Downloads\\AI Project\\reel\\venv\\Scripts\\python.exe',
      [
        'backend/music_recommender.py',
        JSON.stringify({
          trackName: data.trackName,
          artist: data.artist,
          targetDuration: data.targetDuration
        })
      ]
    );

    return new Promise((resolve, reject) => {
      let result = '';
      let errorOutput = '';

      process.stdout.on('data', (data) => {
        result += data.toString();
      });

      process.stderr.on('data', (data) => {
        errorOutput += data.toString();
        console.error('Python stderr:', data.toString());
      });

      process.on('close', (code) => {
        if (code !== 0) {
          resolve(NextResponse.json({
            success: false,
            error: `Failed to analyze audio: ${errorOutput}`
          }, { status: 500 }));
          return;
        }

        try {
          const analysis = JSON.parse(result.trim());
          console.log('Audio analysis results:', analysis);

          resolve(NextResponse.json({
            success: true,
            analysis
          }));
        } catch (error) {
          console.error('Parse error:', error);
          resolve(NextResponse.json({
            success: false,
            error: `Failed to parse analysis results: ${error instanceof Error ? error.message : String(error)}`
          }, { status: 500 }));
        }
      });
    });

  } catch (error) {
    console.error('Request error:', error);
    return NextResponse.json({
      success: false,
      error: 'Failed to analyze audio'
    }, { status: 500 });
  }
} 