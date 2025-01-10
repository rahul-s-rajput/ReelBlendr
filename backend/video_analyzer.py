import json
from google.cloud import videointelligence
from google.cloud.videointelligence_v1.types import Feature
from google.auth import default
import os
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional
from datetime import datetime
import subprocess
from collections import defaultdict
from pathlib import Path
from google.oauth2 import service_account
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, stop_after_attempt, wait_exponential
import tempfile

# Your VideoSegment and VideoAnalyzer classes here
@dataclass
class VideoSegment:
    """Stores comprehensive segment information"""
    start_time: float
    end_time: float
    labels: List[str] = field(default_factory=list)
    objects: List[Dict[str, float]] = field(default_factory=list)
    speech_transcription: str = ""
    text_detection: List[str] = field(default_factory=list)
    faces: List[Dict[str, float]] = field(default_factory=list)  # face attributes and confidence
    segment_confidence: float = 0.0

class VideoAnalyzer:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.results_file = data_dir / 'video_analysis_results1.json'
        self.client = videointelligence.VideoIntelligenceServiceClient()
        self.features = [
            videointelligence.Feature.LABEL_DETECTION,
            videointelligence.Feature.SHOT_CHANGE_DETECTION,
            videointelligence.Feature.OBJECT_TRACKING,
            videointelligence.Feature.SPEECH_TRANSCRIPTION,
            videointelligence.Feature.TEXT_DETECTION,
            videointelligence.Feature.FACE_DETECTION
        ]
        print("Initialized VideoAnalyzer with features:", self.features)
        self.max_dimension = 720  # Set maximum video dimension
        self.target_filesize_mb = 100  # Target file size in MB

    def preprocess_video(self, video_path: str) -> str:
        """Preprocess video to optimize size while maintaining quality"""
        try:
            # Create temp file
            temp_dir = tempfile.mkdtemp()
            output_path = os.path.join(temp_dir, f"processed_{os.path.basename(video_path)}")
            
            # Get video information
            probe = subprocess.run([
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height,duration',
                '-of', 'json',
                video_path
            ], capture_output=True, text=True)
            
            video_info = json.loads(probe.stdout)
            stream = video_info['streams'][0]
            
            # Calculate scaling with even dimensions
            width = int(stream.get('width', 1920))
            height = int(stream.get('height', 1080))
            scale_factor = min(self.max_dimension / max(width, height), 1)
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            
            # Ensure dimensions are even
            new_width = new_width - (new_width % 2)
            new_height = new_height - (new_height % 2)
            
            # Compress video while maintaining reasonable quality
            subprocess.run([
                'ffmpeg',
                '-i', video_path,
                '-vf', f'scale={new_width}:{new_height}',
                '-c:v', 'libx264',
                '-crf', '28',  # Compression quality (23-28 is good range)
                '-preset', 'medium',  # Encoding speed preset
                '-c:a', 'aac',
                '-b:a', '128k',
                '-y',  # Overwrite output file if it exists
                output_path
            ], check=True)
            
            return output_path
            
        except Exception as e:
            print(f"Error preprocessing video {video_path}: {str(e)}")
            return video_path

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    def analyze_video(self, video_path: str):
        """Analyze a single video file"""
        try:
            print(f"\nAnalyzing video: {video_path}")
            if not os.path.exists(video_path):
                print(f"Error: Video file not found at {video_path}")
                return None

            # Preprocess video before analysis
            processed_video_path = self.preprocess_video(video_path)
            print(f"Preprocessed video saved to: {processed_video_path}")

            # Get video duration using ffprobe
            probe = subprocess.run([
                'ffprobe', 
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                processed_video_path
            ], capture_output=True, text=True)
            
            duration = float(probe.stdout.strip())
            
            # Calculate timeout based on video duration (with a minimum of 20 minutes)
            timeout_seconds = max(2400, int(duration * 3))  # 3x video duration or minimum 20 minutes
            print(f"Setting timeout to {timeout_seconds} seconds for {duration} second video")

            with open(processed_video_path, 'rb') as file:
                input_content = file.read()
            

            label_config = videointelligence.LabelDetectionConfig(
                label_detection_mode=videointelligence.LabelDetectionMode.SHOT_AND_FRAME_MODE,
                video_confidence_threshold=0.6,
                frame_confidence_threshold=0.7,
                model="builtin/latest"
            )

            shot_config = videointelligence.ShotChangeDetectionConfig(
                model="builtin/latest"
            )

            video_context = videointelligence.VideoContext(
                label_detection_config=label_config,
                shot_change_detection_config=shot_config
            )

            # Start the asynchronous request with increased timeout
            operation = self.client.annotate_video(
                request={
                    "features": self.features,
                    "input_content": input_content,
                    "video_context": video_context
                }
            )

            print(f"Processing video {processed_video_path}...")
            result = operation.result(timeout=2400)
            return result

        except Exception as e:
            print(f"Analysis error for {processed_video_path}: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            # Cleanup temporary processed video if it exists
            if 'processed_video_path' in locals() and processed_video_path != video_path:
                try:
                    os.remove(processed_video_path)
                    os.rmdir(os.path.dirname(processed_video_path))
                except:
                    pass

    def process_results(self, result, video_path: str) -> Dict:
        """Process analysis results into a structured format"""
        try:
            if not result:
                return {"segments": []}

            print(f"Processing video file: {video_path}")
            
            # Get video duration using ffprobe
            probe = subprocess.run([
                'ffprobe', 
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ], capture_output=True, text=True)
            
            duration = float(probe.stdout.strip())
            print(f"Video duration: {duration} seconds")

            # Initialize segments dictionary
            segments = {}

            # 1. First create base segments from shot changes
            shot_annotations = result.annotation_results[0].shot_annotations if hasattr(result, 'annotation_results') else []
            
            if shot_annotations:
                print(f"Found {len(shot_annotations)} shot changes")
                for shot in shot_annotations:
                    start_time = shot.start_time_offset.seconds + shot.start_time_offset.microseconds / 1e6
                    end_time = shot.end_time_offset.seconds + shot.end_time_offset.microseconds / 1e6
                    
                    # Initialize segment structure
                    segment_key = f"{start_time}-{end_time}"
                    segments[segment_key] = {
                        "start_time": start_time,
                        "end_time": end_time,
                        "frames": {}
                    }

                    # 2. Collect frame label annotations for each second in the segment
                    for second in range(int(start_time+0.5), int(end_time+0.5)):
                        frame_labels = []
                        for frame_annotation in result.annotation_results[0].frame_label_annotations:
                            for frame in frame_annotation.frames:
                                time_offset = frame.time_offset.seconds + frame.time_offset.microseconds / 1e6
                                # Check if the frame falls within the current second
                                if second == int(time_offset):
                                    frame_labels.append({
                                        "label": frame_annotation.entity.description,
                                        "confidence_score": frame.confidence
                                    })
                        
                        # Add frame labels to the segment
                        segments[segment_key]["frames"][str(second)] = frame_labels

            else:
                # Fallback to single segment if no shots detected
                segment_key = "0.0-{}".format(duration)
                segments[segment_key] = {
                    "start_time": 0.0,
                    "end_time": duration,
                    "frames": {}
                }

                # 2. Collect frame label annotations for each second in the segment
                for second in range(0, int(duration+1)):
                    frame_labels = []
                    for frame_annotation in result.annotation_results[0].frame_label_annotations:
                        for frame in frame_annotation.frames:
                            time_offset = frame.time_offset.seconds + frame.time_offset.microseconds / 1e6
                            # Check if the frame falls within the current second
                            if second == int(time_offset):
                                frame_labels.append({
                                    "label": frame_annotation.entity.description,
                                    "confidence_score": frame.confidence
                                })
                    
                    # Add frame labels to the segment
                    segments[segment_key]["frames"][str(second)] = frame_labels

            print(f"Created {len(segments)} segments")

            return {
                "segments": segments,
                "duration": duration,
                "file_name": os.path.basename(video_path)
            }

        except Exception as e:
            print(f"Error processing results for {video_path}: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"segments": [], "duration": 0, "file_name": os.path.basename(video_path)}

    def analyze_videos_batch(self, video_paths: List[str], max_workers: int = 3, progress_callback=None) -> None:
        """Analyze multiple videos in parallel and save results"""
        if progress_callback:
            progress_callback(f"Starting analysis of {len(video_paths)} videos")

        print(f"Starting parallel batch analysis of {len(video_paths)} videos with {max_workers} workers")
        print(f"Video paths to analyze: {video_paths}")

        # Check existing results
        existing_results = {}
        if os.path.exists(self.results_file):
            try:
                with open(self.results_file, 'r') as f:
                    existing_results = json.load(f)
                print(f"Found existing analysis results at {self.results_file}")
            except Exception as e:
                print(f"Error reading existing results: {e}")

        # Filter out already analyzed videos
        videos_to_analyze = [
            path for path in video_paths 
            if os.path.basename(str(path)) not in existing_results
        ]

        if not videos_to_analyze:
            print("All videos already analyzed. Using cached results.")
            return

        print(f"Analyzing {len(videos_to_analyze)} new videos")
        analysis_results = existing_results.copy()

        # Process videos in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_video = {
                executor.submit(self.analyze_video, str(video_path)): video_path 
                for video_path in videos_to_analyze
            }

            # Process completed tasks as they finish
            for future in as_completed(future_to_video):
                video_path = future_to_video[future]
                try:
                    results = future.result()
                    if results:
                        file_name = os.path.basename(str(video_path))
                        analysis_results[file_name] = self.process_results(results, str(video_path))
                        if progress_callback:
                            progress_callback(f"Completed analysis for: {file_name}")
                except Exception as e:
                    if progress_callback:
                        progress_callback(f"Analysis failed for {video_path}: {str(e)}")

        # Save results to file
        print(f"Saving results for {len(analysis_results)} videos")
        with open(self.results_file, 'w') as f:
            json.dump(analysis_results, f, indent=2)
            print(f"Saved analysis results to {self.results_file}")