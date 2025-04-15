from typing import List, Dict, Optional, Callable
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

    def create_video(self, video_segments: List[Dict], audio_file_path: Optional[str] = None, progress_callback: Optional[Callable] = None) -> Optional[Path]:
        """
        Create video using the provided segments and optional audio file.
        Uses VideoProcessor for FFmpeg execution.
        """
        try:
            if not video_segments:
                if progress_callback: progress_callback("Error: No video segments provided for creation.")
                print("Error: No video segments provided for creation.")
                return None
            # Generate output filename (consider adding timestamp or unique ID)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f'final_video_{timestamp}.mp4'
            output_path = str(self.output_dir / output_filename)

            if progress_callback: progress_callback(f"Initializing video processing for {output_filename}...")
            print(f"Initializing video processing for {output_filename}...")

            # Initialize VideoProcessor with segments and output path
            # VideoProcessor implicitly looks for 'trimmed_audio.mp3' in the data_dir passed to create_final_video
            processor = VideoProcessor(video_segments, output_path)

            if progress_callback: progress_callback("Starting FFmpeg processing...")
            print(f"\nStarting FFmpeg processing...")
            # Pass the base data directory to create_final_video, where VideoProcessor expects inputs/audio
            success, message = processor.create_final_video(self.data_dir)

            if success:
                if progress_callback: progress_callback(f"Video created successfully: {output_filename}")
                print(f"Successfully created video at: {output_path}")
                return Path(output_path)
            else:
                if progress_callback: progress_callback(f"Video creation failed: {message}")
                print(f"Failed to create video: {message}")
                return None

        except Exception as e:
            if progress_callback: progress_callback(f"Error during video creation: {e}")
            print(f"Error creating video: {e}")
            import traceback
            traceback.print_exc()
            return None
