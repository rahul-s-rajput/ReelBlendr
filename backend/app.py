from flask import Flask, request, jsonify, Response, send_from_directory, stream_with_context, send_file
from flask_cors import CORS
import logging
from pathlib import Path
import os
import re
from dotenv import load_dotenv
from video_creator import VideoCreator
from video_analyzer import VideoAnalyzer
from music_recommender import MusicRecommender
from video_editor import create_edit_sequence, simplify_analysis_results

import json
from werkzeug.serving import WSGIRequestHandler
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Increase timeout for Werkzeug server
WSGIRequestHandler.protocol_version = "HTTP/1.1"

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 2048 * 1024 * 1024  # 2GB max-limit
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# Create data directory
data_dir = Path("data")
data_dir.mkdir(exist_ok=True)
logger.info(f"Data directory created/verified at {data_dir}")

# Initialize components
video_creator = VideoCreator(data_dir)
music_recommender = None

try:
    music_recommender = MusicRecommender()
    logger.info("YouTube Music client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize YouTube Music client: {e}")
# Setup Google credentials
def setup_google_credentials():
    try:
        creds_json = os.getenv('SERVICE_ACCOUNT_JSON')
        if not creds_json:
            logger.error("Google Cloud credentials not found in environment")
            return False
            
        creds_path = data_dir / "google_credentials.json"
        with open(creds_path, 'w') as f:
            f.write(creds_json)
        
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(creds_path)
        logger.info("Google credentials setup successfully")
        return True
    except Exception as e:
        logger.error(f"Error setting up Google credentials: {e}")
        return False

# Initialize credentials
if not setup_google_credentials():
    logger.error("Failed to setup Google credentials!")

