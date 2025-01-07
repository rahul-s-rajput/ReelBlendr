from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime
from video_processor import VideoProcessor

class VideoCreator:
    def __init__(self, data_dir: Path):
        """Initialize VideoCreator with data directory"""
        self.data_dir = data_dir
        self.output_dir = data_dir / 'output'
        self.output_dir.mkdir(exist_ok=True)
        print(f"VideoCreator initialized with data directory: {data_dir}")
        print(f"Output directory: {self.output_dir}")

    def create_video(self, config: dict) -> Optional[Path]:
        """Create video using both video and audio analysis"""
        try:
            video_segments = config.get('video_segments', [])
            
            if not video_segments:
                print("No video segments provided")
                return None
            
            # Generate output filename with timestamp
            output_path = str(self.output_dir / f'final_video.mp4')
            
            # Initialize VideoProcessor with segments and output path
            processor = VideoProcessor(video_segments, output_path)
            
            print(f"\nCreating final video...")
            success, message = processor.create_final_video(self.data_dir)
            
            if success:
                print(f"Successfully created video at: {output_path}")
                return Path(output_path)
            else:
                print(f"Failed to create video: {message}")
                return None
            
        except Exception as e:
            print(f"Error creating video: {e}")
            import traceback
            traceback.print_exc()
            return None 