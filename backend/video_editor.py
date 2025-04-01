import json
import os
import time
import json
import os
import time
import httpx
import logging # Add logging
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from typing import List, Dict, Any, Optional, Callable

# Load environment variables early
load_dotenv()

# Configure logging for this module
logger = logging.getLogger(__name__)

class VideoEditor:
    def __init__(self):
        self.data_dir = Path("./data") # Define data_dir for saving debug files if needed
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("Error: GOOGLE_API_KEY not found in environment variables")

        # Initialize Gemini client
        self.client = genai.Client(api_key=self.api_key)
        # Set longer timeout
        timeout = httpx.Timeout(120.0, connect=10.0, read=120.0, write=60.0) # Increased timeout
        self.client._api_client._httpx_client = httpx.Client(timeout=timeout)
        print("Initialized VideoEditor with Gemini Client")

    def _construct_editing_prompt(self, video_analysis: Dict, audio_data: Dict, prompt_parameters: Dict) -> str:
        """Constructs the detailed editing plan prompt for Gemini."""

        # Log received parameters for debugging
        logger.debug(f"Constructing prompt with parameters: {prompt_parameters}")
        logger.debug(f"Audio data keys: {audio_data.keys() if audio_data else 'None'}")
        logger.debug(f"Video analysis keys: {video_analysis.keys() if video_analysis else 'None'}")


        # Extract relevant prompt parameters (add more as needed)
        content_focus = prompt_parameters.get('content_focus', 'General theme')
        style = prompt_parameters.get('stylePreference', 'Smooth/Cinematic')
        total_target_duration = audio_data.get('track_info', {}).get('duration', 30000) / 1000 # Convert ms to s

        # Basic validation - Check if video_analysis is a non-empty dict
        # and at least one value contains the expected 'video_analysis' key
        if not video_analysis or not isinstance(video_analysis, dict):
             raise ValueError("Video analysis data is missing or not a dictionary.")
        
        is_valid_analysis_present = any(
            isinstance(data, dict) and 'video_analysis' in data
            for data in video_analysis.values()
        )
        if not is_valid_analysis_present:
             raise ValueError("No valid 'video_analysis' key found within any entry in the video analysis data.")

        if not audio_data or 'segments' not in audio_data:
             raise ValueError("Invalid or missing audio data.")

        prompt = f"""
You are a professional video editor AI creating a short, engaging **reel**. You will be provided with:

1. A detailed JSON analysis of **one or more source videos**, including segmented content and quality rankings. You should utilize segments from **multiple source videos** if available to create a dynamic reel.
2. User inputs about audio segments and their durations.
3. User preferences for content focus and style.

Your task is to create a precise editing plan JSON that maps the best video segments (from **any** of the analyzed source videos) to each audio segment, optimizing for visual quality, thematic coherence with the content focus ('{content_focus}'), and matching the desired style ('{style}').

## Input Video Analysis (Contains data for one or more source videos)
```json
{json.dumps(video_analysis, indent=2)}
```

## Input Audio Segments & Info
```json
{json.dumps(audio_data, indent=2)}
```

## Output Requirements

Create a single JSON object containing the key "editing_plan". The value should be an array where each element represents a final video segment chosen to match an audio segment.

Each object in the "editing_plan" array must have these EXACT fields:
- "file_name": string (The original video file name from the analysis)
- "start_time": number (The start time in seconds within the original video file)
- "end_time": number (The end time in seconds within the original video file)
- "duration": number (The duration of this video segment, matching the corresponding audio segment duration)
- "output_start_time": number (The time in seconds where this segment should start in the final output video, based on audio segment timing)
- "segment_id": number (The original segment_id from the video analysis, if available)
- "quality_score": number (The overall_score from the video analysis rankings, if available)
- "match_rationale": string (Brief explanation why this video segment was chosen for the corresponding audio segment, considering content, quality, and style)

Example format for one element in the "editing_plan" array:
{{
  "file_name": "video9.mp4",
  "start_time": 45.3,
  "end_time": 50.5,
  "duration": 5.2,
  "output_start_time": 0.0,
  "segment_id": 12,
  "quality_score": 9.2,
  "match_rationale": "High emotional impact segment with strong composition matches the introductory audio."
}}

## Selection Criteria & Constraints

1.  **Match Audio Segments:** Create exactly one output video segment object for each segment defined in the input `audio_data['segments']`. The `duration` of the output video segment MUST match the `duration` of the corresponding audio segment. The `output_start_time` MUST match the `start` time of the corresponding audio segment.
2.  **Prioritize Quality:** Use the `segment_rankings` from the video analysis. Prefer video segments with higher `overall_score`.
3.  **Thematic Coherence:** Select video segments whose content (labels, descriptions) aligns with the user's content focus: '{content_focus}'.
4.  **Style Matching:** Choose segments and pacing appropriate for the desired style: '{style}'. For example, 'Fast-paced' might use shorter cuts from high-action segments, while 'Smooth/Cinematic' might use longer takes from stable, well-composed segments.
5.  **Avoid Repetition:** Try not to use the exact same video time range multiple times unless necessary.
6.  **Use Best Part:** If a ranked video segment is longer than the required audio duration, choose the most relevant or highest quality part of that segment (adjust `start_time` and `end_time` accordingly, ensuring `end_time - start_time` equals the audio duration).
7.  **Continuity & Variety:** Consider the visual flow between consecutive segments. **Crucially, avoid selecting two consecutive segments in the output plan if they represent a continuous, uninterrupted clip from the *same* source video file.** For example, if segment A ends at 15.0s in `video1.mp4` and segment B starts exactly at 15.0s in `video1.mp4`, do not place them back-to-back in the plan. Prioritize switching between different source files or non-adjacent parts of the same file for better reel dynamism.
8.  **Total Duration:** The sum of the durations in the final `editing_plan` should ideally be close to the total target duration ({total_target_duration:.2f} seconds).

## Output Format

Return ONLY the JSON object containing the "editing_plan" array. Do not include markdown formatting (```json ... ```) or any other text.
"""
        return prompt

    def generate_editing_plan(self, video_analysis_path: Path, audio_data: Dict, prompt_parameters: Dict, progress_callback: Optional[Callable] = None) -> List[Dict]:
        """
        Generates an editing plan using Gemini based on video analysis and audio data.
        Returns a list of segments formatted for VideoProcessor.
        """
        try:
            if progress_callback: progress_callback("Loading detailed video analysis...")
            print("Loading detailed video analysis...")
            with open(video_analysis_path, 'r') as f:
                video_analysis = json.load(f)

            # Check if analysis is per-file or combined
            # Assuming the new analyzer saves a dict where keys are filenames
            # If only one video was analyzed, the structure might be different
            # We need the analysis for the specific video file used.
            # For now, assume the structure contains the necessary 'video_analysis' key
            # This might need adjustment based on how analyze_videos_batch saves results
            if not video_analysis or not isinstance(video_analysis, dict):
                 raise ValueError(f"No valid analysis data (dictionary expected) found in file: {video_analysis_path}")

            # --- Removed logic that selected only the first video's analysis ---
            # We now pass the entire dictionary containing all video analyses

            # Validate that there's at least one valid analysis entry
            has_valid_entry = any(
                isinstance(value, dict) and 'video_analysis' in value and 'error' not in value
                for value in video_analysis.values()
            )
            if not has_valid_entry:
                raise ValueError("No valid 'video_analysis' structures found within the analysis file.")

            if progress_callback: progress_callback("Constructing prompt for Gemini editor...")
            print(f"Constructing prompt for Gemini editor using analysis for {len(video_analysis)} video(s)...")
            # Pass the complete video_analysis dictionary to the prompt constructor
            editing_prompt = self._construct_editing_prompt(video_analysis, audio_data, prompt_parameters)

            # Specify model
            model = "gemini-2.5-pro-exp-03-25" # Use the specific experimental model if needed
            # model = "models/gemini-1.5-pro-latest" # Use the latest stable model

            contents = [types.Content(role="user", parts=[types.Part.from_text(text=editing_prompt)])]

            # Configure response
            generate_content_config = types.GenerateContentConfig(
                response_mime_type="application/json", # Request JSON directly
            )

            if progress_callback: progress_callback("Requesting editing plan from Gemini...")
            print(f"Sending editing plan request to Gemini model: {model}")
            response = self.client.models.generate_content(
                model=model,
                contents=contents,
                config=generate_content_config,
            )
            print("Received editing plan response from Gemini.")

            # Parse the JSON response from the text attribute
            editing_plan_response = json.loads(response.text)
            if "editing_plan" not in editing_plan_response or not isinstance(editing_plan_response["editing_plan"], list):
                 print("Error: Gemini response did not contain a valid 'editing_plan' array.")
                 print("Raw Gemini Response:", editing_plan_response)
                 raise ValueError("Invalid editing plan format received from Gemini.")

            final_segments = editing_plan_response["editing_plan"]

            # Basic validation of the final segments
            if len(final_segments) != len(audio_data.get('segments', [])):
                 print(f"Warning: Number of generated video segments ({len(final_segments)}) does not match number of audio segments ({len(audio_data.get('segments', []))}).")
                 # Attempt to proceed, but this indicates a potential issue with the Gemini response.

            validated_segments = []
            for i, seg in enumerate(final_segments):
                if not all(k in seg for k in ["file_name", "start_time", "end_time", "duration", "output_start_time"]):
                    print(f"Warning: Skipping invalid segment {i+1} due to missing keys: {seg}")
                    continue
                # Ensure duration matches audio segment duration (within tolerance)
                audio_seg_duration = audio_data['segments'][i]['duration']
                if abs(seg['duration'] - audio_seg_duration) > 0.1: # Allow 100ms tolerance
                     print(f"Warning: Segment {i+1} duration ({seg['duration']:.2f}s) significantly differs from audio duration ({audio_seg_duration:.2f}s). Adjusting.")
                     seg['duration'] = audio_seg_duration
                     # Adjust end_time based on corrected duration
                     seg['end_time'] = seg['start_time'] + seg['duration']

                validated_segments.append(seg)

            if not validated_segments:
                 raise ValueError("No valid segments found in the generated editing plan.")

            print(f"Generated {len(validated_segments)} segments for the final video.")
            if progress_callback: progress_callback("Editing plan generated successfully.")

            # Save the generated plan for debugging
            plan_file = self.data_dir / "generated_editing_plan.json"
            try:
                with open(plan_file, "w") as f:
                    json.dump(editing_plan_response, f, indent=2)
                print(f"Saved generated editing plan to {plan_file}")
            except Exception as save_e:
                print(f"Error saving generated editing plan: {save_e}")


            return validated_segments # Return the list formatted for VideoProcessor

        except Exception as e:
            print(f"Error generating editing plan: {e}")
            import traceback
            traceback.print_exc()
            if progress_callback: progress_callback(f"Error generating editing plan: {e}")
            return [] # Return empty list on error