@app.route('/api/create-video', methods=['POST'])
def create_video():
    @stream_with_context
    def generate_updates():
        try:
            # Get form data and log it
            logger.info("Received form data:")
            logger.info(f"Files: {request.files.getlist('videos')}")
            logger.info(f"Target Duration: {request.form.get('targetDuration')}")
            
            # Save uploaded videos and analyze them
            video_paths = []
            for video in request.files.getlist('videos'):
                video_path = data_dir / video.filename
                video.save(str(video_path))
                video_paths.append(str(video_path))
                yield f"data: {json.dumps({'type': 'progress', 'message': f'Saved video: {video_path}'})}\n\n"

            # Initialize VideoAnalyzer and process videos
            analyzer = VideoAnalyzer(data_dir)
            logger.info("Starting video analysis...")
            
            # Create a list to store progress messages
            progress_messages = []
            def progress_callback(msg):
                progress_messages.append(msg)
            
            # Process videos and collect results
            analyzed_videos = analyzer.analyze_videos_batch(
                video_paths,
                progress_callback=progress_callback
            )
            
            # Yield all collected progress messages
            for msg in progress_messages:
                yield f"data: {json.dumps({'type': 'progress', 'message': msg})}\n\n"
            
            logger.info("Video analysis complete")
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Video analysis complete'})}\n\n"

            # Initialize video configuration
            video_config = {
                'video_segments': None,  # Make sure this contains the segments from create_edit_sequence
                'audio_analysis': None
            }

            # Get music URL from form data (check both possible field names)
            music_url = request.form.get('musicUrl') or request.form.get('spotifyTrack')
            logger.info(f"Processing music URL: {music_url}")

            # If music URL is provided and audioOption is not "No Audio", analyze it
            if music_url and request.form.get('audioOption') != "No Audio" and music_recommender:
                logger.info(f"Analyzing music from URL: {music_url}")
                try:
                    # Pass the URL directly as track_name
                    audio_analysis = music_recommender.get_audio_analysis(
                        music_url,
                        "",  # Empty artist since we're using URL
                        request.form.get('stylePreference', 'Smooth/Cinematic'),
                        int(request.form.get('targetDuration', 30)) * 1000,
                        request.form.get('moodTone', 'Neutral')
                    )
                    
                    if audio_analysis:
                        logger.info("Audio analysis completed successfully:")
                        logger.info(f"Transition points: {audio_analysis['analysis']['transition_points']}")
                        
                        # Store analysis results for video creation
                        video_config['audio_analysis'] = audio_analysis
                    else:
                        logger.warning("Audio analysis returned no results")
                        
                except Exception as e:
                    logger.error(f"Error analyzing audio: {e}")
            else:
                logger.warning(f"Skipping audio analysis - music_url: {bool(music_url)}, audioOption: {request.form.get('audioOption')}, music_recommender: {bool(music_recommender)}")
            
            # 3. Create edit sequence based on video and audio analysis
            prompt_parameters = {
                'content_focus': request.form.get('contentFocus', ''),
                'key_labels': request.form.getlist('keyLabels[]'),
                'style': request.form.get('stylePreference', 'Smooth/Cinematic'),
                'order': request.form.get('orderPreference', 'AI-determined')
            }
            simplified_analysis_results = simplify_analysis_results(data_dir / 'video_analysis_results.json')
            # Get video segments
            audio_segments = audio_analysis.get('segments', [])
            video_segments = create_edit_sequence(
                data_dir / 'simplified_analysis_results.json',
                prompt_parameters,
                audio_segments
            )
            
            if video_segments:
                video_config['video_segments'] = video_segments
                logger.info(f"Created edit sequence with {len(video_segments)} segments")
            else:
                logger.warning("No video segments created")

            # Create final video
            output_path = video_creator.create_video(video_config)
            
            if output_path:
                relative_path = str(output_path).replace('\\', '/')
                video_filename = relative_path.split('/')[-1]
                video_url = f'/data/output/{video_filename}'
                
                yield f"data: {json.dumps({'type': 'complete', 'video_url': video_url})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Failed to create video'})}\n\n"

        except Exception as e:
            logger.error(f"Error in create_video: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        finally:
            # Ensure we always send a final message
            yield f"data: {json.dumps({'type': 'end'})}\n\n"

    return Response(
        generate_updates(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*'
        }
    )

@app.route('/api/get-music-recommendations', methods=['POST'])
def get_music_recommendations():
    try:
        if not music_recommender:
            return jsonify({
                'success': False,
                'error': 'Spotify client not initialized'
            }), 500

        data = request.json
        recommendations = music_recommender.find_recommendations(
            content_focus=data.get('contentFocus', ''),
            genre=data.get('genre', ''),
            mood=data.get('mood', ''),
            duration=int(data.get('duration', 30)),
            num_recommendations=3
        )

        return jsonify({
            'success': True,
            'recommendations': recommendations
        })

    except Exception as e:
        logger.error(f"Error getting music recommendations: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/data/output/<filename>')
def serve_video(filename):
    try:
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'output')
        video_path = os.path.join(output_dir, filename)
        
        if not os.path.exists(video_path):
            logger.error(f"Video file not found at path: {video_path}")
            return jsonify({
                'status': 'error',
                'message': 'Video file not found'
            }), 404

        file_size = os.path.getsize(video_path)
        
        # Handle range header
        range_header = request.headers.get('Range', None)
        if range_header:
            byte1, byte2 = 0, None
            match = re.search(r'bytes=(\d+)-(\d*)', range_header)
            if match:
                groups = match.groups()
                if groups[0]:
                    byte1 = int(groups[0])
                if groups[1]:
                    byte2 = int(groups[1])

            if byte2 is None:
                byte2 = file_size - 1
            
            chunk_length = byte2 - byte1 + 1

            # Create response
            with open(video_path, 'rb') as f:
                f.seek(byte1)
                chunk = f.read(chunk_length)

            response = Response(
                chunk,
                206,
                mimetype='video/mp4',
                direct_passthrough=True
            )
            
            response.headers.add('Content-Range', f'bytes {byte1}-{byte2}/{file_size}')
            response.headers.add('Accept-Ranges', 'bytes')
            response.headers.add('Content-Length', str(chunk_length))
            response.headers.add('Cache-Control', 'no-cache')
            
            return response

        # If no range header, serve entire file
        response = send_file(
            video_path,
            mimetype='video/mp4',
            as_attachment=False,
            conditional=True
        )
        response.headers.add('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        response.headers.add('Pragma', 'no-cache')
        response.headers.add('Expires', '0')
        
        return response

    except Exception as e:
        logger.error(f"Error serving video: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error serving video: {str(e)}'
        }), 500

if __name__ == '__main__':
    # Use threaded=True for handling multiple requests
    from werkzeug.serving import run_simple
    run_simple('127.0.0.1', 5000, app, 
               use_reloader=True, 
               use_debugger=True, 
               threaded=True)
