import json
import os
import time
import httpx
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, stop_after_attempt, wait_exponential
import tempfile
from typing import List, Dict, Optional, Callable
import logging

# Load environment variables early
load_dotenv()
logger = logging.getLogger(__name__)
class VideoAnalyzer:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.results_file = data_dir / 'video_analysis_results_gemini.json' # Changed filename
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("Error: GOOGLE_API_KEY not found in environment variables")

        # Initialize Gemini client
        self.client = genai.Client(api_key=self.api_key)
        # Set longer timeout
        timeout = httpx.Timeout(120.0, connect=10.0, read=120.0, write=60.0) # Increased timeout
        self.client._api_client._httpx_client = httpx.Client(timeout=timeout)

        print("Initialized VideoAnalyzer with Gemini Client")
        self.max_dimension = 720  # Set maximum video dimension for preprocessing
        # self.target_filesize_mb = 100 # Target file size - not directly used in current preprocessing

    def preprocess_video(self, video_path: str) -> str:
        """Preprocess video to optimize size while maintaining quality"""
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, f"processed_{os.path.basename(video_path)}")
        try:
            print(f"Preprocessing video: {video_path}")
            # Get video information
            probe_command = [
                'ffprobe', '-v', 'error', '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height', '-of', 'json', video_path
            ]
            probe_result = subprocess.run(probe_command, capture_output=True, text=True, check=True)
            video_info = json.loads(probe_result.stdout)
            stream = video_info['streams'][0]

            width = int(stream.get('width', 1920))
            height = int(stream.get('height', 1080))

            # Calculate scaling only if dimensions exceed max_dimension
            if max(width, height) > self.max_dimension:
                scale_factor = self.max_dimension / max(width, height)
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)
                # Ensure dimensions are even
                new_width = new_width - (new_width % 2)
                new_height = new_height - (new_height % 2)
                scale_filter = f'scale={new_width}:{new_height}'
            else:
                # Ensure dimensions are even if no scaling needed
                new_width = width - (width % 2)
                new_height = height - (height % 2)
                if new_width != width or new_height != height:
                     scale_filter = f'scale={new_width}:{new_height}'
                else:
                     scale_filter = None # No scaling needed

            ffmpeg_command = [
                'ffmpeg', '-i', video_path,
                '-c:v', 'libx264', '-crf', '28', '-preset', 'ultrafast', # Faster preprocessing preset
                '-c:a', 'aac', '-b:a', '128k',
                '-y', # Overwrite output file
                output_path
            ]

            # Insert scale filter if needed
            if scale_filter:
                ffmpeg_command.insert(3, '-vf')
                ffmpeg_command.insert(4, scale_filter)

            print(f"Running FFmpeg preprocessing command: {' '.join(ffmpeg_command)}")
            subprocess.run(ffmpeg_command, check=True, capture_output=True) # Capture output to avoid printing verbose ffmpeg logs
            print(f"Preprocessed video saved to: {output_path}")
            return output_path

        except Exception as e:
            print(f"Error preprocessing video {video_path}: {str(e)}")
            # Cleanup temp dir if preprocessing fails
            try:
                os.remove(output_path)
                os.rmdir(temp_dir)
            except OSError:
                pass
            return video_path # Return original path if preprocessing fails

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    def _upload_and_wait(self, video_path: str, progress_callback: Optional[Callable] = None) -> types.File:
        """Uploads a video file to Gemini and waits for it to become active."""
        if progress_callback: progress_callback(f"Uploading {os.path.basename(video_path)}...")
        print(f"Uploading file: {video_path}")
        with open(video_path, "rb") as file:
            # Assuming video/mp4, adjust if needed or detect dynamically
            uploaded_file = self.client.files.upload(file=file, config={"mime_type": "video/mp4"})
        print(f"File uploaded as {uploaded_file.name}")

        if progress_callback: progress_callback(f"Waiting for {os.path.basename(video_path)} processing...")
        print(f"Waiting for file {uploaded_file.name} to be processed...")

        max_retries = 7 # Increased retries
        retry_count = 0
        file_active = False
        while retry_count < max_retries and not file_active:
            try:
                file_info = self.client.files.get(name=uploaded_file.name)
                print(f"File status ({retry_count+1}/{max_retries}): {file_info.state}")
                if file_info.state == "ACTIVE":
                    file_active = True
                elif file_info.state == "FAILED":
                     raise Exception(f"File processing failed for {uploaded_file.name}")
                else:
                    wait_time = 20 + (retry_count * 15) # Increased wait time
                    print(f"File not yet active, waiting {wait_time}s...")
                    if progress_callback: progress_callback(f"Processing {os.path.basename(video_path)} (attempt {retry_count+1})...")
                    time.sleep(wait_time)
                    retry_count += 1
            except Exception as e:
                print(f"Error checking file status: {e}. Retrying...")
                time.sleep(10)
                retry_count += 1

        if not file_active:
            raise TimeoutError(f"File {uploaded_file.name} did not become active after multiple retries.")

        print(f"File {uploaded_file.name} is active.")
        if progress_callback: progress_callback(f"Processing active for {os.path.basename(video_path)}")
        return uploaded_file

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    def analyze_video_gemini(self, video_path: str, progress_callback: Optional[Callable] = None) -> Dict:
        """Analyze a single video file using the Gemini detailed analysis prompt."""
        processed_video_path = None
        temp_dir_to_clean = None
        try:
            print(f"\nAnalyzing video with Gemini: {video_path}")
            if not os.path.exists(video_path):
                raise FileNotFoundError(f"Error: Video file not found at {video_path}")

            # Preprocess video before analysis
            processed_video_path = self.preprocess_video(video_path)
            if processed_video_path != video_path:
                temp_dir_to_clean = os.path.dirname(processed_video_path)

            # Upload and wait for the processed video
            uploaded_file = self._upload_and_wait(processed_video_path, progress_callback)

            if progress_callback: progress_callback(f"Starting Gemini analysis for {os.path.basename(video_path)}...")
            print(f"Analyzing video {uploaded_file.name} with Gemini...")

            # Define the detailed analysis prompt (from test_video_with_audio_segments.py)
            analysis_prompt = """Analyze this video in complete detail and provide a single comprehensive JSON output with two main sections:

## Main JSON Structure

{
  "video_analysis": {
    "segments": [
      // Array of all time-based segments
    ],
    "segment_rankings": {
      // Rankings of all segments
    }
  }
}

## Part 1: Detailed Time-Based Segmentation

Create a comprehensive array of segments that breaks down the entire video based on content changes. For each segment:

1. Identify the precise start and end timestamps (in seconds, with decimal precision)
2. Provide detailed labels for all visible elements:
   - Main subjects/objects
   - Actions/movements
   - Background elements
   - Camera movements/angles
   - Lighting conditions
   - Audio elements (speech, music, ambient sounds)
   - Emotional tone
   - Text overlays or graphics
   - Scene transitions

Create a new segment whenever there is a significant change in ANY of these elements. Be extremely granular - even subtle changes should trigger a new segment. The goal is to have many detailed segments rather than few general ones.

Format each segment like this:
{
  "segment_id": 1,
  "start_time": 0.0,
  "end_time": 4.2,
  "main_subjects": ["woman in red dress", "small dog"],
  "actions": ["woman walking", "dog sitting"],
  "background": ["urban street", "storefronts"],
  "camera": ["medium tracking shot", "slight pan right"],
  "lighting": ["natural daylight", "slight shadow from buildings"],
  "audio": ["ambient street noise", "woman speaking", "faint music"],
  "emotional_tone": ["casual", "relaxed"],
  "text_overlays": ["opening credits", "location identifier"],
  "transitions": ["fade in from black"]
}

## Part 2: Segment Rankings

Evaluate and rank ALL segments based on their quality from a video editor's perspective. For each segment, assess:

1. Visual composition and framing
2. Camera stability (minimal shakiness)
3. Lighting quality and consistency
4. Subject interest and engagement
5. Action/movement quality
6. Narrative importance
7. Audio clarity and quality
8. Emotional impact
9. Technical quality (focus, resolution, color)
10. Transition potential (how well it could be used in an edit)

Include these rankings in the "segment_rankings" section of the JSON:
{
  "segment_rankings": {
    "ranking_criteria": {
      "composition": "Visual composition and framing",
      "stability": "Camera stability",
      "lighting": "Lighting quality",
      "subject_interest": "Subject interest and engagement",
      "movement_quality": "Action/movement quality",
      "narrative_importance": "Importance to the narrative",
      "audio_quality": "Audio clarity and quality",
      "emotional_impact": "Emotional impact",
      "technical_quality": "Technical quality",
      "transition_potential": "Potential for transitions"
    },
    "ranked_segments": [
      {
        "segment_id": 12,
        "duration": 5.3,
        "composition_score": 9.5,
        "stability_score": 8.7,
        "lighting_score": 9.2,
        "subject_interest_score": 9.8,
        "movement_quality_score": 8.9,
        "narrative_importance_score": 9.3,
        "audio_quality_score": 8.5,
        "emotional_impact_score": 9.7,
        "technical_quality_score": 9.1,
        "transition_potential_score": 8.8,
        "overall_score": 9.2,
        "rank": 1,
        "editor_notes": "Perfect moment capturing the emotional climax of the story. The lighting creates ideal contrast, facial expression is authentic and powerful, and the subtle sound design enhances the emotional impact."
      },
      // Additional ranked segments...
    ]
  }
}

Ensure the JSON structure is valid and properly formatted for direct use in applications. The "ranked_segments" array should contain ALL segments from the video, sorted by their overall quality score (highest to lowest). Return ONLY the JSON structure."""

            # Specify model
            model = "gemini-2.5-pro-exp-03-25" # Use the specific experimental model if needed
            # model = "models/gemini-1.5-pro-latest" # Use the latest stable model

            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_uri(
                            file_uri=uploaded_file.uri,
                            mime_type=uploaded_file.mime_type,
                        ),
                        types.Part.from_text(text=analysis_prompt),
                    ],
                ),
            ]

            # Configure response
            generate_content_config = types.GenerateContentConfig(
                response_mime_type="application/json", # Request JSON directly
            )

            # Generate content
            print(f"Sending analysis request to Gemini model: {model}")
            response = self.client.models.generate_content(
                model=model,
                contents=contents,
                config=generate_content_config,
            )
            print("Received analysis response from Gemini.")

            # Parse the JSON string from the response text
            analysis_result = json.loads(response.text)

            # Add original filename and duration for context
            probe = subprocess.run([
                'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1', video_path
            ], capture_output=True, text=True, check=True)
            duration = float(probe.stdout.strip())

            analysis_result['original_file_name'] = os.path.basename(video_path)
            analysis_result['original_duration'] = duration

            if progress_callback: progress_callback(f"Gemini analysis complete for {os.path.basename(video_path)}")
            return analysis_result

        except Exception as e:
            print(f"Gemini analysis error for {video_path}: {str(e)}")
            import traceback
            traceback.print_exc()
            if progress_callback: progress_callback(f"Gemini analysis FAILED for {os.path.basename(video_path)}: {str(e)}")
            # Return an error structure or re-raise
            return {"error": str(e), "file_name": os.path.basename(video_path)}
        finally:
            # Cleanup temporary processed video if it exists and is different from original
            if processed_video_path and processed_video_path != video_path and os.path.exists(processed_video_path):
                try:
                    print(f"Cleaning up temporary file: {processed_video_path}")
                    os.remove(processed_video_path)
                    if temp_dir_to_clean and os.path.exists(temp_dir_to_clean):
                         os.rmdir(temp_dir_to_clean)
                except OSError as cleanup_error:
                     print(f"Error cleaning up temporary file {processed_video_path}: {cleanup_error}")
            # Attempt to delete the file from Gemini service if upload succeeded
            if 'uploaded_file' in locals() and uploaded_file:
                try:
                    print(f"Deleting uploaded file from Gemini service: {uploaded_file.name}")
                    self.client.files.delete(name=uploaded_file.name)
                except Exception as delete_error:
                    print(f"Could not delete file {uploaded_file.name} from Gemini service: {delete_error}")


    def analyze_videos_batch(self, video_paths: List[str], max_workers: int = 3, progress_callback: Optional[Callable] = None) -> None:
        """Analyze multiple videos in parallel using Gemini and save results"""
        if progress_callback:
            progress_callback(f"Starting Gemini analysis of {len(video_paths)} videos")

        logger.info(f"Starting parallel Gemini batch analysis of {len(video_paths)} videos with {max_workers} workers")
        logger.info(f"Video paths to analyze: {video_paths}")

        # Check existing results (optional, can be useful for resuming)
        existing_results = {}
        if os.path.exists(self.results_file):
            logger.info(f"Attempting to load existing results from {self.results_file}")
            try:
                with open(self.results_file, 'r') as f:
                    existing_results = json.load(f)
                logger.info(f"Successfully loaded {len(existing_results)} existing results. Keys: {list(existing_results.keys())}")
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding JSON from existing results file {self.results_file}: {e}")
                existing_results = {} # Reset to empty dict if file is corrupt
            except Exception as e:
                logger.error(f"Error reading existing results file {self.results_file}: {e}")
                existing_results = {}

        # Filter out already analyzed videos
        videos_to_analyze = []
        logger.info("Filtering videos for analysis...")
        for path in video_paths:
            basename = os.path.basename(str(path))
            if basename not in existing_results:
                logger.info(f"'{basename}' not found in existing results. Adding to analysis queue.")
                videos_to_analyze.append(path)
            else:
                logger.info(f"'{basename}' found in existing results. Skipping analysis.")


        if not videos_to_analyze:
            logger.info("All videos already analyzed or no videos provided. Using cached results if available.")
            # Ensure the results file exists even if empty if no analysis is done
            if not os.path.exists(self.results_file):
                 logger.warning(f"Results file {self.results_file} not found, creating empty file.")
                 try:
                     with open(self.results_file, 'w') as f:
                        json.dump({}, f)
                 except Exception as e:
                     logger.error(f"Failed to create empty results file: {e}")
            return # Exit if nothing to analyze

        logger.info(f"Found {len(videos_to_analyze)} videos requiring analysis: {[os.path.basename(str(p)) for p in videos_to_analyze]}")
        analysis_results = existing_results.copy() # Start with existing results

        # Process videos in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Pass the progress_callback to the submitted function
            future_to_video = {
                executor.submit(self.analyze_video_gemini, str(video_path), progress_callback): video_path
                for video_path in videos_to_analyze
            }

            # Process completed tasks as they finish
            for future in as_completed(future_to_video):
                video_path = future_to_video[future]
                file_name = os.path.basename(str(video_path))
                try:
                    # Result is the direct JSON analysis from Gemini
                    result_data = future.result()
                    if result_data and 'error' not in result_data:
                        # Use the original filename as the key
                        analysis_results[file_name] = result_data
                        logger.info(f"Successfully analyzed {file_name}")
                        # No need for process_results anymore
                    elif result_data and 'error' in result_data:
                         logger.error(f"Analysis failed for {file_name}: {result_data['error']}")
                         # Optionally store error information
                         analysis_results[file_name] = {"error": result_data['error']}
                    else:
                         logger.warning(f"Analysis returned no result for {file_name}")
                         analysis_results[file_name] = {"error": "No result returned"}

                except Exception as e:
                    logger.error(f"Exception during analysis future result processing for {video_path}: {str(e)}")
                    if progress_callback:
                        progress_callback(f"Analysis failed for {file_name}: {str(e)}") # Keep callback for external updates
                    # Store error information
                    analysis_results[file_name] = {"error": str(e)} # Store error info


        # Save combined results to file
        logger.info(f"Saving combined results for {len(analysis_results)} videos to {self.results_file}")
        try:
            with open(self.results_file, 'w') as f:
                json.dump(analysis_results, f, indent=2)
            logger.info(f"Successfully saved analysis results.")
            if progress_callback: progress_callback(f"Analysis complete. Results saved.")
        except Exception as e:
             logger.error(f"Error saving analysis results: {e}")
             if progress_callback: progress_callback(f"Error saving analysis results: {e}")