# Example usage (optional, for testing)
if __name__ == '__main__':
    # This part would only run if the script is executed directly
    print("Testing VideoEditor...")
    data_dir = Path("./data")
    editor = VideoEditor()

    # Mock data (replace with actual file paths and data)
    mock_analysis_path = data_dir / "video_analysis_results_gemini.json" # Use the new analysis file
    mock_audio_data = {
        'track_info': {'name': 'Test Track', 'duration': 15000}, # 15 seconds
        'segments': [
            {'start': 0.0, 'duration': 5.0},
            {'start': 5.0, 'duration': 4.5},
            {'start': 9.5, 'duration': 5.5}
        ]
    }
    mock_prompt_params = {
        'content_focus': 'Happy moments',
        'stylePreference': 'Smooth/Cinematic'
    }

    # Create a dummy analysis file if it doesn't exist
    if not mock_analysis_path.exists():
        print(f"Creating dummy analysis file: {mock_analysis_path}")
        dummy_analysis = {
            "video9.mp4": { # Assuming video9.mp4 was analyzed
                "video_analysis": {
                    "segments": [
                        {"segment_id": 1, "start_time": 0.0, "end_time": 5.0, "labels": ["happy", "people"]},
                        {"segment_id": 2, "start_time": 5.0, "end_time": 10.0, "labels": ["outdoors", "sun"]},
                        {"segment_id": 3, "start_time": 10.0, "end_time": 15.0, "labels": ["celebration", "food"]},
                        {"segment_id": 4, "start_time": 15.0, "end_time": 20.0, "labels": ["people", "talking"]}
                    ],
                    "segment_rankings": {
                         "ranked_segments": [
                              {"segment_id": 1, "overall_score": 9.0, "duration": 5.0},
                              {"segment_id": 3, "overall_score": 8.5, "duration": 5.0},
                              {"segment_id": 4, "overall_score": 8.0, "duration": 5.0},
                              {"segment_id": 2, "overall_score": 7.5, "duration": 5.0}
                         ]
                    }
                },
                "original_file_name": "video9.mp4",
                "original_duration": 20.0
            }
        }
        with open(mock_analysis_path, 'w') as f:
            json.dump(dummy_analysis, f, indent=2)

    try:
        final_segments = editor.generate_editing_plan(mock_analysis_path, mock_audio_data, mock_prompt_params)
        print("\nGenerated Final Segments:")
        print(json.dumps(final_segments, indent=2))
    except Exception as main_e:
        print(f"Error during test execution: {main_e}")
