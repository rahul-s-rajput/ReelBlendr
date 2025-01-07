import subprocess
import os
import tempfile
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

class VideoProcessor:
    def __init__(self, edit_list: List[Dict], output_path: str):
        self.edit_list = edit_list
        self.output_path = output_path
        self.temp_dir = tempfile.mkdtemp()
        self.temp_files = []
        self.transition_duration = 0.2  # Transition duration in seconds
        print(f"Initialized VideoProcessor with {len(edit_list)} segments")
        print(f"Output path: {output_path}")

    def create_final_video(self, input_dir: Path) -> Tuple[bool, str]:
        try:
            filter_complex = []
            inputs = []
            
            print("\nSegment Information:")
            print("| Segment | Start Time | End Time | Duration | Total Duration | Offset |")
            print("|---------|------------|----------|-----------|----------------|---------|")
            
            total_duration = 0
            for i in range(len(self.edit_list)):
                # Add input
                inputs.extend(['-i', str(input_dir / Path(self.edit_list[i]['file_name']).name)])
            
            # Add audio input
            audio_path = input_dir / 'trimmed_audio.mp3'
            if audio_path.exists():
                inputs.extend(['-i', str(audio_path)])  # Add audio as last input
                has_audio = True
                print(f"Found audio file at: {audio_path}")
            else:
                has_audio = False
                print(f"No audio file found at: {audio_path}")

            total_duration = 0
            for i in range(len(self.edit_list)):
                # Calculate segment duration
                start_time = round(self.edit_list[i]["start_time"], 3)
                end_time = round(self.edit_list[i]["end_time"], 3)
                duration = end_time - start_time
                
                # Calculate total duration (subtract transition overlap for all except first segment)
                if i == 0:
                    total_duration = duration
                else:
                    total_duration = total_duration + duration - self.transition_duration
                
                # Calculate offset for transition (no offset for last segment)
                offset = total_duration - self.transition_duration if i < len(self.edit_list) - 1 else None
                
                # Print segment information
                offset_str = f"{offset:.4f}" if offset is not None else "-"
                print(f"| v{i} | {start_time:.4f} | {end_time:.4f} | {duration:.4f} | {total_duration:.4f} | {offset_str} |")
                
                # Add filtergraph for segment - trim first, then set PTS
                filter_complex.append(
                    f'[{i}:v]trim=start={start_time}:end={end_time},'
                    f'setpts=PTS-STARTPTS,'
                    f'scale=1920:1080:force_original_aspect_ratio=decrease,'
                    f'format=yuv420p,fps=30000/1001[v{i}]'
                )

            # Add transitions
            last_output = '[v0]'
            for i in range(len(self.edit_list) - 1):
                next_input = f'[v{i+1}]'
                output = f'[xf{i}]'
                print('--------------------------------')
                print(self.edit_list[i]['start_time'])
                print(self.edit_list[i]['end_time'])
                print(self.transition_duration)
                print('--------------------------------')
                # Calculate offset for this transition
                current_total = sum(
                    round(self.edit_list[j]["end_time"],3) - round(self.edit_list[j]["start_time"],3) 
                    for j in range(i + 1)
                ) - (i * self.transition_duration)
                offset = round(current_total - self.transition_duration, 3)
                
                # Add xfade filter
                filter_complex.append(
                    f'{last_output}{next_input}xfade=transition=fade:'
                    f'duration={self.transition_duration}:offset={offset}{output}'
                )
                
                last_output = output

            # Join filters and create command
            filter_string = ';'.join(filter for filter in filter_complex if filter)
            command = [
                'ffmpeg', '-y',
                *inputs,  # This includes both video and audio inputs
                '-filter_complex', filter_string,
                '-map', last_output,  # map video
            ]

            if has_audio:
                audio_input_index = len(self.edit_list)  # Audio is the last input
                command.extend([
                    '-map', f'{audio_input_index}:a',  # map audio from the last input
                    '-c:a', 'aac',  # audio codec
                    '-b:a', '192k'  # audio bitrate
                ])

            # Add remaining video settings
            command.extend([
                '-force_key_frames', 'expr:gte(t,n_forced*2)',
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-pix_fmt', 'yuv420p',
                '-r', '30000/1001',
                '-video_track_timescale', '30000',
                '-movflags', '+faststart',
                self.output_path
            ])

            print("\nRunning FFmpeg command:")
            print(' '.join(command))
            self._run_ffmpeg_command(command)
            
            return True, "Success"
            
        except Exception as e:
            print(f"Error during video processing: {str(e)}")
            return False, str(e)

    def _run_ffmpeg_command(self, command):
        if os.name == 'nt':  # Windows
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        else:  # Unix-like systems
            result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"FFmpeg error: {result.stderr}")
            raise Exception(f"FFmpeg error: {result.stderr}") 