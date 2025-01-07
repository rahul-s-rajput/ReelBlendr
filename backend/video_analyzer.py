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

# Your VideoSegment and VideoAnalyzer classes here
# (The code you provided) 
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
        self.results_file = data_dir / 'video_analysis_results.json'
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

    def analyze_video(self, video_path: str):
        """Analyze a single video file"""
        try:
            print(f"\nAnalyzing video: {video_path}")
            # Ensure the video path exists
            if not os.path.exists(video_path):
                print(f"Error: Video file not found at {video_path}")
                return None

            with open(video_path, 'rb') as file:
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

            # Start the asynchronous request
            operation = self.client.annotate_video(
                request={
                    "features": self.features,
                    "input_content": input_content,
                    "video_context": video_context
                }
            )

            print(f"Processing video {video_path}...")
            result = operation.result(timeout=600)  # 10-minute timeout
            return result

        except Exception as e:
            print(f"Analysis error for {video_path}: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

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

    def analyze_videos_batch(self, video_paths: List[str]) -> None:
        """Analyze multiple videos and save results"""
        print(f"Starting batch analysis of {len(video_paths)} videos")
        print(f"Video paths to analyze: {video_paths}")
        ### remove this if code for huggingface spaces
        # Check if analysis results already exist
        if os.path.exists(self.results_file):
            try:
                with open(self.results_file, 'r') as f:
                    existing_results = json.load(f)
                    
                # Check if all videos are already analyzed
                all_analyzed = all(
                    os.path.basename(path) in existing_results 
                    for path in video_paths
                )
                
                if all_analyzed:
                    print(f"Found existing analysis results at {self.results_file}")
                    print("Using cached results instead of re-analyzing videos")
                    return
                else:
                    print("Some videos not found in existing results, proceeding with analysis")
            except Exception as e:
                print(f"Error reading existing results: {e}")
                print("Proceeding with fresh analysis")
        
        # Proceed with analysis if needed
        analysis_results = {}
        for video_path in video_paths:
            # Convert to string if it's a Path object
            video_path = str(video_path)
            print(f"Processing: {video_path}")
            
            # Check if file exists
            if not os.path.exists(video_path):
                print(f"Error: File not found - {video_path}")
                continue
                
            results = self.analyze_video(video_path)
            if results:
                file_name = os.path.basename(video_path)
                analysis_results[file_name] = self.process_results(results, video_path)

        # Save results to file
        print(f"Saving results for {len(analysis_results)} videos")
        with open(self.results_file, 'w') as f:
            json.dump(analysis_results, f, indent=2)
            print(f"Saved analysis results to {self.results_file}")