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
# from video_editor import create_edit_sequence, simplify_analysis_results # Old editor functions removed
from video_editor import VideoEditor # Import the new class

import json
from concurrent.futures import ThreadPoolExecutor, Future # Import for parallel execution
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
video_editor = VideoEditor() # Instantiate the new VideoEditor
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
            
            # Save uploaded videos (if they don't already exist) and get paths
            video_paths = []
            uploaded_file_objects = request.files.getlist('videos')
            logger.info(f"Received {len(uploaded_file_objects)} file objects in request.")

            for video_file_storage in uploaded_file_objects:
                # Sanitize filename (optional but recommended)
                # filename = secure_filename(video_file_storage.filename) # Requires importing secure_filename from werkzeug.utils
                filename = video_file_storage.filename # Using original filename for now
                if not filename:
                    logger.warning("Received a file without a filename, skipping.")
                    continue

                video_path = data_dir / filename
                logger.debug(f"Processing file: {filename}, Target path: {video_path}")

                # Check if file already exists in the data directory
                if video_path.exists():
                    logger.info(f"File '{filename}' already exists. Using existing file.")
                    yield f"data: {json.dumps({'type': 'progress', 'message': f'Using existing video: {filename}'})}\n\n"
                else:
                    logger.info(f"Saving new file: {filename}")
                    try:
                        video_file_storage.save(str(video_path))
                        logger.info(f"Successfully saved {filename} to {video_path}")
                        yield f"data: {json.dumps({'type': 'progress', 'message': f'Saved video: {filename}'})}\n\n"
                    except Exception as save_error:
                        logger.error(f"Error saving file {filename}: {save_error}")
                        yield f"data: {json.dumps({'type': 'error', 'message': f'Error saving file {filename}: {save_error}'})}\n\n"
                        # Decide if we should continue or raise error - let's skip this file
                        continue

                # Add the path (either existing or newly saved) to the list for analysis
                video_paths.append(str(video_path))

            if not video_paths:
                 logger.error("No valid video files were processed or found.")
                 yield f"data: {json.dumps({'type': 'error', 'message': 'No valid video files received or processed.'})}\n\n"
                 raise Exception("No valid video files available for processing.")

            logger.info(f"Video paths to be analyzed: {video_paths}")

            # Initialize VideoAnalyzer and process videos
            analyzer = VideoAnalyzer(data_dir)
            logger.info("Starting video analysis...")
            
            # Create a list to store progress messages (can be shared if needed, but might be complex with threads)
            # Using separate yields might be simpler for now.
            def progress_callback(msg):
                # This callback needs to be thread-safe if modifying shared state.
                # For now, just log it. We'll yield messages after tasks complete.
                logger.info(f"Progress Callback: {msg}")
                # yield f"data: {json.dumps({'type': 'progress', 'message': msg})}\n\n" # Avoid yielding directly from callback in thread

            # --- Parallel Execution Start ---
            video_analysis_future: Optional[Future] = None
            audio_analysis_future: Optional[Future] = None
            audio_analysis_result = None # Variable to store audio result

            with ThreadPoolExecutor(max_workers=2) as executor:
                # Submit video analysis task
                logger.info("Submitting video analysis task...")
                yield f"data: {json.dumps({'type': 'progress', 'message': 'Starting video analysis...'})}\n\n"
                video_analysis_future = executor.submit(
                    analyzer.analyze_videos_batch,
                    video_paths,
                    progress_callback=progress_callback
                )

                # Submit audio analysis task (if applicable)
                music_url = request.form.get('musicUrl') or request.form.get('spotifyTrack')
                logger.info(f"Checking music URL for parallel processing: {music_url}")
                if music_url and request.form.get('audioOption') != "No Audio" and music_recommender:
                    logger.info("Submitting audio analysis task...")
                    yield f"data: {json.dumps({'type': 'progress', 'message': 'Starting audio analysis...'})}\n\n"
                    audio_analysis_future = executor.submit(
                        music_recommender.get_audio_analysis,
                        music_url,
                        "",  # Empty artist since we're using URL
                        request.form.get('stylePreference', 'Smooth/Cinematic'),
                        int(request.form.get('targetDuration', 30)) * 1000,
                        request.form.get('moodTone', 'Neutral')
                    )
                else:
                    logger.warning(f"Skipping audio analysis task - music_url: {bool(music_url)}, audioOption: {request.form.get('audioOption')}, music_recommender: {bool(music_recommender)}")
                    yield f"data: {json.dumps({'type': 'progress', 'message': 'Skipping audio analysis...'})}\n\n"

                # Wait for tasks and get results
                logger.info("Waiting for analysis tasks to complete...")
                if video_analysis_future:
                    try:
                        # analyze_videos_batch writes to file, doesn't return data directly
                        video_analysis_future.result() # Wait for completion and check for exceptions
                        logger.info("Video analysis task completed.")
                        yield f"data: {json.dumps({'type': 'progress', 'message': 'Video analysis complete.'})}\n\n"
                    except Exception as e:
                        logger.error(f"Video analysis task failed: {e}")
                        yield f"data: {json.dumps({'type': 'error', 'message': f'Video analysis failed: {e}'})}\n\n"
                        raise # Re-raise exception to stop processing

                if audio_analysis_future:
                    try:
                        audio_analysis_result = audio_analysis_future.result() # Get result
                        if audio_analysis_result:
                            logger.info("Audio analysis task completed successfully.")
                            logger.info(f"Audio transition points: {audio_analysis_result['analysis']['transition_points']}")
                            yield f"data: {json.dumps({'type': 'progress', 'message': 'Audio analysis complete.'})}\n\n"
                        else:
                            logger.warning("Audio analysis task completed but returned no results.")
                            yield f"data: {json.dumps({'type': 'progress', 'message': 'Audio analysis complete (no results).'})}\n\n"
                    except Exception as e:
                        logger.error(f"Audio analysis task failed: {e}")
                        yield f"data: {json.dumps({'type': 'error', 'message': f'Audio analysis failed: {e}'})}\n\n"
                        # Decide if you want to continue without audio or raise exception
                        # For now, let's continue without audio data
                        audio_analysis_result = None

            # --- Parallel Execution End ---

            # Initialize video configuration (now uses audio_analysis_result)
            video_config = {
                'video_segments': None,
                'audio_analysis': audio_analysis_result if audio_analysis_result else {} # Use result or empty dict
            }

            # 3. Generate editing plan using Gemini
            key_labels_str = request.form.get('keyLabels', '')
            key_labels_list = [label.strip() for label in key_labels_str.split(',') if label.strip()] # Split comma-separated string into list
            prompt_parameters = {
                'content_focus': request.form.get('contentFocus', ''),
                'key_labels': key_labels_list, # Use the processed list
                'style': request.form.get('stylePreference', 'Smooth/Cinematic'),
                'order': request.form.get('orderPreference', 'AI-determined') # Note: 'order' might not be used by the new editor prompt directly
            }
            logger.debug(f"Processed prompt parameters: {prompt_parameters}") # Add log to verify
            # 3. Generate editing plan using Gemini based on detailed video analysis and audio data
            logger.info("Generating editing plan using Gemini...")
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Generating editing plan...'})}\n\n"

            # Define path to the new analysis results file
            analysis_results_path = analyzer.results_file # Use the path defined in VideoAnalyzer

            # Ensure audio_analysis_result is a dictionary, even if empty
            if audio_analysis_result is None:
                audio_analysis_result = {}

            # Call the new editor method using the result from the parallel task
            video_segments = video_editor.generate_editing_plan(
                video_analysis_path=analysis_results_path,
                audio_data=audio_analysis_result, # Use the result from the parallel task
                prompt_parameters=prompt_parameters,
                progress_callback=progress_callback # Pass the callback
            )

            # Note: progress_callback might need adjustment if generate_editing_plan doesn't use it directly
            # Removed iteration over progress_messages as it's no longer used here

            if video_segments:
                video_config['video_segments'] = video_segments
                logger.info(f"Generated editing plan with {len(video_segments)} segments")
                yield f"data: {json.dumps({'type': 'progress', 'message': f'Generated editing plan with {len(video_segments)} segments'})}\n\n"
            else:
                logger.error("Failed to generate editing plan.")
                yield f"data: {json.dumps({'type': 'error', 'message': 'Failed to generate editing plan'})}\n\n"
                # Stop processing if no segments were generated
                raise Exception("Editing plan generation failed")

            # 4. Create final video using VideoCreator (which uses VideoProcessor)
            logger.info("Creating final video...")
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Creating final video...'})}\n\n"

            # Pass the necessary info to VideoCreator
            # VideoCreator/VideoProcessor needs the segment list and potentially the audio file path
            # Use audio_analysis_result here as well
            audio_file_path = audio_analysis_result.get('track_info', {}).get('trimmed_file') if audio_analysis_result else None

            # Assuming VideoCreator.create_video needs segments and optional audio path
            # We might need to adjust VideoCreator if its signature changed
            output_path = video_creator.create_video(
                video_segments=video_config['video_segments'],
                audio_file_path=audio_file_path, # Pass audio path explicitly
                progress_callback=progress_callback # Pass callback if VideoCreator supports it
            )

            # Removed iteration over progress_messages as it's no longer used here

            if output_path:
                logger.info(f"Final video created successfully at {output_path}")
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
